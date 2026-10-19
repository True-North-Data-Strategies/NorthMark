"""Kit-level checks that need options the command line does not expose yet."""

from pathlib import Path
import tempfile
import unittest

from PIL import Image

from logo_sizes.kit import BuildOptions, generate_kit
from logo_sizes.presets import Preset


class SizeReportingTests(unittest.TestCase):
    def test_file_sizes_are_recorded_and_caps_produce_warnings_not_failures(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "demo.png"
            Image.effect_noise((300, 300), 80).convert("RGBA").save(source)
            image = Image.open(source).convert("RGBA")
            presets = (Preset("capped", 300, 300, "custom", "Custom export", max_kb=1),
                       Preset("free", 20, 20, "custom", "Custom export"))
            options = BuildOptions(presets, icons=False, preview=False, archive=False, padding=0)
            work = root / "work"
            work.mkdir()
            result = generate_kit(source, image, False, "demo", work, options, [])
            self.assertTrue((result.folder / "original" / "capped.png").is_file())
            self.assertEqual(len(result.warnings), 1)
            self.assertIn("capped.png", result.warnings[0])
            self.assertIn("1 KB", result.warnings[0])
            sizes = {entry["path"]: entry for entry in result.manifest["files"]}
            self.assertGreater(sizes["original/capped.png"]["bytes"], 1024)
            self.assertEqual(sizes["original/capped.png"]["width"], 300)
            self.assertEqual(sizes["original/capped.png"]["variant"], "original")
            self.assertEqual(sizes["original/capped.png"]["preset"], "capped")


if __name__ == "__main__":
    unittest.main()
