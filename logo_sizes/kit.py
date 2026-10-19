"""Build complete kits in temporary storage, then publish with backups."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import uuid
import zipfile

from PIL import Image, ImageDraw, ImageFont

from . import __version__
from .imaging import fit_canvas, make_variant


SYMBOL_MAX_SIDE = 64      # sizes at or under this use the symbol source when one exists
HORIZONTAL_MIN_RATIO = 2  # canvases at least this wide for their height use the horizontal source


@dataclass
class SourceArt:
    """One prepared source image and where it came from."""
    role: str
    path: Path
    image: Image.Image
    vector: bool
    background: dict | None = None


@dataclass
class KitResult:
    folder: Path
    archive: Path | None
    manifest: dict
    warnings: list


@dataclass
class BuildOptions:
    presets: tuple
    variants: tuple = ("original",)
    formats: tuple = ("png",)
    padding: float = 0.08
    upscale: bool = True
    icons: bool = True
    preview: bool = True
    archive: bool = True
    icon_background: tuple | None = None
    background: dict | None = None
    trim: int | None = None
    maps: dict = field(default_factory=dict)


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def choose_source(sources, width, height):
    """Pick the symbol for tiny canvases, the horizontal art for banners, else the primary."""
    if "symbol" in sources and max(width, height) <= SYMBOL_MAX_SIDE:
        return "symbol"
    if "horizontal" in sources and width >= HORIZONTAL_MIN_RATIO * height:
        return "horizontal"
    return "primary"


def write_icons(pick, folder, padding, upscale, background):
    """``pick(width, height)`` returns the variant image to use for that canvas."""
    folder.mkdir()
    sizes = (16, 32, 48, 64, 128, 256)
    icons = [fit_canvas(pick(size, size), (size, size), padding, upscale) for size in sizes]
    icons[-1].save(folder / "favicon.ico", format="ICO", sizes=[(s, s) for s in sizes],
                   append_images=icons[:-1])
    manifest_icons = []
    for size in (192, 512):
        name = f"icon-{size}.png"
        fit_canvas(pick(size, size), (size, size), padding, upscale).save(folder / name, optimize=True)
        manifest_icons.append({"src": name, "sizes": f"{size}x{size}", "type": "image/png", "purpose": "any"})
        name = f"icon-maskable-{size}.png"
        # Keep the entire rectangular artwork inside the guaranteed 80% circle.
        safe_padding = max(padding, 0.5 - 0.4 / math.sqrt(2))
        fit_canvas(pick(size, size), (size, size), safe_padding, upscale, background).save(folder / name, optimize=True)
        manifest_icons.append({"src": name, "sizes": f"{size}x{size}", "type": "image/png", "purpose": "maskable"})
    fit_canvas(pick(180, 180), (180, 180), padding, upscale, background).save(folder / "apple-touch-icon.png", optimize=True)
    _write_json(folder / "manifest.webmanifest", {"icons": manifest_icons})


def write_preview(images, folder, exports):
    cell_width, row_height = 360, 300
    preview = Image.new("RGB", (cell_width * 3, 52 + row_height * len(images)), "#eeeeee")
    draw = ImageDraw.Draw(preview)
    font = ImageFont.load_default(size=17)
    draw.text((20, 16), "Logo variants and small-size checks", font=font, fill="black")
    for row, (name, image) in enumerate(images.items()):
        y = 52 + row * row_height
        for column, label in enumerate(("White", "Dark", "Transparency")):
            x = column * cell_width
            draw.text((x + 16, y + 8), f"{name.title()} / {label}", fill="black", font=font)
            background = Image.new("RGBA", (328, 244), "#ffffff" if column != 1 else "#202020")
            if column == 2:
                checker = ImageDraw.Draw(background)
                for top in range(0, 244, 16):
                    for left in range(0, 328, 16):
                        if (left // 16 + top // 16) % 2:
                            checker.rectangle((left, top, left + 15, top + 15), fill="#cccccc")
            large = fit_canvas(image, (328, 190), 0.08)
            background.alpha_composite(large, (0, 0))
            for index, size in enumerate((16, 32, 48)):
                tiny = fit_canvas(image, (size, size), 0.08)
                background.alpha_composite(tiny, (76 + index * 64, 194 + (48 - size) // 2))
            preview.paste(background.convert("RGB"), (x + 16, y + 36))
    preview.save(folder / "preview.png", optimize=True)
    links = "\n".join(f'<li><a href="{html.escape(path, quote=True)}">{html.escape(path)}</a></li>' for path in exports)
    page = f'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Logo kit preview</title>
<style>body{{font:17px system-ui,sans-serif;margin:2rem auto;padding:0 1rem;max-width:1100px;background:#f3f3f3;color:#222}}img{{max-width:100%;height:auto}}a{{color:#164b8b}}li{{margin:.4rem 0}}</style>
<h1>Logo kit preview</h1><p>Inspect the white, dark and checkerboard backgrounds. Small samples below each logo are 16, 32 and 48 pixels.</p>
<img src="preview.png" alt="Logo variants on white, dark and checkerboard backgrounds, with small icon samples">
<p><a href="GUIDE.txt">Which file to use</a></p><h2>Exports</h2><ul>{links}</ul></html>
'''
    (folder / "preview.html").write_text(page, encoding="utf-8")


GUIDE = '''LOGO KIT - WHICH FILE TO USE

original/: Original colors, with existing transparency preserved.
white/: White artwork for dark surfaces, if requested.
black/: Black artwork for light surfaces, if requested.
grayscale/: Neutral shades, if requested.
inverted/: A color negative. This changes every brand color, if requested.
Other folders are named color-map variants from the brand configuration,
such as reverse/ for a dark-background version.

PNG preserves transparency. WebP exports, if requested, are lossless.
app-icons/favicon.ico contains six browser icon sizes.
app-icons/apple-touch-icon.png has an opaque background.
app-icons/manifest.webmanifest is an ICON FRAGMENT. Merge its icons into
your application's manifest and adjust the paths for your website.
Maskable icons have extra safe padding and an opaque background.
White variants use a dark icon background by default; others use white.
The --icon-background option overrides that choice for all variants.

Use preview.html or preview.png to inspect dark/light contrast and tiny
icon legibility. A detailed wordmark often needs separate symbol-only art.
When a brand configuration supplies symbol and horizontal sources, sizes
of 64 pixels and under use the symbol and banner shapes use the horizontal
art; kit.json records which source made each file.

masters/source.* is the untouched primary original, including any source
metadata. Other masters/ files are the untouched symbol and horizontal
sources. A supplied vector SVG remains vector. Raster sources are NOT
vectorized. master-2048.png is a sized derivative and may have been
enlarged. Pixel dimensions alone do not specify print size, resolution or
CMYK color. Ask your printer for the required vector artwork and print
specifications.

Background removal only runs when explicitly requested. Edge mode keeps
enclosed details; all mode removes all matching colors, including details.
Check soft edges and textured backgrounds carefully before using a result.

Exports use RGB color. Source EXIF is not copied into generated images.
Platform requirements change; preset names are convenient starting sizes.
Check current requirements before uploading. Artwork rights remain with
their respective owners; the software license grants no artwork rights.
'''


def generate_kit(sources, slug, work, options, notes):
    """Write a complete kit for one brand into ``work/slug`` and return a KitResult.

    ``sources`` maps roles (primary, symbol, horizontal) to SourceArt.
    """
    primary = sources["primary"]
    folder = work / slug
    folder.mkdir()
    masters = folder / "masters"
    masters.mkdir()
    for role, art in sources.items():
        name = "source" if role == "primary" else role
        shutil.copy2(art.path, masters / (name + art.path.suffix.lower()))
    variants = {role: {variant: make_variant(art.image, variant, options.maps) for variant in options.variants}
                for role, art in sources.items()}
    exports, details, warnings = [], {}, []
    for name in options.variants:
        variant_dir = folder / name
        variant_dir.mkdir()
        for preset in options.presets:
            role = choose_source(sources, preset.width, preset.height)
            art = sources[role]
            fitted = fit_canvas(variants[role][name], (preset.width, preset.height), options.padding,
                                options.upscale or art.vector)
            for format_name in options.formats:
                path = variant_dir / f"{preset.name}.{format_name}"
                if format_name == "webp":
                    fitted.save(path, format="WEBP", lossless=True, exact=True)
                else:
                    fitted.save(path, format="PNG", optimize=True)
                relative = path.relative_to(folder).as_posix()
                exports.append(relative)
                details[relative] = {"width": preset.width, "height": preset.height, "variant": name,
                                     "preset": preset.name, "purpose": preset.purpose, "source": role}
                size = path.stat().st_size
                if preset.max_kb is not None and size > preset.max_kb * 1024:
                    warnings.append(f"{relative} is {size / 1024:.1f} KB, over the {preset.max_kb} KB "
                                    f"cap for {preset.name}.")
        if options.icons:
            background = options.icon_background or ((32, 32, 32, 255) if name == "white" else (255, 255, 255, 255))

            def pick(width, height, name=name):
                return variants[choose_source(sources, width, height)][name]
            write_icons(pick, variant_dir / "app-icons", options.padding,
                        options.upscale or primary.vector, background)
            exports.extend(p.relative_to(folder).as_posix() for p in sorted((variant_dir / "app-icons").iterdir()))
    if options.preview:
        write_preview(variants["primary"], folder, exports)
    (folder / "GUIDE.txt").write_text(GUIDE, encoding="utf-8")
    metadata = {
        "generator_version": __version__, "brand": slug, "source_name": primary.path.name,
        "source_sha256": hashlib.sha256(primary.path.read_bytes()).hexdigest(), "vector_source": primary.vector,
        "sources": {role: {"name": art.path.name, "sha256": hashlib.sha256(art.path.read_bytes()).hexdigest(),
                           "vector": art.vector, "background": art.background} for role, art in sources.items()},
        "variants": list(options.variants), "formats": list(options.formats), "padding": options.padding,
        "upscale_raster": options.upscale, "background": options.background, "trim": options.trim,
        "notes": notes, "warnings": warnings, "files": [],
    }
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            relative = path.relative_to(folder).as_posix()
            entry = {"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "bytes": path.stat().st_size}
            entry.update(details.get(relative, {}))
            metadata["files"].append(entry)
    _write_json(folder / "kit.json", metadata)
    archive = None
    if options.archive:
        archive = work / f"{slug}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    bundle.write(path, path.relative_to(work).as_posix())
    return KitResult(folder, archive, metadata, warnings)


def publish(items, output_root, label, overwrite=False):
    """Move built items to their destinations in one step, keeping a backup of anything replaced.

    ``items`` is a list of (built_path, destination) pairs. Either every item lands
    or nothing changes: a failure part-way restores the previous state.
    """
    destinations = [destination for _, destination in items]
    for destination in destinations:
        if destination.is_symlink():
            raise ValueError("An output is a symbolic link. Choose a different output folder.")
        if destination.exists() and not overwrite:
            raise FileExistsError(f"Output already exists for {label}. Use --overwrite to keep a backup and replace it.")
    backup = None
    moved_old, moved_new = [], []
    try:
        if any(path.exists() for path in destinations):
            backups = output_root / ".backups"
            if backups.is_symlink():
                raise ValueError("The backup folder must not be a symbolic link.")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = backups / f"{label}-{stamp}-{uuid.uuid4().hex[:8]}"
            backup.mkdir(parents=True)
            for path in destinations:
                if path.exists():
                    saved = backup / path.name
                    path.rename(saved)
                    moved_old.append((saved, path))
        for built, destination in items:
            destination.parent.mkdir(parents=True, exist_ok=True)
            built.rename(destination)
            moved_new.append((destination, built))
    except BaseException:
        # Preserve the previous complete output if publishing any part fails.
        for destination, original in reversed(moved_new):
            destination.rename(original)
        for saved, original in reversed(moved_old):
            saved.rename(original)
        raise
    return backup


def publish_kit(folder, archive, output_root, overwrite=False):
    slug = folder.name
    items = [(folder, output_root / slug)]
    if archive:
        items.append((archive, output_root / f"{slug}.zip"))
    return publish(items, output_root, slug, overwrite)
