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
from .dtf import (DtfRequest, UVDTF, build_dtf, garment_colors, load_order, load_placements, pixels_for,
                  placement_box, placement_names)
from .gang import build_gang, load_job, pack
from .kit import BuildOptions, SourceArt, generate_kit, publish, publish_kit
from .presets import GROUPS, PRESETS, STANDARD_PRESETS, VARIANTS, parse_size, preset_named, slugify
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
    add_background_arguments(parser)
    parser.add_argument("--trim", action="store_true", help="Crop to the artwork before fitting.")
    parser.add_argument("--trim-threshold", type=int, default=8, help="Alpha level that counts as artwork when trimming, 0 to 255.")
    parser.add_argument("--icon-background", metavar="COLOR", help="Opaque app icon background; default dark for white variants, white otherwise.")
    parser.add_argument("--banner-background", metavar="COLOR", help="Opaque background for banner and share sizes; default transparent.")
    parser.add_argument("--no-icons", action="store_true")
    parser.add_argument("--no-preview", action="store_true")
    parser.add_argument("--no-zip", action="store_true")
    parser.add_argument("--list", action="store_true", help="List the standard export sizes.")
    add_common_arguments(parser)
    return parser


def select_options(args):
    if not math.isfinite(args.padding) or not 0 <= args.padding < 0.5:
        raise ValueError("Padding must be a finite fraction from 0 to below 0.5.")
    if not 0 <= args.trim_threshold <= 255:
        raise ValueError("The trim threshold must be 0 to 255.")
    background = background_from_args(args)
    presets = list(STANDARD_PRESETS)
    if args.group:
        presets = [p for p in PRESETS if p.group == args.group]
    if args.preset:
        presets = [preset_named(args.preset)]
    if args.size:
        if not (args.group or args.preset):
            presets = []
        presets.extend(parse_size(value) for value in args.size)
    if len({p.name for p in presets}) != len(presets):
        raise ValueError("Each selected size must have a different name.")
    variants = VARIANTS if "all" in args.variants else tuple(dict.fromkeys(args.variants))
    icon_color = opaque_color(args.icon_background) if args.icon_background else None
    banner_color = opaque_color(args.banner_background) if args.banner_background else None
    return BuildOptions(tuple(presets), variants, tuple(dict.fromkeys(args.formats)), args.padding,
                        upscale=not args.no_upscale, icons=not args.no_icons, preview=not args.no_preview,
                        archive=not args.no_zip, icon_background=icon_color, background=background,
                        trim=args.trim_threshold if args.trim else None, banner_background=banner_color)


def options_from_brand(args, brand):
    """A brand file supplies everything the selection flags would; refuse conflicting flags."""
    defaults = parser_for_cli().parse_args([])
    conflicting = [name for name in ("group", "preset", "size", "variants", "formats", "padding", "remove_background",
                                     "background_mode", "tolerance", "feather", "trim", "icon_background",
                                     "banner_background", "source")
                   if getattr(args, name) != getattr(defaults, name)]
    if conflicting:
        raise ValueError("With --brand, sources, sizes, variants and colors come from the configuration file. "
                         "Remove: " + ", ".join("--" + name.replace("_", "-") for name in conflicting))
    return BuildOptions(brand.presets, brand.variants, brand.formats, brand.padding,
                        upscale=not args.no_upscale, icons=not args.no_icons, preview=not args.no_preview,
                        archive=not args.no_zip, icon_background=brand.icon_background + (255,) if brand.icon_background else None,
                        background=brand.background, trim=brand.trim, maps=brand.maps,
                        banner_background=brand.banner_background, web=brand.web)


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


def prepare_sources(roles, render_size, notes, background=None, trim=None, enlarges=None):
    """Load, matte and optionally trim every source for one brand. Returns role -> SourceArt.

    ``enlarges(image)`` may report whether raster exports would be upscaled.
    """
    prepared = {}
    for role, path in roles.items():
        image, vector, source_notes = load_image(path, render_size)
        notes.extend(f"{role}: {note}" for note in source_notes)
        image, used = matte(image, background, role, notes)
        if trim is not None:
            image, box = trim_to_art(image, trim)
            notes.append(f"{role}: trimmed to {image.width}x{image.height} px (box {box[0]},{box[1]} to {box[2]},{box[3]}).")
        if image.getchannel("A").getextrema()[0] == 255:
            notes.append(f"{role}: the source has a solid background. Converting to PNG does not remove it.")
        if not vector and enlarges and enlarges(image):
            notes.append(f"{role}: some raster exports were enlarged. More pixels do not restore missing detail.")
        prepared[role] = SourceArt(role, path, image, vector, used)
    return prepared


def kit_enlarges(options):
    if not options.upscale:
        return None
    return lambda image: any(min(p.width * (1 - 2 * options.padding) / image.width,
                                 p.height * (1 - 2 * options.padding) / image.height) > 1 for p in options.presets)


def run_kit(argv):
    parser = parser_for_cli()
    args = parser.parse_args(argv)
    if args.list:
        for preset in PRESETS:
            marker = "standard" if preset.standard else "optional"
            print(f"{preset.name:24} {preset.width:4}x{preset.height:<4} {preset.group:8} {marker:8} {preset.purpose}")
        print("Standard sizes are written by default; select optional sizes with --group, --preset or a brand file.")
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
                    sources = prepare_sources(roles, render_size, notes, options.background, options.trim,
                                              kit_enlarges(options))
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


DEFAULT_PLACEMENTS = ("left-chest", "full-front", "full-back")


def add_background_arguments(parser):
    parser.add_argument("--remove-background", metavar="COLOR", help="Explicit background color, such as '#ffffff', or 'auto' to measure the border.")
    parser.add_argument("--background-mode", choices=("edge", "all"), default="edge")
    parser.add_argument("--tolerance", type=int, default=0, help="Background matching tolerance, 0 to 255.")
    parser.add_argument("--feather", type=int, default=0, help="Soft-edge ramp width above the tolerance, 0 to 255; 0 is a hard cut.")


def background_from_args(args):
    if not 0 <= args.tolerance <= 255 or not 0 <= args.feather <= 255:
        raise ValueError("Tolerance and feather must be 0 to 255.")
    if not args.remove_background:
        if args.tolerance or args.feather or args.background_mode != "edge":
            raise ValueError("Background mode, tolerance and feather require --remove-background COLOR.")
        return None
    if args.remove_background.lower() != "auto":
        opaque_color(args.remove_background)
    return {"color": args.remove_background, "mode": args.background_mode,
            "tolerance": args.tolerance, "feather": args.feather}


def parser_for_dtf():
    parser = argparse.ArgumentParser(prog="logo-sizes dtf", description="Make 300 DPI DTF transfer files at exact placement sizes, with garment mockups, an order sheet and a press card.")
    parser.add_argument("source", nargs="?", type=Path, help="One image, or use --brand.")
    parser.add_argument("--brand", type=Path, metavar="BRAND.yaml", help="Brand configuration with sources, maps and a dtf section.")
    parser.add_argument("--placement", action="append", default=[], metavar="NAME",
                        help="Placement from the placements file; repeat for more. Default: the brand's list, or left-chest, full-front and full-back.")
    parser.add_argument("--audience", help="adult, youth or womens; default adult or the brand's setting.")
    parser.add_argument("--variants", nargs="+", help="Standard variants or map names from the brand file; default original or the brand's dtf list.")
    parser.add_argument("--garments", nargs="+", help="Garment colors from the placements file; default the brand's list or all of them.")
    parser.add_argument("--placements-file", type=Path, help="Alternative placements YAML; default is the packaged vendor file.")
    parser.add_argument("--order", type=Path, metavar="ORDER.yaml", help="Order file whose quantities fill the order sheet.")
    parser.add_argument("--allow-low-dpi", action="store_true", help="Write outputs below 150 DPI anyway. The true source DPI is still reported.")
    parser.add_argument("--no-harden", action="store_true", help="Keep soft alpha instead of thresholding it for DTF.")
    parser.add_argument("--choke", type=int, default=0, help="Shrink the hardened alpha by this many pixels to remove fringe; default 0.")
    add_background_arguments(parser)
    parser.add_argument("--list-placements", action="store_true", help="List placements and sizes from the placements file.")
    add_common_arguments(parser)
    return parser


def dtf_request(args, data, brand):
    """Resolve every DTF setting from the brand file and flags before reading artwork."""
    if brand:
        settings = brand.dtf
        design, maps, roles = brand.slug, brand.maps, {role: brand.sources[role] for role in ("primary", "symbol") if role in brand.sources}
        variants = tuple(args.variants or settings.get("variants") or brand.variants)
        background, trim = brand.background, brand.trim if brand.trim is not None else 8
        uv_sizes, uv_variants = brand.uvdtf.get("sizes", []), brand.uvdtf.get("variants")
    else:
        if not args.source:
            raise ValueError("Give a source image or --brand BRAND.yaml.")
        settings, maps = {}, {}
        design, roles = slugify(args.source.name), {"primary": args.source.resolve()}
        variants = tuple(args.variants or ["original"])
        background, trim = background_from_args(args), 8
        uv_sizes, uv_variants = [], None
    for variant in variants:
        if variant not in VARIANTS and variant not in maps:
            raise ValueError(f"Unknown variant '{variant}'. Use {', '.join(VARIANTS)} or a map name from the brand file.")
    audience = args.audience or settings.get("audience") or "adult"
    placements = list(args.placement or settings.get("placements") or DEFAULT_PLACEMENTS)
    overrides = settings.get("overrides", {})
    for placement in placements:
        placement_box(data, audience, placement, overrides)
    garments = garment_colors(data, args.garments or settings.get("garments")
                              or [k for k, v in data.get("garments", {}).items() if isinstance(v, dict)])
    if not 0 <= args.choke <= 10:
        raise ValueError("Choke must be 0 to 10 pixels.")
    quantities = load_order(args.order) if args.order else {}
    request = DtfRequest(design, audience, placements, variants, garments, maps, overrides,
                         tuple(settings.get("symbol_for", [])), uv_sizes, tuple(uv_variants) if uv_variants else None,
                         args.allow_low_dpi, not args.no_harden, args.choke, quantities, trim)
    return request, roles, background


def run_dtf(argv):
    args = parser_for_dtf().parse_args(argv)
    try:
        data = load_placements(args.placements_file)
        if args.list_placements:
            for audience in data["audiences"]:
                for name in placement_names(data, audience):
                    width, height = placement_box(data, audience, name)
                    print(f"{audience:8} {name:14} {width:5.2f} x {height:5.2f} in")
            print(f"Source: {data.get('sources', {}).get('placement_guide', '')} (checked {data.get('checked')})")
            return 0
        brand = load_brand(args.brand) if args.brand else None
        request, roles, background = dtf_request(args, data, brand)
        root = args.output_dir.resolve()
        destination = root / request.design / "dtf"
        for path in roles.values():
            check_source(path, root, request.design)
        if destination.is_symlink():
            raise ValueError("The dtf output is a symbolic link. Choose a different output folder.")
        if destination.exists() and not args.overwrite:
            raise ValueError(f"DTF output already exists for {request.design}. Use --overwrite to back it up and replace it.")
        boxes = [(request.audience, name, placement_box(data, request.audience, name, request.overrides)) for name in request.placements]
        boxes += [(UVDTF, size["name"], (float(size["width_in"]), float(size["height_in"]))) for size in request.uvdtf_sizes]
        print(f"{request.design}: {len(boxes)} placement(s) x {len(request.variants)} variant(s); audience {request.audience}; "
              f"garments {', '.join(request.garments)}")
        if args.dry_run:
            for audience, name, (width, height) in boxes:
                print(f"PLAN: {audience}/{name}: fit inside {width:.2f} x {height:.2f} in -> {destination / audience / name}")
            print("Dry run only. Artwork was not decoded or validated; nothing was written.")
            return 0
        render_size = max(max(pixels_for(width, height)) for _, _, (width, height) in boxes)
        notes = []
        refused = 0
        with output_lock(args.output_dir):
            sources = prepare_sources(roles, render_size, notes, background)
            with tempfile.TemporaryDirectory(prefix=".logo-build-", dir=args.output_dir) as temporary:
                folder, manifest, outputs = build_dtf(sources, request, data, Path(temporary))
                backup = publish([(folder, destination)], root, f"{request.design}-dtf", args.overwrite)
        print(f"DONE: {request.design} -> {destination}")
        if backup:
            print(f"  Previous dtf output kept at: {backup}")
        for output in outputs:
            verdict = output.verdict
            status = {"ok": "OK", "warn": "WARN", "fail": "FAIL"}[verdict.level]
            print(f"  {output.audience}/{output.placement} / {output.variant}: Ninja custom size "
                  f"{output.width_in:.2f} x {output.height_in:.2f} in ({output.width_px}x{output.height_px} px); "
                  f"source DPI {verdict.dpi} {status}")
            if not output.file:
                refused += 1
                print(f"    NOT WRITTEN: {verdict.dpi} DPI is below {150}. 300 DPI needs {verdict.needed[0]}x{verdict.needed[1]} px. "
                      "Supply a larger master, or pass --allow-low-dpi.")
            for warning in output.warnings:
                print(f"    WARNING: {warning}")
            for note in output.notes:
                print(f"    NOTE: {note}")
        for placement, picks in manifest["recommendations"].items():
            print(f"  {placement}: " + "; ".join(f"{garment} shirt: use {variant}" for garment, variant in picks.items()))
        print_file_table(manifest["files"], limit=40)
        for note in notes:
            print(f"  NOTE: {note}")
        print(f"Finished: {len(outputs) - refused} transfer file(s) written, {refused} refused for resolution. "
              f"Vendor data checked {data.get('checked')}; confirm current specs before ordering.")
        return 1 if refused else 0
    except (ValueError, OSError) as exc:
        print(f"Cannot export: {exc}", file=sys.stderr)
        return 1


def parser_for_gang():
    parser = argparse.ArgumentParser(prog="logo-sizes gang", description="Pack transfers onto wide gang sheets and write the sheet files, layout, cut list and preview.")
    parser.add_argument("job", type=Path, help="Job file (YAML or CSV) listing designs or files, sizes and quantities.")
    parser.add_argument("--no-rotate", action="store_true", help="Never rotate transfers, even if the job file allows it.")
    parser.add_argument("--no-pdf", action="store_true", help="Skip the PDF sheets.")
    parser.add_argument("--placements-file", type=Path, help="Alternative vendor data YAML; default is the packaged file.")
    add_common_arguments(parser)
    return parser


def run_gang(argv):
    args = parser_for_gang().parse_args(argv)
    try:
        data = load_placements(args.placements_file)
        root = args.output_dir.resolve()
        job = load_job(args.job, root)
        if args.no_rotate:
            job.rotate = False
        destination = root / "gang-sheets" / job.name
        if destination.is_symlink():
            raise ValueError("The gang-sheet output is a symbolic link. Choose a different output folder.")
        if destination.exists() and not args.overwrite:
            raise ValueError(f"Gang-sheet output already exists for {job.name}. Use --overwrite to back it up and replace it.")
        sheets = pack(job.items, job.width_in, job.lengths_in, job.gap_in, job.margin_in, job.rotate)
        copies = sum(item.qty for item in job.items)
        print(f"{job.name}: {len(job.items)} item(s), {copies} transfer(s) -> {len(sheets)} sheet(s); "
              f"gap {job.gap_in:g} in, margin {job.margin_in:g} in, rotation {'on' if job.rotate else 'off'}")
        for index, sheet in enumerate(sheets, 1):
            print(f"  sheet {index}: {sheet.width_in:g} x {sheet.length_in:g} in ({sheet.length_in / 12:g} ft), "
                  f"{len(sheet.placements)} transfer(s), used length {sheet.used_in:g} in, utilization {sheet.utilization:.0%}")
        if args.dry_run:
            for index, sheet in enumerate(sheets, 1):
                for placed in sheet.placements:
                    print(f"PLAN: sheet {index}: {placed.key} #{placed.copy} at {placed.x_in:.2f}, {placed.y_in:.2f} in, "
                          f"{placed.width_in:.2f} x {placed.height_in:.2f} in{' rotated' if placed.rotated else ''}")
            print("Dry run only. Nothing was written.")
            return 0
        with output_lock(args.output_dir):
            with tempfile.TemporaryDirectory(prefix=".logo-build-", dir=args.output_dir) as temporary:
                folder, layout, _, warnings = build_gang(job, data, Path(temporary), not args.no_pdf)
                backup = publish([(folder, destination)], root, f"gang-{job.name}", args.overwrite)
        print(f"DONE: {job.name} -> {destination}")
        if backup:
            print(f"  Previous gang-sheet output kept at: {backup}")
        print_file_table(layout["files"])
        for warning in warnings:
            print(f"  WARNING: {warning}")
        if "cost_compare" in layout:
            print(f"  COST: {layout['cost_compare']['summary']}")
        gang = data.get("gang_sheets", {})
        for key in ("upload_note", "spacing_note", "lengths_note"):
            if gang.get(key):
                print(f"  NOTE: {gang[key]}")
        print(f"Finished: {len(sheets)} sheet(s). Vendor data checked {data.get('checked')}; confirm the gang-sheet "
              "format and spacing with the vendor before the first upload.")
        return 0
    except (ValueError, OSError) as exc:
        print(f"Cannot export: {exc}", file=sys.stderr)
        return 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = "kit"
    if argv and argv[0] in COMMANDS:
        command = argv.pop(0)
    if command == "dtf":
        return run_dtf(argv)
    if command == "gang":
        return run_gang(argv)
    return run_kit(argv)
