"""Gang sheets: deterministic shelf packing onto wide sheets, with PNG, PDF, layout, cut list and preview.

Sheet widths, standard lengths and the gap and margin defaults come from the
placements data file or the job file, never from constants in code.
"""

from dataclasses import dataclass, field
import csv
import hashlib
import json
from pathlib import Path
import struct
import zlib

from PIL import Image, ImageDraw, ImageFont

from . import __version__
from .config import load_yaml
from .dtf import DPI_TARGET, load_placements
from .imaging import fit_canvas
from .presets import slugify


CUT_LIST_COLUMNS = ("sheet", "item", "design", "file", "copy", "width_in", "height_in", "x_in", "y_in", "rotated")
JOB_CSV_COLUMNS = ("design", "placement", "variant", "file", "width_in", "height_in", "qty")
GANG_MAX_PIXELS = 60_000_000      # per transfer image; sheets themselves are rendered in bands
BAND_ROWS = 1024
PREVIEW_PX_PER_IN = 20


@dataclass
class GangItem:
    key: str
    design: str
    file: Path
    width_in: float
    height_in: float
    qty: int = 1
    placement: str = ""


@dataclass
class Placed:
    key: str
    design: str
    file: Path
    copy: int
    x_in: float
    y_in: float
    width_in: float
    height_in: float
    rotated: bool


@dataclass
class Sheet:
    width_in: float
    length_in: float
    used_in: float
    placements: list = field(default_factory=list)

    @property
    def utilization(self):
        area = sum(p.width_in * p.height_in for p in self.placements)
        return area / (self.width_in * self.length_in) if self.length_in else 0.0


@dataclass
class Job:
    name: str
    items: list
    width_in: float
    lengths_in: tuple
    gap_in: float
    margin_in: float
    rotate: bool
    prices: dict = field(default_factory=dict)
    source: Path | None = None


def _orientations(width, height, policy):
    as_is, turned = (width, height, False), (height, width, True)
    if policy == "none":
        return [as_is]
    if policy == "landscape":
        return [as_is] if width >= height else [turned]
    if policy == "portrait":
        return [as_is] if height >= width else [turned]
    return [as_is, turned]


def _shelves(pieces, width, gap, margin, policy):
    """First-fit shelf packing with unbounded length. Returns [(height, [placements])]."""
    usable = width - 2 * margin
    shelves = []
    for item, copy in pieces:
        choice = None
        for index, shelf in enumerate(shelves):
            for w, h, rotated in _orientations(item.width_in, item.height_in, policy):
                if h <= shelf["height"] + 1e-9 and shelf["x"] + w <= width - margin + 1e-9:
                    score = (index, shelf["height"] - h)
                    if choice is None or score < choice[0]:
                        choice = (score, index, w, h, rotated)
        if choice is None:
            options = [o for o in _orientations(item.width_in, item.height_in, policy) if o[0] <= usable + 1e-9]
            if not options:
                raise ValueError(f"{item.key} ({item.width_in:g} x {item.height_in:g} in) is wider than the sheet.")
            w, h, rotated = min(options, key=lambda o: (o[1], o[0]))
            shelves.append({"height": h, "x": margin, "items": []})
            index = len(shelves) - 1
        else:
            _, index, w, h, rotated = choice
        shelf = shelves[index]
        shelf["items"].append(Placed(item.key, item.design, item.file, copy, shelf["x"], 0.0, w, h, rotated))
        shelf["x"] += w + gap
    return [(shelf["height"], shelf["items"]) for shelf in shelves]


def pack(items, width, lengths, gap, margin, rotate=True):
    """Pack every copy of every item onto the fewest, shortest standard sheets. Deterministic."""
    lengths = tuple(sorted(float(length) for length in lengths))
    if not lengths or not items:
        raise ValueError("Gang sheets need at least one standard length and one item.")
    longest = lengths[-1]
    usable_w, usable_l = width - 2 * margin, longest - 2 * margin
    pieces = []
    for item in items:
        fits = (item.width_in <= usable_w and item.height_in <= usable_l) or \
               (rotate and item.height_in <= usable_w and item.width_in <= usable_l)
        if not fits or item.width_in <= 0 or item.height_in <= 0:
            raise ValueError(f"{item.key} ({item.width_in:g} x {item.height_in:g} in) cannot fit a {width:g} x {longest:g} in sheet"
                             f"{' even rotated' if rotate else ''}. Reduce it or split the design.")
        pieces.extend((item, copy) for copy in range(1, item.qty + 1))
    pieces.sort(key=lambda piece: (-max(piece[0].width_in, piece[0].height_in),
                                   -min(piece[0].width_in, piece[0].height_in), piece[0].key, piece[1]))
    policies = ("fit", "landscape", "portrait") if rotate else ("none",)
    best = None
    for policy in policies:
        shelves = _shelves(pieces, width, gap, margin, policy)
        total = 2 * margin + sum(h for h, _ in shelves) + gap * (len(shelves) - 1)
        if best is None or total < best[0] - 1e-9:
            best = (total, shelves)
    shelves = best[1]
    sheets, current, used = [], [], 2 * margin
    for height, placed in shelves:
        extra = height + (gap if current else 0)
        if current and used + extra > longest + 1e-9:
            sheets.append(current)
            current, used = [], 2 * margin
            extra = height
        current.append((height, placed))
        used += extra
    sheets.append(current)
    result = []
    for group in sheets:
        used = 2 * margin + sum(h for h, _ in group) + gap * (len(group) - 1)
        length = next(l for l in lengths if l >= used - 1e-9)
        sheet = Sheet(width, length, round(used, 4))
        y = margin
        for height, placed in group:
            for p in placed:
                sheet.placements.append(Placed(p.key, p.design, p.file, p.copy, round(p.x_in, 4), round(y, 4),
                                               p.width_in, p.height_in, p.rotated))
            y += height + gap
        result.append(sheet)
    return result


def _inches_from_png(path):
    with Image.open(path) as image:
        if image.width * image.height > GANG_MAX_PIXELS:
            raise ValueError(f"{path.name} exceeds the {GANG_MAX_PIXELS:,} pixel limit for a transfer image.")
        dpi = image.info.get("dpi", (DPI_TARGET, DPI_TARGET))
        horizontal = dpi[0] if dpi and dpi[0] else DPI_TARGET
        vertical = dpi[1] if dpi and len(dpi) > 1 and dpi[1] else DPI_TARGET
        return round(image.width / horizontal, 2), round(image.height / vertical, 2)


def _resolve_item(raw, base, exports_root, index):
    design = str(raw.get("design") or "").strip()
    placement = str(raw.get("placement") or "").strip()
    file_value = str(raw.get("file") or "").strip()
    qty = raw.get("qty", 1)
    if isinstance(qty, str):
        qty = int(qty) if qty.strip() else 1
    if not isinstance(qty, int) or isinstance(qty, bool) or qty < 1:
        raise ValueError(f"Item {index}: qty must be a whole number of 1 or more.")
    if file_value:
        path = (base / Path(file_value).expanduser()).resolve()
        design = design or slugify(path.name)
    elif design and placement:
        variant = str(raw.get("variant") or "original").strip()
        audience = str(raw.get("audience") or "adult").strip()
        folder = exports_root / design / "dtf" / audience / placement / variant
        matches = sorted(folder.glob("*.png")) if folder.is_dir() else []
        if not matches:
            raise ValueError(f"Item {index}: no DTF output found for {design} {audience}/{placement}/{variant} under "
                             f"{exports_root}. Run logo-sizes dtf for that design first.")
        path = matches[-1]
    else:
        raise ValueError(f"Item {index}: give a file, or a design with a placement.")
    if not path.is_file() or path.suffix.lower() != ".png":
        raise ValueError(f"Item {index}: {path.name} is missing or not a PNG.")
    width = raw.get("width_in")
    height = raw.get("height_in")
    if isinstance(width, str):
        width = float(width) if width.strip() else None
    if isinstance(height, str):
        height = float(height) if height.strip() else None
    if width is None or height is None:
        file_w, file_h = _inches_from_png(path)
        if width is None and height is None:
            width, height = file_w, file_h
        elif width is None:
            width = round(height * file_w / file_h, 2)
        else:
            height = round(width * file_h / file_w, 2)
    for value in (width, height):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 < value <= 300:
            raise ValueError(f"Item {index}: sizes must be positive inches.")
    key = f"{design}-{placement}" if placement else design
    return GangItem(key, design, path, float(width), float(height), qty, placement)


def load_job(path, exports_root):
    """Read a YAML or CSV job file. Items resolve against the job file's folder and the exports root."""
    path = Path(path).resolve()
    exports_root = Path(exports_root).resolve()
    defaults = load_placements().get("gang_sheets", {})
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or [f.strip() for f in reader.fieldnames] != list(JOB_CSV_COLUMNS):
                raise ValueError(f"{path.name} needs the header: {','.join(JOB_CSV_COLUMNS)} (see examples/templates/gang-job.csv).")
            raw_items = [row for row in reader if any((v or "").strip() for v in row.values())]
        data, name = {}, path.stem
    else:
        data = load_yaml(path)
        name = str(data.get("job") or path.stem)
        raw_items = data.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            raise ValueError(f"{path.name} needs a non-empty 'items' list.")
    if name != slugify(name):
        raise ValueError("The job name must be lowercase letters, digits and hyphens.")
    sheet = data.get("sheet", {}) or {}
    unknown = set(sheet) - {"width_in", "lengths_ft", "lengths_in", "gap_in", "margin_in", "rotate"}
    if unknown:
        raise ValueError(f"Unknown sheet setting(s): {', '.join(sorted(unknown))}.")
    width = float(sheet.get("width_in", defaults.get("width_in", 22)))
    if "lengths_in" in sheet:
        lengths = tuple(float(v) for v in sheet["lengths_in"])
    else:
        lengths = tuple(float(v) * 12 for v in sheet.get("lengths_ft", defaults.get("lengths_ft", [])))
    if not lengths or any(l <= 0 for l in lengths):
        raise ValueError("Sheet lengths must be positive; set sheet.lengths_ft or sheet.lengths_in.")
    gap = float(sheet.get("gap_in", defaults.get("gap_in", 0.25)))
    margin = float(sheet.get("margin_in", defaults.get("margin_in", 0.25)))
    if gap < 0 or margin < 0 or width <= 2 * margin:
        raise ValueError("Gap and margin must be zero or more, and the margin must leave usable width.")
    rotate = bool(sheet.get("rotate", True))
    items = []
    for index, raw in enumerate(raw_items, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"Item {index} must be a mapping.")
        items.append(_resolve_item(raw, path.parent, exports_root, index))
    prices = data.get("prices", {}) or {}
    if not isinstance(prices, dict):
        raise ValueError("prices must be a mapping.")
    return Job(name, items, width, lengths, gap, margin, rotate, prices, path)


def write_png_banded(path, width, height, paint, dpi=DPI_TARGET, band_rows=BAND_ROWS):
    """Stream an RGBA PNG in horizontal bands so very long sheets never sit in memory at once.

    ``paint(top, bottom)`` returns an RGBA image of ``width`` x (bottom - top) pixels.
    """
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)

    pixels_per_meter = round(dpi / 0.0254)
    compressor = zlib.compressobj(6)
    stride = width * 4
    with path.open("wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        handle.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
        handle.write(chunk(b"pHYs", struct.pack(">IIB", pixels_per_meter, pixels_per_meter, 1)))
        for top in range(0, height, band_rows):
            bottom = min(height, top + band_rows)
            raw = paint(top, bottom).tobytes()
            rows = b"".join(b"\x00" + raw[r * stride:(r + 1) * stride] for r in range(bottom - top))
            compressed = compressor.compress(rows)
            if compressed:
                handle.write(chunk(b"IDAT", compressed))
        handle.write(chunk(b"IDAT", compressor.flush()))
        handle.write(chunk(b"IEND", b""))


class _ImageCache:
    """Each transfer image is decoded and sized once per orientation."""

    def __init__(self):
        self.cache = {}

    def get(self, placed, dpi):
        size = (max(1, round(placed.width_in * dpi)), max(1, round(placed.height_in * dpi)))
        key = (placed.file, size, placed.rotated)
        if key not in self.cache:
            with Image.open(placed.file) as source:
                if source.width * source.height > GANG_MAX_PIXELS:
                    raise ValueError(f"{placed.file.name} exceeds the {GANG_MAX_PIXELS:,} pixel limit.")
                image = source.convert("RGBA")
            if placed.rotated:
                image = image.rotate(90, expand=True)
            self.cache[key] = fit_canvas(image, size, 0, True)
        return self.cache[key]


def render_sheet_png(sheet, path, dpi=DPI_TARGET, cache=None):
    cache = cache or _ImageCache()
    width = round(sheet.width_in * dpi)
    height = round(sheet.length_in * dpi)
    boxes = []
    for placed in sheet.placements:
        x, y = round(placed.x_in * dpi), round(placed.y_in * dpi)
        image = cache.get(placed, dpi)
        boxes.append((x, y, image))

    def paint(top, bottom):
        band = Image.new("RGBA", (width, bottom - top), (0, 0, 0, 0))
        for x, y, image in boxes:
            if y >= bottom or y + image.height <= top:
                continue
            crop_top, crop_bottom = max(0, top - y), min(image.height, bottom - y)
            band.alpha_composite(image.crop((0, crop_top, image.width, crop_bottom)), (x, max(0, y - top)))
        return band

    write_png_banded(path, width, height, paint, dpi)


def render_sheet_pdf(sheet, path, title):
    """One PDF page the size of the sheet; each transfer image is embedded once and placed per copy."""
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    page = canvas.Canvas(str(path), pagesize=(sheet.width_in * 72, sheet.length_in * 72))
    page.setTitle(title)
    readers = {}
    for placed in sheet.placements:
        reader = readers.setdefault(placed.file, ImageReader(str(placed.file)))
        page.saveState()
        if placed.rotated:
            page.translate(placed.x_in * 72, (sheet.length_in - placed.y_in) * 72)
            page.rotate(-90)
            page.drawImage(reader, 0, 0, placed.height_in * 72, placed.width_in * 72, mask="auto")
        else:
            page.drawImage(reader, placed.x_in * 72, (sheet.length_in - placed.y_in - placed.height_in) * 72,
                           placed.width_in * 72, placed.height_in * 72, mask="auto")
        page.restoreState()
    page.showPage()
    page.save()


def write_preview(sheets, path):
    scale = PREVIEW_PX_PER_IN
    gap = 24
    width = sum(round(s.width_in * scale) for s in sheets) + gap * (len(sheets) + 1)
    height = max(round(s.length_in * scale) for s in sheets) + 2 * gap + 20
    preview = Image.new("RGB", (width, height), "#dddddd")
    draw = ImageDraw.Draw(preview)
    font = ImageFont.load_default(size=12)
    x = gap
    for index, sheet in enumerate(sheets, 1):
        w, h = round(sheet.width_in * scale), round(sheet.length_in * scale)
        draw.rectangle((x, gap, x + w, gap + h), fill="white", outline="#444444")
        for placed in sheet.placements:
            box = (x + placed.x_in * scale, gap + placed.y_in * scale,
                   x + (placed.x_in + placed.width_in) * scale, gap + (placed.y_in + placed.height_in) * scale)
            draw.rectangle(box, fill="#cfe3f7", outline="#1f4f82")
            label = f"{placed.key} #{placed.copy}" + (" R" if placed.rotated else "")
            draw.text((box[0] + 2, box[1] + 1), label[:28], fill="#111111", font=font)
        draw.text((x, gap + h + 4), f"sheet {index}: {sheet.width_in:g} x {sheet.length_in:g} in, "
                                     f"{sheet.utilization:.0%} used", fill="#111111", font=font)
        x += w + gap
    preview.save(path, optimize=True)


def upload_warning(size_bytes, max_mb):
    if max_mb and size_bytes > max_mb * 1_000_000:
        return f"{size_bytes / 1_000_000:.1f} MB is over the {max_mb} MB upload ceiling; confirm with the vendor."
    return None


def _money(value):
    return f"${value:,.2f}"


def cost_compare(sheet_lengths_ft, items, prices, tiers):
    """Cost per transfer for gang sheets versus by-size orders, from configured prices only."""
    by_length = {str(k): float(v) for k, v in (prices.get("gang_sheet_by_length_ft") or {}).items()}
    by_size = {str(k): float(v) for k, v in (prices.get("by_size") or {}).items()}
    total_qty = sum(item.qty for item in items)
    missing = [str(ft) for ft in sheet_lengths_ft if f"{ft:g}" not in by_length and str(ft) not in by_length]
    if missing or not total_qty:
        return {"summary": "Cost compare skipped: no gang-sheet price configured for " + ", ".join(missing) + " ft."}
    gang_total = sum(by_length.get(f"{ft:g}", by_length.get(str(ft))) for ft in sheet_lengths_ft)
    priced = []
    for item in items:
        price = by_size.get(item.placement) or by_size.get(item.design) or by_size.get(item.key)
        if price is None:
            return {"summary": f"Cost compare skipped: no by-size price configured for {item.key}.",
                    "gang_total": gang_total, "gang_per_transfer": gang_total / total_qty}
        priced.append(price * item.qty)
    percent = 0
    for tier in tiers or []:
        high = tier.get("max_qty")
        if tier["min_qty"] <= total_qty and (high is None or total_qty <= high):
            percent = tier["percent"]
    by_size_total = sum(priced) * (1 - percent / 100)
    currency = prices.get("currency", "USD")
    summary = (f"Gang sheets: {_money(gang_total)} for {total_qty} transfers ({_money(gang_total / total_qty)} each). "
               f"By size: {_money(by_size_total)} with the {percent}% tier ({_money(by_size_total / total_qty)} each). "
               f"Prices as entered in the job file ({currency}).")
    return {"gang_total": round(gang_total, 2), "gang_per_transfer": round(gang_total / total_qty, 4),
            "by_size_total": round(by_size_total, 2), "by_size_discount_percent": percent,
            "by_size_per_transfer": round(by_size_total / total_qty, 4), "summary": summary}


def build_gang(job, data, work, want_pdf=True):
    """Pack and write every output for a job into ``work/<job>``. Returns (folder, manifest, sheets, warnings)."""
    sheets = pack(job.items, job.width_in, job.lengths_in, job.gap_in, job.margin_in, job.rotate)
    folder = work / job.name
    folder.mkdir()
    warnings = []
    max_mb = data.get("files", {}).get("max_upload_mb")
    cache = _ImageCache()
    layout = {"generator_version": __version__, "job": job.name, "units": "in", "dpi": DPI_TARGET,
              "gap_in": job.gap_in, "margin_in": job.margin_in, "rotate": job.rotate, "mirrored": False,
              "vendor_checked": str(data.get("checked")), "sheets": []}
    rows = []
    pdf_ready = want_pdf
    if want_pdf:
        try:
            import reportlab  # noqa: F401
        except ImportError:
            pdf_ready = False
            warnings.append('PDF sheets skipped: install the print extra with pip install ".[print]".')
    for index, sheet in enumerate(sheets, 1):
        suffix = "" if len(sheets) == 1 else f"-{index}"
        stem = f"sheet-{sheet.width_in:g}x{sheet.length_in:g}{suffix}"
        render_sheet_png(sheet, folder / f"{stem}.png", DPI_TARGET, cache)
        warning = upload_warning((folder / f"{stem}.png").stat().st_size, max_mb)
        if warning:
            warnings.append(f"{stem}.png: {warning}")
        if pdf_ready:
            render_sheet_pdf(sheet, folder / f"{stem}.pdf", f"Gang sheet {job.name} {index}")
            warning = upload_warning((folder / f"{stem}.pdf").stat().st_size, max_mb)
            if warning:
                warnings.append(f"{stem}.pdf: {warning}")
        layout["sheets"].append({
            "index": index, "width_in": sheet.width_in, "length_in": sheet.length_in,
            "length_ft": round(sheet.length_in / 12, 3), "used_length_in": sheet.used_in,
            "utilization": round(sheet.utilization, 4), "png": f"{stem}.png", "pdf": f"{stem}.pdf" if pdf_ready else None,
            "items": [{"item": p.key, "design": p.design, "file": p.file.name, "copy": p.copy, "x_in": p.x_in,
                       "y_in": p.y_in, "width_in": p.width_in, "height_in": p.height_in, "rotated": p.rotated}
                      for p in sheet.placements]})
        rows.extend({"sheet": index, "item": p.key, "design": p.design, "file": p.file.name, "copy": p.copy,
                     "width_in": f"{p.width_in:.2f}", "height_in": f"{p.height_in:.2f}", "x_in": f"{p.x_in:.2f}",
                     "y_in": f"{p.y_in:.2f}", "rotated": "yes" if p.rotated else "no"} for p in sheet.placements)
    with (folder / "cut-list.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CUT_LIST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    write_preview(sheets, folder / "preview.png")
    if job.prices:
        tiers = (data.get("bulk_discounts") or {}).get("tiers", [])
        layout["cost_compare"] = cost_compare([round(s.length_in / 12, 3) for s in sheets], job.items, job.prices, tiers)
    layout["warnings"] = warnings
    layout["files"] = []
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.name != "layout.json":
            layout["files"].append({"path": path.relative_to(folder).as_posix(), "bytes": path.stat().st_size,
                                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (folder / "layout.json").write_text(json.dumps(layout, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return folder, layout, sheets, warnings
