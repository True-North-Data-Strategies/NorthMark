"""Image preparation, alpha-safe variants and optional local SVG rendering."""

from dataclasses import dataclass
from io import BytesIO
import math
import re
import warnings

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFilter, ImageMath, ImageOps

from .presets import MAX_PIXELS


SOURCE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".svg"}


def opaque_color(value):
    try:
        color = ImageColor.getcolor(value, "RGBA")
    except ValueError as exc:
        raise ValueError(f"Unrecognized color: {value}") from exc
    if color[3] != 255:
        raise ValueError("Choose an opaque background color, such as #ffffff.")
    return color


STYLE_FORBIDDEN = ("@", "url(", "/*", "*/", "\\", "<", "&", "expression(", "javascript", "-moz-binding", "behavior")


def _check_style_text(text):
    lowered = (text or "").lower()
    if any(token in lowered for token in STYLE_FORBIDDEN):
        raise ValueError("SVG style blocks may only contain plain fill, stroke and font rules; imports, url() and comments are not supported.")


def _validated_svg(path):
    """Return the SVG bytes and its width and height after the safety checks."""
    try:
        from defusedxml import ElementTree
    except ImportError as exc:
        raise ValueError('SVG support needs CairoSVG and Cairo. Install with: pip install ".[svg]". See README for system setup.') from exc
    data = path.read_bytes()
    if len(data) > 5_000_000:
        raise ValueError("SVG source exceeds the 5 MB limit.")
    # Plain, self-contained vector SVGs only. No network, local file reads,
    # embedded raster images, CSS imports, scripts, entities or active content.
    if b"<?xml-stylesheet" in data.lower():
        raise ValueError("External SVG stylesheets are not supported. Export a plain SVG.")
    root = ElementTree.fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    allowed = {"svg", "g", "defs", "path", "rect", "circle", "ellipse", "line", "polyline",
               "polygon", "use", "symbol", "clipPath", "mask", "linearGradient",
               "radialGradient", "stop", "title", "desc", "text", "tspan", "style"}
    if root.tag != "{http://www.w3.org/2000/svg}svg":
        raise ValueError("Source must be a plain SVG document with the SVG namespace.")
    for element in root.iter():
        local_tag = element.tag.rsplit("}", 1)[-1]
        if local_tag not in allowed:
            raise ValueError("Unsupported SVG element. Export a plain vector SVG with inline attributes.")
        if local_tag == "style":
            _check_style_text(element.text)
        for key, value in element.attrib.items():
            local = key.rsplit("}", 1)[-1].lower()
            if local.startswith("on") or (local == "href" and not value.startswith("#")):
                raise ValueError("SVG external resources and active content are not supported.")
            if any(token in value for token in ("\\", "@", "/*", "*/")):
                raise ValueError("SVG CSS escapes, imports and comments are not supported.")
            cleaned = re.sub(r"url\(\s*['\"]?#[a-zA-Z0-9_.:-]+['\"]?\s*\)", "", value, flags=re.I)
            if re.search(r"url\s*\(", cleaned, re.I):
                raise ValueError("SVG external resources are not supported.")
    viewbox = root.get("viewBox", "").replace(",", " ").split()
    try:
        if len(viewbox) == 4:
            _, _, width, height = map(float, viewbox)
        else:
            width = float(root.get("width", "").removesuffix("px"))
            height = float(root.get("height", "").removesuffix("px"))
    except ValueError as exc:
        raise ValueError("SVG needs a viewBox or numeric pixel width and height.") from exc
    if not all(math.isfinite(n) and n > 0 for n in (width, height)):
        raise ValueError("SVG dimensions must be finite and positive.")
    return data, width, height


def _svg_image(path, render_size):
    try:
        import cairosvg
    except (ImportError, OSError) as exc:
        raise ValueError('SVG support needs CairoSVG and Cairo. Install with: pip install ".[svg]". See README for system setup.') from exc
    data, width, height = _validated_svg(path)
    scale = render_size / max(width, height)
    out_width, out_height = max(1, round(width * scale)), max(1, round(height * scale))
    png = cairosvg.svg2png(bytestring=data, unsafe=False,
                          output_width=out_width, output_height=out_height)
    with Image.open(BytesIO(png)) as image:
        return image.convert("RGBA")


def svg_to_pdf(path):
    """Vector PDF bytes for a validated SVG source; the artwork stays vector."""
    try:
        import cairosvg
    except (ImportError, OSError) as exc:
        raise ValueError('Vector PDF output needs CairoSVG and Cairo. Install with: pip install ".[svg]".') from exc
    data, _, _ = _validated_svg(path)
    return cairosvg.svg2pdf(bytestring=data, unsafe=False)


def load_image(path, render_size=2048):
    notes = []
    vector = path.suffix.lower() == ".svg"
    if vector:
        image = _svg_image(path, render_size)
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as source:
                if source.width * source.height > MAX_PIXELS:
                    raise ValueError(f"Source exceeds the {MAX_PIXELS:,} pixel limit.")
                if getattr(source, "n_frames", 1) > 1:
                    notes.append("Animated or multi-page source: only the first frame was used.")
                image = ImageOps.exif_transpose(source).convert("RGBA")
    if image.getchannel("A").getbbox() is None:
        raise ValueError("Source artwork is fully transparent; there is nothing to export.")
    # Do not propagate EXIF, comments or other source metadata into derivatives.
    image.info.clear()
    return image, vector, notes


def _rgb(value):
    if isinstance(value, str):
        return ImageColor.getcolor(value, "RGB")
    return tuple(int(v) for v in value[:3])


def _distance_to_color(image, color):
    """Largest per-channel difference between each pixel and a flat color, 0 to 255."""
    flat = Image.new("RGB", image.size, _rgb(color))
    red, green, blue = ImageChops.difference(image.convert("RGB"), flat).split()
    return ImageChops.lighter(ImageChops.lighter(red, green), blue)


def _ramp(distance, inner, feather):
    """255 where a pixel fully matches, 0 where it clearly does not, linear in between."""
    if feather <= 0:
        return distance.point(lambda v: 255 if v <= inner else 0)
    table = [255 if v <= inner else 0 if v >= inner + feather
             else round(255 * (1 - (v - inner) / feather)) for v in range(256)]
    return distance.point(table)


def _connected_to_border(mask):
    """Pixels of a 0/255 mask that touch the border through other mask pixels."""
    connected = ImageOps.expand(mask, border=1, fill=255)
    ImageDraw.floodfill(connected, (0, 0), 128)
    connected = connected.crop((1, 1, mask.width + 1, mask.height + 1))
    return connected.point(lambda v: 255 if v == 128 else 0)


def _decontaminate(image, color, keep):
    """Remove the background color's contribution from partially kept edge pixels."""
    background = _rgb(color)
    channels = []
    for channel, flat in zip(image.convert("RGB").split(), background):
        cleaned = ImageMath.lambda_eval(
            lambda a, flat=flat: a["convert"](
                a["max"](a["min"]((a["c"] * 255 - flat * (255 - a["k"])) / a["max"](a["k"], 1), 255), 0), "L"),
            c=channel.convert("F"), k=keep.convert("F"))
        channels.append(cleaned)
    cleaned = Image.merge("RGB", channels)
    # Fully removed pixels keep their original color; only partial pixels change.
    partial = keep.point(lambda v: 255 if v else 0)
    return Image.composite(cleaned, image.convert("RGB"), partial)


def remove_background(image, color, tolerance=0, mode="edge", feather=0):
    """Make a flat background color transparent.

    Pixels within ``tolerance`` of the color are removed. With ``feather`` above
    zero the alpha ramps over the next ``feather`` levels of difference and the
    background color is subtracted from those edge pixels, so anti-aliased edges
    carry no halo onto a dark surface. ``edge`` mode only removes regions that
    touch the image border; ``all`` removes every matching pixel.
    """
    distance = _distance_to_color(image, color)
    amount = _ramp(distance, tolerance, feather)
    if mode == "edge":
        core = amount.point(lambda v: 255 if v >= 128 else 0)
        region = _connected_to_border(core)
        if feather > 0:
            # Anti-aliased edges extend a few pixels past the mostly-background core.
            region = region.filter(ImageFilter.MaxFilter(7))
        amount = ImageChops.multiply(amount, region)
    keep = ImageChops.invert(amount)
    if feather > 0:
        result = _decontaminate(image, color, keep).convert("RGBA")
    else:
        result = image.copy()
    result.putalpha(ImageChops.multiply(image.getchannel("A"), keep))
    if result.getchannel("A").getbbox() is None:
        raise ValueError("Background removal removed all artwork. Check the chosen color and tolerance.")
    return result


@dataclass(frozen=True)
class DetectedBackground:
    color: tuple
    tolerance: int
    feather: int
    noise: int


def _percentile(histogram, fraction):
    total = sum(histogram)
    if not total:
        return 0
    running = 0
    for value, count in enumerate(histogram):
        running += count
        if running >= total * fraction:
            return value
    return len(histogram) - 1


def detect_background(image, ring=2):
    """Measure the border color and its noise, and derive matting settings from them."""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    if min(width, height) <= ring * 2:
        raise ValueError("The image is too small to sample a border.")
    inner = Image.new("L", (width - 2 * ring, height - 2 * ring), 0)
    border = Image.new("L", rgba.size, 255)
    border.paste(inner, (ring, ring))
    translucent = rgba.getchannel("A").point(lambda v: 255 if v < 255 else 0)
    if ImageChops.multiply(border, translucent).getbbox():
        raise ValueError("The border is already transparent; there is no flat background to detect.")
    samples = [pixel[:3] for pixel, flag in zip(rgba.getdata(), border.getdata()) if flag]
    color = tuple(sorted(channel)[len(samples) // 2] for channel in zip(*samples))
    deviations = sorted(abs(c - m) for pixel in samples for c, m in zip(pixel, color))
    noise = deviations[min(len(deviations) - 1, int(len(deviations) * 0.99))]
    tolerance = min(64, noise + 2)
    distance = _distance_to_color(rgba, color)
    histogram = distance.histogram()
    art = [0] * (tolerance + 9) + histogram[tolerance + 9:]
    if not sum(art):
        raise ValueError("No artwork differs from the border color; nothing would remain.")
    contrast = _percentile(art, 0.2)
    feather = max(8, min(200, contrast - tolerance))
    return DetectedBackground(color, tolerance, feather, noise)


def color_map(image, entries):
    """Recolor or clear chosen colors.

    Each entry has ``from`` (a color), ``to`` (a color, or None for transparent),
    an optional ``tolerance`` and an optional ``feather`` ramp. Matching uses the
    source colors, so entries never see each other's results.
    """
    rgba = image.convert("RGBA")
    amounts = []
    for entry in entries:
        distance = _distance_to_color(rgba, entry["from"])
        amount = _ramp(distance, int(entry.get("tolerance", 0)), int(entry.get("feather", 0)))
        amounts.append((entry, amount))
    rgb = rgba.convert("RGB")
    alpha = rgba.getchannel("A")
    for entry, amount in amounts:
        target = entry.get("to")
        if target is None or (isinstance(target, str) and target.lower() == "transparent"):
            alpha = ImageChops.multiply(alpha, ImageChops.invert(amount))
        else:
            rgb = Image.composite(Image.new("RGB", rgb.size, _rgb(target)), rgb, amount)
    result = rgb.convert("RGBA")
    result.putalpha(alpha)
    if result.getchannel("A").getbbox() is None:
        raise ValueError("The color map removed all artwork.")
    return result


def trim_to_art(image, threshold=0):
    """Crop to the pixels whose alpha exceeds the threshold; returns (image, box)."""
    mask = image.getchannel("A").point(lambda v: 255 if v > threshold else 0)
    box = mask.getbbox()
    if box is None:
        raise ValueError("No artwork above the trim threshold.")
    return image.crop(box), box


def make_variant(image, name, maps=None):
    """Standard variants, or a named color map from the brand configuration."""
    if maps and name in maps:
        return color_map(image, maps[name])
    alpha = image.getchannel("A")
    if name in ("white", "black"):
        if alpha.getextrema()[0] == 255:
            raise ValueError(f"The {name} variant needs a transparent source. Supply one or explicitly use --remove-background COLOR.")
        result = Image.new("RGBA", image.size, "white" if name == "white" else "black")
    elif name == "inverted":
        result = ImageOps.invert(image.convert("RGB")).convert("RGBA")
    elif name == "grayscale":
        result = ImageOps.grayscale(image).convert("RGBA")
    else:
        result = image.copy()
    result.putalpha(alpha)
    return result


def fit_canvas(image, size, padding=0.08, upscale=True, background=None):
    width, height = size
    inner = (max(1, int(width * (1 - 2 * padding))), max(1, int(height * (1 - 2 * padding))))
    scale = min(inner[0] / image.width, inner[1] / image.height)
    if not upscale:
        scale = min(scale, 1)
    fitted = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                          Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.paste(fitted, ((width - fitted.width) // 2, (height - fitted.height) // 2))
    if background is not None:
        opaque = Image.new("RGBA", size, background)
        canvas = Image.alpha_composite(opaque, canvas)
    return canvas
