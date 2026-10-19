"""DTF transfer outputs: exact print sizes, honest DPI checks, hardened alpha, mockups and order sheets.

Every vendor number comes from the placements data file, never from code.
"""

from dataclasses import dataclass, field
import csv
import hashlib
from importlib import resources
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from . import __version__
from .config import load_yaml, resolve_color
from .imaging import fit_canvas, make_variant, trim_to_art


DATA = resources.files("logo_sizes") / "data"
PLACEMENTS_FILE = "ninja-placements.yaml"
ORDER_SHEET_COLUMNS = ("design", "placement", "audience", "variant", "garment_colors", "width_in", "height_in",
                       "width_px", "height_px", "source_dpi", "warnings", "file", "qty")
DPI_TARGET = 300
DPI_FAIL_BELOW = 150
UVDTF = "uvdtf"
LOW_CONTRAST_RATIO = 1.5
MOCKUP_PX_PER_IN = 24
MOCKUP_SHIRT_IN = (24, 30)


def load_placements(path=None):
    """Load the vendor placements file; the packaged copy unless a path is given."""
    if path is not None:
        return load_yaml(path)
    with resources.as_file(DATA / PLACEMENTS_FILE) as packaged:
        return load_yaml(packaged)


def placement_names(data, audience):
    """Placements with a published size for this audience."""
    group = data["audiences"].get(audience)
    if not isinstance(group, dict):
        raise ValueError(f"Unknown audience '{audience}'. Choose from {', '.join(data['audiences'])}.")
    return [name for name, entry in group.items() if isinstance(entry, dict) and "average" in entry]


def placement_box(data, audience, name, overrides=None):
    """Width and height in inches of the box the art must fit, from an override or the vendor average."""
    if overrides and name in overrides:
        box = overrides[name]
        return float(box["width_in"]), float(box["height_in"])
    group = data["audiences"].get(audience)
    if not isinstance(group, dict):
        raise ValueError(f"Unknown audience '{audience}'. Choose from {', '.join(data['audiences'])}.")
    entry = group.get(name)
    if not isinstance(entry, dict) or "average" not in entry:
        available = ", ".join(placement_names(data, audience))
        raise ValueError(f"The placements file lists no {name} size for {audience}. Available: {available}.")
    return float(entry["average"]["width"]), float(entry["average"]["height"])


def placement_info(data, audience, name):
    group = data["audiences"].get(audience, {})
    entry = group.get(name) if isinstance(group, dict) else None
    return entry if isinstance(entry, dict) else {}


def fit_inches(art_width, art_height, box_width, box_height):
    """Largest size, in hundredths of an inch, that keeps the art's aspect inside the box."""
    scale = min(box_width / art_width, box_height / art_height)
    return round(art_width * scale + 1e-9, 2), round(art_height * scale + 1e-9, 2)


def pixels_for(width_in, height_in, dpi=DPI_TARGET):
    return max(1, round(width_in * dpi)), max(1, round(height_in * dpi))


@dataclass(frozen=True)
class DpiVerdict:
    dpi: int
    level: str          # ok, warn or fail
    needed: tuple       # pixels for 300 DPI at this size


def effective_dpi(art_width, art_height, width_in, height_in):
    """Real detail per inch before any resampling, with the verdict thresholds applied."""
    dpi = int(round(min(art_width / width_in, art_height / height_in)))
    level = "ok" if dpi >= DPI_TARGET else "warn" if dpi >= DPI_FAIL_BELOW else "fail"
    return DpiVerdict(dpi, level, pixels_for(width_in, height_in))


def harden_alpha(image, choke=0):
    """Make alpha opaque or clear, keeping at most a one-pixel soft edge. Returns (image, soft pixels left)."""
    alpha = image.getchannel("A")
    hard = alpha.point(lambda v: 255 if v >= 128 else 0)
    if choke > 0:
        hard = hard.filter(ImageFilter.MinFilter(2 * choke + 1))
    ring = ImageChops.subtract(hard, hard.filter(ImageFilter.MinFilter(3)))
    new_alpha = Image.composite(alpha, hard, ring)
    result = image.copy()
    result.putalpha(new_alpha)
    return result, sum(new_alpha.histogram()[1:255])


@dataclass(frozen=True)
class StrokeReport:
    fraction: float          # share of the art thinner than the minimum
    thinnest_px: int | None  # estimated thinnest stroke found below the minimum, or None


def thin_strokes(image, min_px):
    """Estimate how much of the art is thinner than ``min_px`` using morphological opening."""
    hard = image.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    total = hard.histogram()[255]
    if not total:
        return StrokeReport(0.0, None)
    radius = max(1, math.ceil(min_px / 2))
    thinnest = None
    fraction = 0.0
    for step in range(1, radius + 1):
        size = 2 * step + 1
        opened = hard.filter(ImageFilter.MinFilter(size)).filter(ImageFilter.MaxFilter(size))
        removed = ImageChops.subtract(hard, opened).histogram()[255] / total
        if thinnest is None and removed > 0.001:
            thinnest = 2 * step
        fraction = removed
    return StrokeReport(round(fraction, 4), thinnest)


def _luminance(rgb):
    def channel(value):
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    red, green, blue = (channel(v) for v in rgb[:3])
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def edge_color(image):
    """Average color of the art's outer edge, where it meets the garment."""
    alpha = image.getchannel("A")
    hard = alpha.point(lambda v: 255 if v >= 128 else 0)
    ring = ImageChops.subtract(hard, hard.filter(ImageFilter.MinFilter(3)))
    mask = ring if ring.getbbox() else hard
    histogram = image.convert("RGB").histogram(mask=mask)
    count = sum(histogram[:256]) or 1
    return tuple(sum(v * n for v, n in enumerate(histogram[c * 256:(c + 1) * 256])) // count for c in range(3))


def contrast_ratio(color_a, color_b):
    bright, dark = sorted((_luminance(color_a), _luminance(color_b)), reverse=True)
    return (bright + 0.05) / (dark + 0.05)


def choose_variants_for_garments(variant_images, garments):
    """Recommend a variant per garment color and flag (variant, garment) pairs with low contrast."""
    edges = {name: edge_color(image) for name, image in variant_images.items()}
    recommendation, flags = {}, []
    for garment, rgb in garments.items():
        ratios = {name: contrast_ratio(edge, rgb) for name, edge in edges.items()}
        recommendation[garment] = max(ratios, key=ratios.get)
        flags.extend((name, garment) for name, ratio in ratios.items() if ratio < LOW_CONTRAST_RATIO)
    return recommendation, flags


def garment_colors(data, names):
    table = data.get("garments", {})
    colors = {}
    for name in names:
        entry = table.get(name)
        if not isinstance(entry, dict) or "color" not in entry:
            available = ", ".join(k for k, v in table.items() if isinstance(v, dict))
            raise ValueError(f"Unknown garment color '{name}'. Available: {available}.")
        colors[name] = resolve_color(entry["color"])
    return colors


def write_mockup(art, garment_rgb, placement, label, position, width_in, height_in, path):
    """Composite the transfer on a flat garment swatch at shirt scale."""
    scale = MOCKUP_PX_PER_IN
    canvas = Image.new("RGBA", (MOCKUP_SHIRT_IN[0] * scale, MOCKUP_SHIRT_IN[1] * scale), garment_rgb + (255,))
    draw = ImageDraw.Draw(canvas)
    light = _luminance(garment_rgb) > 0.4
    ink = (40, 40, 40, 255) if light else (230, 230, 230, 255)
    torso = (2 * scale, 2 * scale, (MOCKUP_SHIRT_IN[0] - 2) * scale, (MOCKUP_SHIRT_IN[1] - 2) * scale)
    draw.rectangle(torso, outline=ink, width=2)
    draw.line((torso[0] + 7 * scale, torso[1], torso[2] - 7 * scale, torso[1]), fill=ink, width=4)
    placed = fit_canvas(art, (max(1, round(width_in * scale)), max(1, round(height_in * scale))), 0)
    center_x = canvas.width // 2
    top = torso[1] + 3 * scale
    if placement in ("left-chest", "sleeve"):
        center_x += 5 * scale   # wearer's left is the viewer's right
    elif placement in ("full-back", "upper-back", "back-collar"):
        top = torso[1] + 4 * scale
    elif placement == "oversize":
        top = torso[1] + 2 * scale
    canvas.alpha_composite(placed, (center_x - placed.width // 2, top))
    font = ImageFont.load_default(size=18)
    text = f"{label}: {width_in:.2f} x {height_in:.2f} in"
    draw.text((torso[0] + 8, torso[3] + 8), text, fill=ink, font=font)
    if position:
        draw.text((torso[0] + 8, torso[3] + 30), position, fill=ink, font=font)
    canvas.convert("RGB").save(path, optimize=True)


@dataclass
class DtfRequest:
    """Everything one DTF run needs, resolved before any artwork is read."""
    design: str
    audience: str
    placements: list
    variants: tuple
    garments: dict                  # name -> rgb
    maps: dict = field(default_factory=dict)
    overrides: dict = field(default_factory=dict)
    symbol_for: tuple = ()
    uvdtf_sizes: list = field(default_factory=list)
    uvdtf_variants: tuple | None = None
    allow_low_dpi: bool = False
    harden: bool = True
    choke: int = 0
    quantities: dict = field(default_factory=dict)   # (placement, variant, audience) -> qty
    trim_threshold: int = 8


@dataclass
class DtfOutput:
    placement: str
    audience: str
    variant: str
    width_in: float
    height_in: float
    width_px: int
    height_px: int
    source_px: tuple
    verdict: DpiVerdict
    file: str | None
    warnings: list
    notes: list


def load_order(path):
    """Quantities from an order file: (design, placement, variant, audience) -> qty."""
    data = load_yaml(path)
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError(f"{Path(path).name} needs an 'items' list.")
    quantities = {}
    for item in items:
        if not isinstance(item, dict) or "design" not in item:
            raise ValueError("Every order item needs at least a design.")
        qty = item.get("qty", 1)
        if not isinstance(qty, int) or isinstance(qty, bool) or qty < 0:
            raise ValueError("Order quantities must be whole numbers.")
        key = (str(item["design"]), str(item.get("placement", "")), str(item.get("variant", "original")),
               str(item.get("audience", "")))
        quantities[key] = quantities.get(key, 0) + qty
    return quantities


def _quantity(request, placement, variant, audience):
    for audience_key in (audience, ""):
        qty = request.quantities.get((request.design, placement, variant, audience_key))
        if qty is not None:
            return qty
    return None


def _format_in(value):
    return f"{value:.2f}"


def build_dtf(sources, request, data, work):
    """Write every DTF output for one design into ``work/dtf``; returns (folder, manifest, outputs)."""
    folder = work / "dtf"
    folder.mkdir()
    mockups = folder / "mockups"
    industry = data.get("industry", {})
    min_line_mm = industry.get("min_line_mm")
    min_px = math.ceil(min_line_mm / 25.4 * DPI_TARGET) if min_line_mm else None
    max_mb = data.get("files", {}).get("max_upload_mb")
    variants_by_role = {role: {name: make_variant(art.image, name, request.maps) for name in request.variants}
                        for role, art in sources.items()}
    jobs = [(request.audience, name, placement_box(data, request.audience, name, request.overrides),
             request.variants, True) for name in request.placements]
    for size in request.uvdtf_sizes:
        jobs.append((UVDTF, size["name"], (float(size["width_in"]), float(size["height_in"])),
                     request.uvdtf_variants or request.variants, False))
    outputs, recommendations, flags = [], {}, []
    for audience, placement, box, variants, garments_apply in jobs:
        role = "symbol" if placement in request.symbol_for and "symbol" in sources else "primary"
        trimmed = {}
        for variant in variants:
            trimmed[variant], _ = trim_to_art(variants_by_role[role][variant], request.trim_threshold)
        if garments_apply and request.garments:
            recommendation, low = choose_variants_for_garments(trimmed, request.garments)
            recommendations[placement] = recommendation
            flags.extend((placement, variant, garment) for variant, garment in low)
        for variant, art in trimmed.items():
            width_in, height_in = fit_inches(art.width, art.height, *box)
            width_px, height_px = pixels_for(width_in, height_in)
            verdict = effective_dpi(art.width, art.height, width_in, height_in)
            warnings, notes = [], []
            if role == "symbol":
                notes.append("symbol source used")
            if verdict.level == "fail":
                warnings.append(f"{verdict.dpi} DPI at this size is below {DPI_FAIL_BELOW}. 300 DPI needs "
                                f"{verdict.needed[0]}x{verdict.needed[1]} px.")
            elif verdict.level == "warn":
                warnings.append(f"{verdict.dpi} DPI at this size is below {DPI_TARGET}. 300 DPI needs "
                                f"{verdict.needed[0]}x{verdict.needed[1]} px.")
            info = placement_info(data, audience, placement)
            span = info.get("range")
            if span and not (span["width"][0] <= width_in <= span["width"][1]
                             and span["height"][0] <= height_in <= span["height"][1]):
                warnings.append(f"{_format_in(width_in)} x {_format_in(height_in)} in is outside Ninja's "
                                f"{placement} range {span['width'][0]}-{span['width'][1]} x "
                                f"{span['height'][0]}-{span['height'][1]} in.")
            file_name = None
            if verdict.level != "fail" or request.allow_low_dpi:
                if verdict.level == "fail":
                    warnings.append("Written with --allow-low-dpi.")
                render = fit_canvas(art, (width_px, height_px), 0, True)
                if width_px > art.width or height_px > art.height:
                    notes.append(f"enlarged from {art.width}x{art.height} px; true source DPI {verdict.dpi}")
                soft = sum(render.getchannel("A").histogram()[1:255])
                if request.harden:
                    render, soft = harden_alpha(render, request.choke)
                    notes.append(f"{soft} semi-transparent pixel(s) remain after hardening")
                elif soft:
                    warnings.append(f"{soft} semi-transparent pixels; DTF prints soft alpha badly (industry guidance).")
                if min_px:
                    report = thin_strokes(render, min_px)
                    if report.thinnest_px is not None:
                        warnings.append(f"About {report.fraction:.1%} of the art is thinner than {min_line_mm} mm "
                                        f"(thinnest about {report.thinnest_px / DPI_TARGET * 25.4:.2f} mm); "
                                        "industry guidance says such strokes may not print.")
                target_dir = folder / audience / placement / variant
                target_dir.mkdir(parents=True, exist_ok=True)
                file_name = f"{request.design}-{placement}-{_format_in(width_in)}x{_format_in(height_in)}in.png"
                path = target_dir / file_name
                render.save(path, format="PNG", dpi=(DPI_TARGET, DPI_TARGET))
                size_mb = path.stat().st_size / 1_000_000
                if max_mb and size_mb > max_mb:
                    warnings.append(f"File is {size_mb:.1f} MB, over the {max_mb} MB upload ceiling.")
                if garments_apply:
                    mockups.mkdir(exist_ok=True)
                    for garment, rgb in request.garments.items():
                        write_mockup(render, rgb, placement, f"{placement} / {variant}", info.get("position", ""),
                                     width_in, height_in, mockups / f"{placement}-{variant}-on-{garment}.png")
                file_name = path.relative_to(folder).as_posix()
            outputs.append(DtfOutput(placement, audience, variant, width_in, height_in, width_px, height_px,
                                     (art.width, art.height), verdict, file_name, warnings, notes))
    for placement, variant, garment in flags:
        for output in outputs:
            if output.placement == placement and output.variant == variant:
                output.warnings.append(f"Low contrast against the {garment} garment; "
                                       f"use the {recommendations[placement][garment]} variant there.")
    rows = []
    for output in outputs:
        recommended = [garment for garment, variant in recommendations.get(output.placement, {}).items()
                       if variant == output.variant]
        qty = _quantity(request, output.placement, output.variant, output.audience)
        rows.append({"design": request.design, "placement": output.placement, "audience": output.audience,
                     "variant": output.variant, "garment_colors": ", ".join(recommended),
                     "width_in": _format_in(output.width_in), "height_in": _format_in(output.height_in),
                     "width_px": output.width_px, "height_px": output.height_px, "source_dpi": output.verdict.dpi,
                     "warnings": " ".join(output.warnings), "file": output.file or "",
                     "qty": "" if qty is None else qty})
    with (folder / "order-sheet.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ORDER_SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    card = write_press_card(folder, request, data, outputs, recommendations)
    manifest = {
        "generator_version": __version__, "design": request.design, "audience": request.audience,
        "placements_source": {key: str(value) for key, value in data.get("sources", {}).items()},
        "placements_checked": str(data.get("checked")), "dpi": DPI_TARGET, "mirrored": False,
        "alpha_hardened": request.harden, "choke_px": request.choke,
        "garments": {name: "#%02x%02x%02x" % rgb for name, rgb in request.garments.items()},
        "recommendations": recommendations,
        "low_contrast": [{"placement": p, "variant": v, "garment": g} for p, v, g in flags],
        "outputs": rows, "press_card": card.name, "files": [],
    }
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.name != "dtf.json":
            manifest["files"].append({"path": path.relative_to(folder).as_posix(), "bytes": path.stat().st_size,
                                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (folder / "dtf.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return folder, manifest, outputs


def press_card_lines(request, data, outputs, recommendations):
    """Plain-text lines for the press card; the PDF and PNG renderers share them."""
    lines = [f"PRESS CARD: {request.design}", f"Audience: {request.audience}. Files are 300 DPI PNG, not mirrored.", ""]
    for output in outputs:
        info = placement_info(data, output.audience, output.placement)
        status = output.verdict.level.upper()
        lines.append(f"{output.placement} / {output.variant}: {_format_in(output.width_in)} x "
                     f"{_format_in(output.height_in)} in, source {output.verdict.dpi} DPI {status}")
        if info.get("position"):
            lines.append(f"    Position: {info['position']}")
        if output.placement in recommendations:
            picks = ", ".join(f"{garment}: {variant}" for garment, variant in recommendations[output.placement].items())
            lines.append(f"    Garments: {picks}")
        if not output.file:
            lines.append("    NOT WRITTEN: resolution too low. Supply a larger master.")
    lines.append("")
    press = data.get("press", {})
    lines.append("Press settings")
    for setting in press.get("settings", []):
        parts = [f"{key.replace('_', ' ')}: {value}" for key, value in setting.items() if key != "source"]
        lines.append("    " + "; ".join(parts))
    if press.get("caveat"):
        lines.append(f"    {press['caveat']}")
    return lines


def write_press_card(folder, request, data, outputs, recommendations):
    lines = press_card_lines(request, data, outputs, recommendations)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        path = folder / "press-card.png"
        page = Image.new("RGB", (1275, 1650), "white")
        draw = ImageDraw.Draw(page)
        font = ImageFont.load_default(size=22)
        for index, line in enumerate(lines[:60]):
            draw.text((60, 60 + index * 26), line, fill="black", font=font)
        page.save(path, optimize=True)
        return path
    path = folder / "press-card.pdf"
    page = canvas.Canvas(str(path), pagesize=letter)
    page.setTitle(f"Press card: {request.design}")
    y = letter[1] - 54
    for line in lines:
        if y < 54:
            page.showPage()
            y = letter[1] - 54
        page.setFont("Helvetica-Bold" if line.startswith("PRESS CARD") else "Helvetica", 10)
        page.drawString(54, y, line[:110])
        y -= 14
    page.showPage()
    page.save()
    return path
