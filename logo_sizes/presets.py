"""Convenient export sizes, not a promise of platform upload acceptance."""

from dataclasses import dataclass
import re


MAX_SIDE = 8192
MAX_PIXELS = 32_000_000


@dataclass(frozen=True)
class Preset:
    name: str
    width: int
    height: int
    group: str
    purpose: str


PRESETS = (
    Preset("youtube-watermark-150", 150, 150, "youtube", "Video watermark"),
    Preset("youtube-profile-800", 800, 800, "youtube", "Channel profile"),
    Preset("favicon-16", 16, 16, "web", "Tiny browser icon"),
    Preset("favicon-32", 32, 32, "web", "Browser icon"),
    Preset("favicon-180", 180, 180, "web", "Touch icon size"),
    Preset("favicon-192", 192, 192, "web", "Small app icon size"),
    Preset("favicon-512", 512, 512, "web", "Large app icon size"),
    Preset("social-linkedin-400", 400, 400, "social", "Profile image starting size"),
    Preset("social-x-400", 400, 400, "social", "Profile image starting size"),
    Preset("social-facebook-500", 500, 500, "social", "Profile image starting size"),
    Preset("social-instagram-320", 320, 320, "social", "Profile image starting size"),
    Preset("doc-header-600", 600, 600, "docs", "Document logo"),
    Preset("email-signature-200", 200, 200, "docs", "Email logo"),
    Preset("slide-deck-1000", 1000, 1000, "docs", "Presentation logo"),
    Preset("master-2048", 2048, 2048, "master", "Large raster derivative, not original artwork"),
)
GROUPS = tuple(sorted({p.group for p in PRESETS}))
VARIANTS = ("original", "white", "black", "grayscale", "inverted")


def parse_size(value):
    match = re.fullmatch(r"([a-zA-Z0-9][a-zA-Z0-9_-]*)=(\d+)x(\d+)", value)
    if not match:
        raise ValueError("Use --size name=WIDTHxHEIGHT, for example header=1200x300.")
    name, width, height = match.groups()
    width, height = int(width), int(height)
    if not (1 <= width <= MAX_SIDE and 1 <= height <= MAX_SIDE) or width * height > MAX_PIXELS:
        raise ValueError(f"Sizes must be 1 to {MAX_SIDE} pixels per side and at most {MAX_PIXELS:,} pixels.")
    return Preset(name.lower(), width, height, "custom", "Custom export")


def slugify(filename):
    from pathlib import Path
    stem = Path(filename).stem.lower().replace("'", "").replace("\u2019", "")
    slug = re.sub(r"[^a-z0-9]+", "-", stem).strip("-") or "logo"
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                *(f"lpt{i}" for i in range(1, 10))}
    return "logo-" + slug if slug in reserved else slug
