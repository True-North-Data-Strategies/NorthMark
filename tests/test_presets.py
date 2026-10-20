"""Platform presets come from a data file with sources; the standard set stays the default."""

import unittest

from northmark.presets import PRESETS, STANDARD_PRESETS, load_platform_presets, preset_named


class PlatformPresetTests(unittest.TestCase):
    def test_new_rectangular_presets_carry_sources_and_safe_areas(self):
        data = load_platform_presets()
        self.assertEqual(data["checked"].isoformat(), "2026-10-18")
        banner = preset_named("youtube-banner-2560")
        self.assertEqual((banner.width, banner.height), (2560, 1440))
        self.assertEqual(banner.safe_area, (1546, 423))
        self.assertEqual(banner.max_kb, 6144)
        self.assertTrue(banner.background)
        self.assertFalse(banner.standard)
        self.assertEqual((preset_named("x-header-1500").width, preset_named("x-header-1500").height), (1500, 500))
        self.assertEqual((preset_named("og-image-1200").width, preset_named("og-image-1200").height), (1200, 630))
        covers = [p for p in PRESETS if p.name.startswith("linkedin-cover-")]
        self.assertEqual({(p.width, p.height) for p in covers}, {(1128, 191), (4200, 700)})
        by_name = {entry["name"]: entry for entry in data["presets"]}
        for name in ("youtube-banner-2560", "x-header-1500", "og-image-1200", "linkedin-cover-1128", "linkedin-cover-4200"):
            self.assertIn("source", by_name[name], name)
            self.assertIn("checked", by_name[name], name)
        self.assertIn("note", by_name["linkedin-cover-1128"])

    def test_standard_presets_are_the_original_fifteen(self):
        self.assertEqual(len(STANDARD_PRESETS), 15)
        self.assertTrue(all(p.standard for p in STANDARD_PRESETS))
        self.assertIn("master-2048", {p.name for p in STANDARD_PRESETS})
        with self.assertRaises(ValueError):
            preset_named("nothing-here")


if __name__ == "__main__":
    unittest.main()
