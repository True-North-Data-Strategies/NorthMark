"""Command line interface with preflight validation and safe batch exports."""

import argparse
from contextlib import contextmanager
import math
from pathlib import Path
import sys
import tempfile

from . import __version__
from .imaging import SOURCE_EXTENSIONS, detect_background, load_image, opaque_color, remove_background
from .report import print_file_table
from .kit import BuildOptions, generate_kit, publish_kit
from .presets import GROUPS, PRESETS, VARIANTS, parse_size, slugify


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT if (PACKAGE_ROOT / "make_logo_sizes.py").is_file() else Path.cwd()


@contextmanager
def output_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".logo-kit.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise ValueError("Another export holds .logo-kit.lock. If it was interrupted, check that it has stopped before removing the lock.") from exc
    try:
        with handle:
            handle.write("Logo export in progress.\n")
        yield
    finally:
        lock.unlink()


def parser_for_cli():
    parser = argparse.ArgumentParser(description="Create safe logo sizes, color variants, previews and shareable brand kits.")
    parser.add_argument("source", nargs="?", type=Path, help="One image; omit to process the input folder.")
    parser.add_argument("-i", "--input-dir", type=Path, default=PROJECT_ROOT / "local-assets" / "input")
    parser.add_argument("-o", "--output-dir", type=Path, default=PROJECT_ROOT / "local-assets" / "exports")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--group", choices=GROUPS)
    selection.add_argument("--preset", help="One standard preset; see --list.")
    parser.add_argument("--size", action="append", default=[], metavar="NAME=WIDTHxHEIGHT",
                        help="Custom size; repeat for more. Without group/preset, replaces the standard sizes.")
    parser.add_argument("--variants", nargs="+", choices=(*VARIANTS, "all"), default=["original"])
    parser.add_argument("--formats", nargs="+", choices=("png", "webp"), default=["png"])
    parser.add_argument("--padding", type=float, default=0.08, help="Fraction per side, 0 to below 0.5; default 0.08.")
    parser.add_argument("--no-upscale", action="store_true", help="Keep raster art at or below its source pixel dimensions.")
    parser.add_argument("--remove-background", metavar="COLOR", help="Explicit background color, such as '#ffffff', or 'auto' to measure the border.")
    parser.add_argument("--background-mode", choices=("edge", "all"), default="edge")
    parser.add_argument("--tolerance", type=int, default=0, help="Background matching tolerance, 0 to 255.")
    parser.add_argument("--feather", type=int, default=0, help="Soft-edge ramp width above the tolerance, 0 to 255; 0 is a hard cut.")
    parser.add_argument("--icon-background", metavar="COLOR", help="Opaque app icon background; default dark for white variants, white otherwise.")
    parser.add_argument("--no-icons", action="store_true")
    parser.add_argument("--no-preview", action="store_true")
    parser.add_argument("--no-zip", action="store_true")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing kits after keeping complete dated backups.")
    parser.add_argument("--dry-run", action="store_true", help="Show the file plan without reading artwork or writing anything.")
    parser.add_argument("--list", action="store_true", help="List the standard export sizes.")
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def select_options(args):
    if not math.isfinite(args.padding) or not 0 <= args.padding < 0.5:
        raise ValueError("Padding must be a finite fraction from 0 to below 0.5.")
    if not 0 <= args.tolerance <= 255 or not 0 <= args.feather <= 255:
        raise ValueError("Tolerance and feather must be 0 to 255.")
    if not args.remove_background and (args.tolerance or args.feather or args.background_mode != "edge"):
        raise ValueError("Background mode, tolerance and feather require --remove-background COLOR.")
    presets = list(PRESETS)
    if args.group:
        presets = [p for p in presets if p.group == args.group]
    if args.preset:
        presets = [p for p in presets if p.name == args.preset]
        if not presets:
            raise ValueError("Unknown preset. Use --list to see the available names.")
    if args.size:
        if not (args.group or args.preset):
            presets = []
        presets.extend(parse_size(value) for value in args.size)
    if len({p.name for p in presets}) != len(presets):
        raise ValueError("Each selected size must have a different name.")
    variants = VARIANTS if "all" in args.variants else tuple(dict.fromkeys(args.variants))
    icon_color = opaque_color(args.icon_background) if args.icon_background else None
    if args.remove_background and args.remove_background.lower() != "auto":
        opaque_color(args.remove_background)
    return BuildOptions(tuple(presets), variants, tuple(dict.fromkeys(args.formats)), args.padding,
                        not args.no_upscale, not args.no_icons, not args.no_preview, not args.no_zip,
                        icon_color, args.remove_background, args.background_mode, args.tolerance,
                        args.feather)


def matte_source(image, options, notes):
    """Apply explicit or measured background removal and record what was used."""
    if not options.background_removal:
        return image
    if options.background_removal.lower() == "auto":
        detected = detect_background(image)
        color = detected.color
        tolerance = options.tolerance or detected.tolerance
        feather = options.feather or detected.feather
        notes.append("Background auto: color #%02x%02x%02x, border noise +/-%d, tolerance %d, feather %d."
                     % (*color, detected.noise, tolerance, feather))
    else:
        color = opaque_color(options.background_removal)
        tolerance, feather = options.tolerance, options.feather
    options.background_removal = "#%02x%02x%02x" % tuple(color[:3])
    options.tolerance, options.feather = tolerance, feather
    return remove_background(image, color, tolerance, options.background_mode, feather)


def source_plan(args):
    if args.source:
        sources = [args.source.resolve()]
    else:
        if not args.input_dir.is_dir():
            raise ValueError(f"Input folder not found: {args.input_dir}. Create it and add source artwork, or pass a file path.")
        sources = sorted(p.resolve() for p in args.input_dir.iterdir()
                         if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in SOURCE_EXTENSIONS)
    if not sources:
        raise ValueError(f"No supported images in the input folder: {args.input_dir}")
    slugs = {}
    root = args.output_dir.resolve()
    for source in sources:
        if not source.is_file() or source.suffix.lower() not in SOURCE_EXTENSIONS:
            raise ValueError(f"Source is missing or unsupported: {source.name}")
        slug = slugify(source.name)
        if slug in slugs:
            raise ValueError(f"Two inputs use the same output name '{slug}'. Rename one before running the batch.")
        slugs[slug] = source
        target = root / slug
        if source.is_relative_to(target):
            raise ValueError("An input is inside its own output folder. Move the source to the input folder first.")
        for path in (target, root / f"{slug}.zip"):
            if path.is_symlink():
                raise ValueError("An output is a symbolic link. Choose a different output folder.")
            if path.exists() and not args.overwrite:
                raise ValueError(f"Output already exists for {slug}. Use --overwrite to back it up, or choose another output folder.")
    return slugs


def main(argv=None):
    parser = parser_for_cli()
    args = parser.parse_args(argv)
    if args.list:
        for preset in PRESETS:
            print(f"{preset.name:28} {preset.width:4}x{preset.height:<4} {preset.group:8} {preset.purpose}")
        return 0
    try:
        options = select_options(args)
        plan = source_plan(args)
        print(f"{len(plan)} source(s); {len(options.presets)} size(s); variants: {', '.join(options.variants)}")
        if args.dry_run:
            for slug, source in plan.items():
                print(f"PLAN: {source.name} -> {args.output_dir / slug}")
            print("Dry run only. Artwork was not decoded or validated; nothing was written.")
            return 0
        done, failed = 0, 0
        with output_lock(args.output_dir):
            for slug, source in plan.items():
                try:
                    render_size = max(512, *(max(p.width, p.height) for p in options.presets))
                    image, vector, notes = load_image(source, render_size)
                    image = matte_source(image, options, notes)
                    if not vector and options.upscale:
                        if any(min(p.width * (1 - 2 * options.padding) / image.width,
                                   p.height * (1 - 2 * options.padding) / image.height) > 1 for p in options.presets):
                            notes.append("Some raster exports were enlarged. More pixels do not restore missing detail.")
                    if image.getchannel("A").getextrema()[0] == 255:
                        notes.append("The source has a solid background. Converting to PNG does not remove it.")
                    with tempfile.TemporaryDirectory(prefix=".logo-build-", dir=args.output_dir) as temporary:
                        kit = generate_kit(source, image, vector, slug, Path(temporary), options, notes)
                        backup = publish_kit(kit.folder, kit.archive, args.output_dir, args.overwrite)
                    done += 1
                    print(f"DONE: {slug} -> {args.output_dir / slug}")
                    if backup:
                        print(f"  Previous kit kept at: {backup}")
                    print_file_table(kit.manifest["files"])
                    for warning in kit.warnings:
                        print(f"  WARNING: {warning}")
                    for note in notes:
                        print(f"  NOTE: {note}")
                except Exception as exc:
                    failed += 1
                    print(f"FAILED: {slug}: {exc}", file=sys.stderr)
        print(f"Finished: {done} complete kit(s), {failed} failed. Originals were kept.")
        return 1 if failed else 0
    except (ValueError, OSError) as exc:
        print(f"Cannot export: {exc}", file=sys.stderr)
        return 1
