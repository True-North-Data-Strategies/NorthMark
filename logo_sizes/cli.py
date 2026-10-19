"""Command line interface with preflight validation and safe batch exports."""

import argparse
from contextlib import contextmanager
import math
from pathlib import Path
import sys
import tempfile

from . import __version__
from .config import ConfigError, load_brand
from .imaging import (SOURCE_EXTENSIONS, detect_background, load_image, opaque_color, remove_background,
                      trim_to_art)
from .kit import BuildOptions, SourceArt, generate_kit, publish_kit
from .presets import GROUPS, PRESETS, VARIANTS, parse_size, slugify
from .report import print_file_table


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT if (PACKAGE_ROOT / "make_logo_sizes.py").is_file() else Path.cwd()
COMMANDS = ("kit", "dtf", "gang")


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


def add_common_arguments(parser):
    parser.add_argument("-o", "--output-dir", type=Path, default=PROJECT_ROOT / "local-assets" / "exports")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing output after keeping complete dated backups.")
    parser.add_argument("--dry-run", action="store_true", help="Show the file plan without reading artwork or writing anything.")
    parser.add_argument("--version", action="version", version=__version__)


def parser_for_cli():
    parser = argparse.ArgumentParser(prog="logo-sizes", description="Create safe logo sizes, color variants, previews and shareable brand kits.")
    parser.add_argument("source", nargs="?", type=Path, help="One image; omit to process the input folder.")
    parser.add_argument("-i", "--input-dir", type=Path, default=PROJECT_ROOT / "local-assets" / "input")
    parser.add_argument("--brand", type=Path, metavar="BRAND.yaml", help="Brand configuration; supplies sources, sizes, variants and colors.")
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
    parser.add_argument("--trim", action="store_true", help="Crop to the artwork before fitting.")
    parser.add_argument("--trim-threshold", type=int, default=8, help="Alpha level that counts as artwork when trimming, 0 to 255.")
    parser.add_argument("--icon-background", metavar="COLOR", help="Opaque app icon background; default dark for white variants, white otherwise.")
    parser.add_argument("--no-icons", action="store_true")
    parser.add_argument("--no-preview", action="store_true")
    parser.add_argument("--no-zip", action="store_true")
    parser.add_argument("--list", action="store_true", help="List the standard export sizes.")
    add_common_arguments(parser)
    return parser


def select_options(args):
    if not math.isfinite(args.padding) or not 0 <= args.padding < 0.5:
        raise ValueError("Padding must be a finite fraction from 0 to below 0.5.")
    if not 0 <= args.tolerance <= 255 or not 0 <= args.feather <= 255 or not 0 <= args.trim_threshold <= 255:
        raise ValueError("Tolerance, feather and trim threshold must be 0 to 255.")
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
    background = None
    if args.remove_background:
        if args.remove_background.lower() != "auto":
            opaque_color(args.remove_background)
        background = {"color": args.remove_background, "mode": args.background_mode,
                      "tolerance": args.tolerance, "feather": args.feather}
    return BuildOptions(tuple(presets), variants, tuple(dict.fromkeys(args.formats)), args.padding,
                        upscale=not args.no_upscale, icons=not args.no_icons, preview=not args.no_preview,
                        archive=not args.no_zip, icon_background=icon_color, background=background,
                        trim=args.trim_threshold if args.trim else None)


def options_from_brand(args, brand):
    """A brand file supplies everything the selection flags would; refuse conflicting flags."""
    defaults = parser_for_cli().parse_args([])
    conflicting = [name for name in ("group", "preset", "size", "variants", "formats", "padding", "remove_background",
                                     "background_mode", "tolerance", "feather", "trim", "icon_background", "source")
                   if getattr(args, name) != getattr(defaults, name)]
    if conflicting:
        raise ValueError("With --brand, sources, sizes, variants and colors come from the configuration file. "
                         "Remove: " + ", ".join("--" + name.replace("_", "-") for name in conflicting))
    return BuildOptions(brand.presets, brand.variants, brand.formats, brand.padding,
                        upscale=not args.no_upscale, icons=not args.no_icons, preview=not args.no_preview,
                        archive=not args.no_zip, icon_background=brand.icon_background + (255,) if brand.icon_background else None,
                        background=brand.background, trim=brand.trim, maps=brand.maps)


def check_destination(root, slug, overwrite):
    for path in (root / slug, root / f"{slug}.zip"):
        if path.is_symlink():
            raise ValueError("An output is a symbolic link. Choose a different output folder.")
        if path.exists() and not overwrite:
            raise ValueError(f"Output already exists for {slug}. Use --overwrite to back it up, or choose another output folder.")


def check_source(source, root, slug):
    if not source.is_file() or source.suffix.lower() not in SOURCE_EXTENSIONS:
        raise ValueError(f"Source is missing or unsupported: {source.name}")
    if source.is_relative_to(root / slug):
        raise ValueError("An input is inside its own output folder. Move the source to the input folder first.")


def source_plan(args, brand=None):
    """Map each output slug to its source files by role, refusing collisions before any write."""
    root = args.output_dir.resolve()
    if brand:
        for source in brand.sources.values():
            check_source(source, root, brand.slug)
        check_destination(root, brand.slug, args.overwrite)
        return {brand.slug: dict(brand.sources)}
    if args.source:
        sources = [args.source.resolve()]
    else:
        if not args.input_dir.is_dir():
            raise ValueError(f"Input folder not found: {args.input_dir}. Create it and add source artwork, or pass a file path.")
        sources = sorted(p.resolve() for p in args.input_dir.iterdir()
                         if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in SOURCE_EXTENSIONS)
    if not sources:
        raise ValueError(f"No supported images in the input folder: {args.input_dir}")
    plan = {}
    for source in sources:
        slug = slugify(source.name)
        if slug in plan:
            raise ValueError(f"Two inputs use the same output name '{slug}'. Rename one before running the batch.")
        check_source(source, root, slug)
        check_destination(root, slug, args.overwrite)
        plan[slug] = {"primary": source}
    return plan


def matte(image, settings, role, notes):
    """Apply explicit or measured background removal; return the image and the settings used."""
    if not settings:
        return image, None
    used = dict(settings)
    if str(settings["color"]).lower() == "auto":
        detected = detect_background(image)
        color = detected.color
        used["tolerance"] = settings["tolerance"] or detected.tolerance
        used["feather"] = settings["feather"] or detected.feather
        used["color"] = "#%02x%02x%02x" % color
        notes.append(f"{role}: background auto measured color {used['color']}, border noise +/-{detected.noise}, "
                     f"tolerance {used['tolerance']}, feather {used['feather']}.")
    else:
        color = opaque_color(settings["color"])
        used["color"] = "#%02x%02x%02x" % color[:3]
    return remove_background(image, color, used["tolerance"], used["mode"], used["feather"]), used


def prepare_sources(roles, options, render_size, notes):
    """Load, matte and trim every source for one brand. Returns role -> SourceArt."""
    prepared = {}
    for role, path in roles.items():
        image, vector, source_notes = load_image(path, render_size)
        notes.extend(f"{role}: {note}" for note in source_notes)
        image, background = matte(image, options.background, role, notes)
        if options.trim is not None:
            image, box = trim_to_art(image, options.trim)
            notes.append(f"{role}: trimmed to {image.width}x{image.height} px (box {box[0]},{box[1]} to {box[2]},{box[3]}).")
        if image.getchannel("A").getextrema()[0] == 255:
            notes.append(f"{role}: the source has a solid background. Converting to PNG does not remove it.")
        if not vector and options.upscale and any(
                min(p.width * (1 - 2 * options.padding) / image.width,
                    p.height * (1 - 2 * options.padding) / image.height) > 1 for p in options.presets):
            notes.append(f"{role}: some raster exports were enlarged. More pixels do not restore missing detail.")
        prepared[role] = SourceArt(role, path, image, vector, background)
    return prepared


def run_kit(argv):
    parser = parser_for_cli()
    args = parser.parse_args(argv)
    if args.list:
        for preset in PRESETS:
            print(f"{preset.name:28} {preset.width:4}x{preset.height:<4} {preset.group:8} {preset.purpose}")
        return 0
    try:
        brand = load_brand(args.brand) if args.brand else None
        options = options_from_brand(args, brand) if brand else select_options(args)
        plan = source_plan(args, brand)
        print(f"{len(plan)} source(s); {len(options.presets)} size(s); variants: {', '.join(options.variants)}")
        if args.dry_run:
            for slug, roles in plan.items():
                print(f"PLAN: {', '.join(p.name for p in roles.values())} -> {args.output_dir / slug}")
            print("Dry run only. Artwork was not decoded or validated; nothing was written.")
            return 0
        done, failed = 0, 0
        with output_lock(args.output_dir):
            for slug, roles in plan.items():
                try:
                    notes = []
                    render_size = max(512, *(max(p.width, p.height) for p in options.presets))
                    sources = prepare_sources(roles, options, render_size, notes)
                    with tempfile.TemporaryDirectory(prefix=".logo-build-", dir=args.output_dir) as temporary:
                        kit = generate_kit(sources, slug, Path(temporary), options, notes)
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


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = "kit"
    if argv and argv[0] in COMMANDS:
        command = argv.pop(0)
    if command == "kit":
        return run_kit(argv)
    print(f"The {command} command is not available in this version.", file=sys.stderr)
    return 2
