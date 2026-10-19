"""Brand configuration loading and validation with generic sample data."""

from pathlib import Path
import tempfile
import textwrap
import unittest

from logo_sizes.config import ConfigError, load_brand, resolve_color


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "brand.example.yaml"


class BrandConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, text, name="brand.yaml"):
        path = self.root / name
        path.write_text(textwrap.dedent(text), encoding="utf-8")
        return path

    def test_shipped_example_loads_and_resolves_colors(self):
        brand = load_brand(EXAMPLE)
        self.assertEqual(brand.slug, "example-brand")
        self.assertIn("reverse", brand.variants)
        self.assertEqual(brand.maps["reverse"][0]["from"], (15, 35, 64))
        self.assertIsNone(brand.maps["reverse"][1]["to"])
        self.assertTrue(any(p.name == "header" for p in brand.presets))
        self.assertTrue(any(p.group == "web" for p in brand.presets))
        self.assertEqual(brand.sources["primary"].name, "example-primary.png")
        self.assertTrue(brand.sources["primary"].is_absolute())

    def test_relative_sources_resolve_against_the_config_folder(self):
        (self.root / "art").mkdir()
        path = self.write("""
            brand: Sample
            sources: {primary: art/mark.png}
        """)
        brand = load_brand(path)
        self.assertEqual(brand.sources["primary"], (self.root / "art" / "mark.png").resolve())
        self.assertEqual(brand.slug, "sample")
        self.assertEqual(brand.variants, ("original",))

    def test_unknown_keys_are_rejected(self):
        path = self.write("""
            brand: Sample
            sources: {primary: mark.png}
            colour_scheme: dark
        """)
        with self.assertRaises(ConfigError) as caught:
            load_brand(path)
        self.assertIn("colour_scheme", str(caught.exception))

    def test_primary_source_is_required(self):
        path = self.write("""
            brand: Sample
            sources: {symbol: mark.png}
        """)
        with self.assertRaises(ConfigError):
            load_brand(path)

    def test_named_colors_resolve_in_maps_and_variants_follow(self):
        path = self.write("""
            brand: Sample
            sources: {primary: mark.png}
            colors: {ink: "#0f2340", paper: "#faf6ee"}
            maps:
              reverse:
                - {from: ink, to: "#ffffff", tolerance: 20}
                - {from: paper, to: transparent}
            variants: [original, reverse]
        """)
        brand = load_brand(path)
        self.assertEqual(brand.maps["reverse"][0], {"from": (15, 35, 64), "to": (255, 255, 255),
                                                    "tolerance": 20, "feather": 0})
        self.assertEqual(brand.maps["reverse"][1]["from"], (250, 246, 238))

    def test_variant_without_a_map_or_standard_name_is_rejected(self):
        path = self.write("""
            brand: Sample
            sources: {primary: mark.png}
            variants: [original, mystery]
        """)
        with self.assertRaises(ConfigError):
            load_brand(path)

    def test_unsafe_yaml_tags_are_rejected(self):
        path = self.write("""
            brand: !!python/object/apply:os.system ["echo hi"]
            sources: {primary: mark.png}
        """)
        with self.assertRaises(ConfigError):
            load_brand(path)

    def test_document_must_be_a_mapping(self):
        with self.assertRaises(ConfigError):
            load_brand(self.write("- just\n- a list\n"))

    def test_background_and_trim_settings_are_validated(self):
        path = self.write("""
            brand: Sample
            sources: {primary: mark.png}
            background: {color: auto, mode: edge, feather: 200}
            trim: {enabled: true, threshold: 8}
        """)
        brand = load_brand(path)
        self.assertEqual(brand.background["color"], "auto")
        self.assertEqual(brand.background["feather"], 200)
        self.assertEqual(brand.trim, 8)
        bad = self.write("""
            brand: Sample
            sources: {primary: mark.png}
            background: {color: auto, mode: sideways}
        """, "bad.yaml")
        with self.assertRaises(ConfigError):
            load_brand(bad)

    def test_resolve_color_accepts_names_hex_and_transparent(self):
        colors = {"ink": "#0f2340"}
        self.assertEqual(resolve_color("ink", colors), (15, 35, 64))
        self.assertEqual(resolve_color("#ffffff", colors), (255, 255, 255))
        self.assertIsNone(resolve_color("transparent", colors))
        with self.assertRaises(ConfigError):
            resolve_color("not-a-color", colors)


if __name__ == "__main__":
    unittest.main()


class ReviewFindingTests(BrandConfigTests):
    """Hardening from the code review: safe names, list colors and resolved web colors."""

    def test_map_names_must_be_safe_single_components(self):
        for name in ("../escape", "/abs", "masters", "web", "print", "app-icons", "Reverse Dark"):
            with self.subTest(name=name):
                path = self.write(f"""
                    brand: Sample
                    sources: {{primary: mark.png}}
                    maps:
                      "{name}":
                        - {{from: "#0f2340", to: "#ffffff"}}
                """, "map.yaml")
                with self.assertRaises(ConfigError):
                    load_brand(path)

    def test_uvdtf_size_names_must_be_safe_single_components(self):
        for name in ("../x", "/abs", "sticker 4x6", ".."):
            with self.subTest(name=name):
                path = self.write(f"""
                    brand: Sample
                    sources: {{primary: mark.png}}
                    uvdtf:
                      sizes:
                        - {{name: "{name}", width_in: 4, height_in: 6}}
                """, "uv.yaml")
                with self.assertRaises(ConfigError):
                    load_brand(path)

    def test_named_rgb_list_colors_resolve_in_maps(self):
        path = self.write("""
            brand: Sample
            sources: {primary: mark.png}
            colors: {ink: [15, 35, 64]}
            maps: {reverse: [{from: ink, to: "#ffffff"}]}
            variants: [reverse]
        """)
        self.assertEqual(load_brand(path).maps["reverse"][0]["from"], (15, 35, 64))

    def test_web_colors_are_stored_resolved(self):
        path = self.write("""
            brand: Sample
            sources: {primary: mark.png}
            colors: {ink: "#112233"}
            web: {name: Sample, theme_color: ink, background_color: white}
        """)
        brand = load_brand(path)
        self.assertEqual(brand.web["theme_color"], "#112233")
        self.assertEqual(brand.web["background_color"], "#ffffff")
