"""Image preparation, alpha-safe variants and optional local SVG rendering."""

from io import BytesIO
import math
import re
import warnings

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageOps

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


def _svg_image(path, render_size):
    try:
        import cairosvg
        from defusedxml import ElementTree
    except (ImportError, OSError) as exc:
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
               "radialGradient", "stop", "title", "desc", "text", "tspan"}
    if root.tag != "{http://www.w3.org/2000/svg}svg":
        raise ValueError("Source must be a plain SVG document with the SVG namespace.")
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] not in allowed:
            raise ValueError("Unsupported SVG element. Export a plain vector SVG with inline attributes.")
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
    scale = render_size / max(width, height)
    out_width, out_height = max(1, round(width * scale)), max(1, round(height * scale))
    png = cairosvg.svg2png(bytestring=data, unsafe=False,
                          output_width=out_width, output_height=out_height)
    with Image.open(BytesIO(png)) as image:
        return image.convert("RGBA")


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


def remove_background(image, color, tolerance=0, mode="edge"):
    difference = ImageChops.difference(image.convert("RGB"), Image.new("RGB", image.size, color[:3]))
    red, green, blue = difference.split()
    distance = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    matching = distance.point(lambda v: 255 if v <= tolerance else 0)
    if mode == "edge":
        connected = ImageOps.expand(matching, border=1, fill=255)
        ImageDraw.floodfill(connected, (0, 0), 128)
        connected = connected.crop((1, 1, image.width + 1, image.height + 1))
        keep = connected.point(lambda v: 0 if v == 128 else 255)
    else:
        keep = ImageOps.invert(matching)
    result = image.copy()
    result.putalpha(ImageChops.multiply(image.getchannel("A"), keep))
    if result.getchannel("A").getbbox() is None:
        raise ValueError("Background removal removed all artwork. Check the chosen color and tolerance.")
    return result


def make_variant(image, name):
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
