"""Brand configuration: one YAML file per brand, validated before any artwork is read."""

from dataclasses import dataclass, field
import math
from pathlib import Path

from PIL import ImageColor
import yaml

from .presets import GROUPS, PRESETS, STANDARD_PRESETS, VARIANTS, parse_size, preset_named, slugify


class ConfigError(ValueError):
    """A configuration file is unreadable, malformed or names something unknown."""


TOP_LEVEL_KEYS = {"brand", "slug", "sources", "colors", "background", "trim", "padding", "variants",
                  "maps", "sizes", "formats", "icon_background", "banner_background", "web", "dtf", "uvdtf"}
SOURCE_ROLES = ("primary", "symbol", "horizontal")
BACKGROUND_KEYS = {"color", "mode", "tolerance", "feather"}
WEB_KEYS = {"name", "short_name", "theme_color", "background_color"}
DTF_KEYS = {"audience", "placements", "variants", "garments", "symbol_for", "overrides", "product"}
UVDTF_KEYS = {"sizes", "variants"}


@dataclass
class BrandConfig:
    path: Path
    name: str
    slug: str
    sources: dict
    colors: dict = field(default_factory=dict)
    background: dict | None = None
    trim: int | None = None
    padding: float = 0.08
    variants: tuple = ("original",)
    maps: dict = field(default_factory=dict)
    presets: tuple = STANDARD_PRESETS
    formats: tuple = ("png",)
    icon_background: tuple | None = None
    banner_background: tuple | None = None
    web: dict = field(default_factory=dict)
    dtf: dict = field(default_factory=dict)
    uvdtf: dict = field(default_factory=dict)


def load_yaml(path):
    """Parse a YAML file with the safe loader; the document must be a mapping."""
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError, UnicodeError) as exc:
        raise ConfigError(f"Cannot read {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name} must contain a YAML mapping of settings.")
    return data


def resolve_color(value, colors=None):
    """Return an RGB tuple, or None for 'transparent'. Named colors come from ``colors``."""
    colors = colors or {}
    if value is None:
        return None
    if isinstance(value, str):
        if value.strip().lower() == "transparent":
            return None
        if value in colors:
            value = colors[value]
        try:
            return ImageColor.getcolor(str(value), "RGB")
        except ValueError as exc:
            raise ConfigError(f"Unrecognized color: {value}") from exc
    if isinstance(value, (list, tuple)) and len(value) in (3, 4) and all(isinstance(v, int) for v in value):
        return tuple(int(v) for v in value[:3])
    raise ConfigError(f"Unrecognized color: {value!r}")


def _expect(condition, message):
    if not condition:
        raise ConfigError(message)


def _check_keys(section, allowed, where):
    _expect(isinstance(section, dict), f"{where} must be a mapping.")
    unknown = sorted(set(section) - allowed)
    _expect(not unknown, f"Unknown setting(s) in {where}: {', '.join(unknown)}. Allowed: {', '.join(sorted(allowed))}.")


def _int_in_range(value, low, high, where):
    _expect(isinstance(value, int) and not isinstance(value, bool) and low <= value <= high,
            f"{where} must be a whole number from {low} to {high}.")
    return value


def _string_list(value, where):
    _expect(isinstance(value, list) and all(isinstance(v, str) for v in value), f"{where} must be a list of names.")
    return value


def _sizes(section):
    if section is None:
        return STANDARD_PRESETS
    _check_keys(section, {"groups", "presets", "custom"}, "sizes")
    chosen = []
    groups = _string_list(section.get("groups", []), "sizes.groups")
    for group in groups:
        _expect(group in GROUPS, f"Unknown size group: {group}. Choose from {', '.join(GROUPS)}.")
    chosen.extend(p for p in PRESETS if p.group in groups)
    for name in _string_list(section.get("presets", []), "sizes.presets"):
        try:
            chosen.append(preset_named(name))
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
    for custom in _string_list(section.get("custom", []), "sizes.custom"):
        try:
            chosen.append(parse_size(custom))
        except ValueError as exc:
            raise ConfigError(f"sizes.custom: {exc}") from exc
    _expect(chosen, "sizes selects nothing. Add groups, presets or custom sizes, or remove the block.")
    _expect(len({p.name for p in chosen}) == len(chosen), "sizes lists the same name twice.")
    return tuple(chosen)


def _maps(section, colors):
    maps = {}
    _expect(isinstance(section, dict), "maps must be a mapping of variant names to entry lists.")
    for name, entries in section.items():
        _expect(isinstance(name, str) and name not in VARIANTS, f"Map name '{name}' clashes with a standard variant.")
        _expect(isinstance(entries, list) and entries, f"maps.{name} must be a non-empty list.")
        resolved = []
        for entry in entries:
            _check_keys(entry, {"from", "to", "tolerance", "feather"}, f"maps.{name}")
            _expect("from" in entry, f"maps.{name}: every entry needs a 'from' color.")
            source = resolve_color(entry["from"], colors)
            _expect(source is not None, f"maps.{name}: 'from' cannot be transparent.")
            resolved.append({"from": source, "to": resolve_color(entry.get("to"), colors),
                             "tolerance": _int_in_range(entry.get("tolerance", 0), 0, 255, f"maps.{name}.tolerance"),
                             "feather": _int_in_range(entry.get("feather", 0), 0, 255, f"maps.{name}.feather")})
        maps[name] = resolved
    return maps


def _background(section, colors):
    if section is None:
        return None
    _check_keys(section, BACKGROUND_KEYS, "background")
    _expect("color" in section, "background needs a color, or 'auto'.")
    color = section["color"]
    if not (isinstance(color, str) and color.lower() == "auto"):
        rgb = resolve_color(color, colors)
        _expect(rgb is not None, "background.color cannot be transparent.")
        color = "#%02x%02x%02x" % rgb
    else:
        color = "auto"
    mode = section.get("mode", "edge")
    _expect(mode in ("edge", "all"), "background.mode must be edge or all.")
    return {"color": color, "mode": mode,
            "tolerance": _int_in_range(section.get("tolerance", 0), 0, 255, "background.tolerance"),
            "feather": _int_in_range(section.get("feather", 0), 0, 255, "background.feather")}


def _trim(section):
    if section is None or section is False:
        return None
    if section is True:
        return 8
    _check_keys(section, {"enabled", "threshold"}, "trim")
    if not section.get("enabled", True):
        return None
    return _int_in_range(section.get("threshold", 8), 0, 255, "trim.threshold")


def _dtf(section):
    if section is None:
        return {}
    _check_keys(section, DTF_KEYS, "dtf")
    for key in ("placements", "variants", "garments", "symbol_for"):
        if key in section:
            _string_list(section[key], f"dtf.{key}")
    if "audience" in section:
        _expect(isinstance(section["audience"], str), "dtf.audience must be a name.")
    overrides = section.get("overrides", {})
    _expect(isinstance(overrides, dict), "dtf.overrides must map placement names to sizes.")
    for name, box in overrides.items():
        _check_keys(box, {"width_in", "height_in"}, f"dtf.overrides.{name}")
        for side in ("width_in", "height_in"):
            value = box.get(side)
            _expect(isinstance(value, (int, float)) and not isinstance(value, bool) and 0 < value <= 60,
                    f"dtf.overrides.{name}.{side} must be a positive number of inches up to 60.")
    return section


def _uvdtf(section):
    if section is None:
        return {}
    _check_keys(section, UVDTF_KEYS, "uvdtf")
    sizes = section.get("sizes", [])
    _expect(isinstance(sizes, list), "uvdtf.sizes must be a list.")
    for entry in sizes:
        _check_keys(entry, {"name", "width_in", "height_in"}, "uvdtf.sizes")
        _expect(isinstance(entry.get("name"), str) and entry["name"], "uvdtf.sizes entries need a name.")
        for side in ("width_in", "height_in"):
            value = entry.get(side)
            _expect(isinstance(value, (int, float)) and not isinstance(value, bool) and 0 < value <= 60,
                    f"uvdtf.sizes.{entry['name']}.{side} must be a positive number of inches up to 60.")
    if "variants" in section:
        _string_list(section["variants"], "uvdtf.variants")
    return section


def load_brand(path):
    """Load and validate a brand configuration. Source files are checked later, at plan time."""
    path = Path(path).resolve()
    data = load_yaml(path)
    _check_keys(data, TOP_LEVEL_KEYS, path.name)
    name = data.get("brand")
    _expect(isinstance(name, str) and name.strip(), "brand must be a non-empty name.")
    slug = data.get("slug", slugify(name))
    _expect(isinstance(slug, str) and slug == slugify(slug), "slug must be lowercase letters, digits and hyphens.")
    sources_section = data.get("sources")
    _check_keys(sources_section or {}, set(SOURCE_ROLES), "sources")
    _expect(sources_section and "primary" in sources_section, "sources.primary is required.")
    sources = {}
    for role, value in sources_section.items():
        _expect(isinstance(value, str) and value.strip(), f"sources.{role} must be a file path.")
        sources[role] = (path.parent / Path(value).expanduser()).resolve()
    colors = data.get("colors", {}) or {}
    _expect(isinstance(colors, dict) and all(isinstance(k, str) for k in colors), "colors must map names to colors.")
    for key, value in colors.items():
        _expect(resolve_color(value) is not None, f"colors.{key} cannot be transparent.")
    maps = _maps(data.get("maps", {}) or {}, colors)
    variants = tuple(dict.fromkeys(_string_list(data.get("variants", ["original"]), "variants")))
    for variant in variants:
        _expect(variant in VARIANTS or variant in maps,
                f"Unknown variant '{variant}'. Use {', '.join(VARIANTS)} or a name from maps.")
    padding = data.get("padding", 0.08)
    _expect(isinstance(padding, (int, float)) and not isinstance(padding, bool) and math.isfinite(padding)
            and 0 <= padding < 0.5, "padding must be a fraction from 0 to below 0.5.")
    formats = tuple(dict.fromkeys(_string_list(data.get("formats", ["png"]), "formats")))
    _expect(formats and set(formats) <= {"png", "webp"}, "formats may only contain png and webp.")
    icon_background = resolve_color(data.get("icon_background"), colors)
    _expect("icon_background" not in data or icon_background is not None, "icon_background must be an opaque color.")
    banner_background = resolve_color(data.get("banner_background"), colors)
    _expect("banner_background" not in data or banner_background is not None, "banner_background must be an opaque color.")
    web = data.get("web", {}) or {}
    _check_keys(web, WEB_KEYS, "web")
    for key, value in web.items():
        _expect(isinstance(value, str) and value.strip(), f"web.{key} must be text.")
        if key.endswith("_color"):
            resolve_color(value, colors)
    return BrandConfig(path, name.strip(), slug, sources, colors, _background(data.get("background"), colors),
                       _trim(data.get("trim")), float(padding), variants, maps, _sizes(data.get("sizes")),
                       formats, icon_background, banner_background, web, _dtf(data.get("dtf")), _uvdtf(data.get("uvdtf")))
