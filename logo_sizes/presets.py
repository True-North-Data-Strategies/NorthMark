"""Export sizes from the platform presets data file; convenient sizes, not upload guarantees."""

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
import re

import yaml


MAX_SIDE = 8192
MAX_PIXELS = 32_000_000
PRESETS_FILE = "platform-presets.yaml"


@dataclass(frozen=True)
class Preset:
    name: str
    width: int
    height: int
    group: str
    purpose: str
    max_kb: int | None = None
    safe_area: tuple | None = None
    background: bool = False
    standard: bool = True


def load_platform_presets():
    """The raw presets document, including each entry's source and checked date."""
    with resources.as_file(resources.files("logo_sizes") / "data" / PRESETS_FILE) as path:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("presets"), list):
        raise ValueError(f"{PRESETS_FILE} must contain a 'presets' list.")
    return data


def _preset_from_entry(entry):
    safe = entry.get("safe_area")
    return Preset(str(entry["name"]), int(entry["width"]), int(entry["height"]), str(entry["group"]),
                  str(entry.get("purpose", "")), entry.get("max_kb"),
                  (int(safe[0]), int(safe[1])) if safe else None, bool(entry.get("background", False)),
                  bool(entry.get("standard", True)))


PRESETS = tuple(_preset_from_entry(entry) for entry in load_platform_presets()["presets"])
STANDARD_PRESETS = tuple(p for p in PRESETS if p.standard)
GROUPS = tuple(sorted({p.group for p in PRESETS}))
VARIANTS = ("original", "white", "black", "grayscale", "inverted")


def preset_named(name):
    for preset in PRESETS:
        if preset.name == name:
            return preset
    raise ValueError(f"Unknown preset '{name}'. Use --list to see the available names.")


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
    stem = Path(filename).stem.lower().replace("'", "").replace("’", "")
    slug = re.sub(r"[^a-z0-9]+", "-", stem).strip("-") or "logo"
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                *(f"lpt{i}" for i in range(1, 10))}
    return "logo-" + slug if slug in reserved else slug
