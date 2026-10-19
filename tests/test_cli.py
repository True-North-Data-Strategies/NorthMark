"""End-to-end checks with generated artwork, never private brand assets."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from PIL import Image, ImageDraw


SCRIPT = Path(__file__).resolve().parents[1] / "make_logo_sizes.py"
SMALL = ("--size", "sample=20x20", "--padding", "0", "--no-icons",
         "--no-preview", "--no-zip")


class LogoToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "input"
        self.inputs.mkdir()
        self.outputs = self.root / "output"
        self.source = self.inputs / "demo.png"
        im = Image.new("RGBA", (20, 20), (10, 20, 30, 0))
        ImageDraw.Draw(im).rectangle((5, 5, 14, 14), fill=(10, 20, 30, 128))
        im.save(self.source)

    def run_tool(self, *args, source=True):
        command = [sys.executable, str(SCRIPT)]
        if source:
            command.append(str(self.source))
        command.extend(["-i", str(self.inputs), "-o", str(self.outputs), *args])
        return subprocess.run(command, capture_output=True, text=True,
                              cwd=self.root, timeout=45)

    def success(self, *args, source=True):
        result = self.run_tool(*args, source=source)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def pixel(self, variant, point=(10, 10)):
        with Image.open(self.outputs / "demo" / variant / "sample.png") as im:
            return im.getpixel(point)

    def test_fit_preserves_both_ends_of_wide_artwork(self):
        im = Image.new("RGBA", (100, 50), (0, 255, 0, 255))
        draw = ImageDraw.Draw(im)
        draw.rectangle((0, 0, 9, 49), fill=(255, 0, 0, 255))
        draw.rectangle((90, 0, 99, 49), fill=(0, 0, 255, 255))
        im.save(self.source)
        self.success("--size", "wide=100x100", "--padding", "0", "--no-icons")
        with Image.open(self.outputs / "demo" / "original" / "wide.png") as out:
            self.assertEqual(out.getpixel((0, 50)), (255, 0, 0, 255))
            self.assertEqual(out.getpixel((99, 50)), (0, 0, 255, 255))
            self.assertEqual(out.getpixel((50, 0))[3], 0)

    def test_padding_and_rectangular_sizes(self):
        Image.new("RGBA", (20, 20), (255, 0, 0, 255)).save(self.source)
        self.success("--size", "header=100x50", "--padding", "0.1", "--no-icons")
        with Image.open(self.outputs / "demo" / "original" / "header.png") as out:
            self.assertEqual(out.size, (100, 50))
            self.assertEqual(out.getchannel("A").getbbox(), (30, 5, 70, 45))

    def test_all_variants_keep_alpha_and_have_correct_colors(self):
        self.success(*SMALL, "--variants", "all")
        for variant, expected in {
            "original": (10, 20, 30, 128), "white": (255, 255, 255, 128),
            "black": (0, 0, 0, 128), "grayscale": (18, 18, 18, 128),
            "inverted": (245, 235, 225, 128),
        }.items():
            with self.subTest(variant=variant):
                self.assertEqual(self.pixel(variant), expected)
                self.assertEqual(self.pixel(variant, (0, 0))[3], 0)

    def test_white_variant_refuses_an_opaque_rectangle(self):
        Image.new("RGB", (20, 20), "white").save(self.source)
        result = self.run_tool(*SMALL, "--variants", "white")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("transparent", result.stdout + result.stderr)
        self.assertFalse((self.outputs / "demo").exists())

    def test_edge_background_removal_preserves_enclosed_white_detail(self):
        im = Image.new("RGB", (20, 20), "white")
        draw = ImageDraw.Draw(im)
        draw.rectangle((4, 4, 15, 15), fill="black")
        draw.rectangle((8, 8, 11, 11), fill="white")
        im.save(self.source)
        self.success(*SMALL, "--remove-background", "#ffffff")
        self.assertEqual(self.pixel("original", (0, 0))[3], 0)
        self.assertEqual(self.pixel("original", (10, 10)), (255, 255, 255, 255))

    def test_all_background_removal_is_explicit(self):
        im = Image.new("RGB", (20, 20), "white")
        ImageDraw.Draw(im).rectangle((4, 4, 15, 15), fill="black")
        im.putpixel((10, 10), (255, 255, 255))
        im.save(self.source)
        self.success(*SMALL, "--remove-background", "white",
                     "--background-mode", "all")
        self.assertEqual(self.pixel("original", (10, 10))[3], 0)

    def test_background_tolerance_is_used(self):
        im = Image.new("RGB", (20, 20), (249, 250, 251))
        ImageDraw.Draw(im).rectangle((5, 5, 14, 14), fill="black")
        im.save(self.source)
        self.success(*SMALL, "--remove-background", "white", "--tolerance", "6")
        self.assertEqual(self.pixel("original", (0, 0))[3], 0)
        self.assertEqual(self.pixel("original")[3], 255)

    def test_existing_kit_is_preserved_without_overwrite(self):
        self.success(*SMALL)
        target = self.outputs / "demo" / "original" / "sample.png"
        before = target.read_bytes()
        Image.new("RGBA", (20, 20), "red").save(self.source)
        result = self.run_tool(*SMALL)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_bytes(), before)

    def test_overwrite_keeps_a_complete_backup(self):
        self.success(*SMALL)
        target = self.outputs / "demo" / "original" / "sample.png"
        before = target.read_bytes()
        (self.outputs / "demo" / "my-notes.txt").write_text("keep me")
        Image.new("RGBA", (20, 20), "red").save(self.source)
        self.success(*SMALL, "--overwrite")
        self.assertNotEqual(target.read_bytes(), before)
        backups = list((self.outputs / ".backups").glob("*/demo/original/sample.png"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), before)
        self.assertEqual((backups[0].parents[1] / "my-notes.txt").read_text(), "keep me")

    def test_slug_collisions_refuse_the_whole_batch_before_writing(self):
        Image.new("RGB", (20, 20), "red").save(self.inputs / "demo.jpg")
        result = self.run_tool(*SMALL, source=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("same output", result.stdout + result.stderr)
        self.assertFalse(self.outputs.exists())

    def test_corrupt_source_returns_failure_and_other_sources_finish(self):
        (self.inputs / "broken.png").write_text("not an image")
        result = self.run_tool(*SMALL, source=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.outputs / "demo" / "original" / "sample.png").is_file())
        self.assertFalse((self.outputs / "broken").exists())

    def test_dry_run_writes_nothing(self):
        self.success(*SMALL, "--dry-run")
        self.assertFalse(self.outputs.exists())

    def test_invalid_size_and_padding_write_nothing(self):
        for args in [("--size", "bad=0x100"), ("--padding", "0.5"),
                     ("--size", "../bad=20x20"), ("--padding", "nan"),
                     ("--size", "huge=50000x50000")]:
            with self.subTest(args=args):
                self.assertNotEqual(self.run_tool(*args).returncode, 0)
                self.assertFalse(self.outputs.exists())

    def test_duplicate_custom_names_are_refused(self):
        result = self.run_tool("--size", "same=10x10", "--size", "same=20x20")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.outputs.exists())

    def test_no_upscale_preserves_the_artwork_pixel_dimensions(self):
        Image.new("RGBA", (20, 20), "red").save(self.source)
        self.success("--size", "large=100x100", "--padding", "0",
                     "--no-upscale", "--no-icons")
        with Image.open(self.outputs / "demo" / "original" / "large.png") as im:
            self.assertEqual(im.getchannel("A").getbbox(), (40, 40, 60, 60))

    def test_png_and_webp_exports(self):
        self.success(*SMALL, "--formats", "png", "webp")
        with Image.open(self.outputs / "demo" / "original" / "sample.webp") as out:
            self.assertEqual(out.size, (20, 20))
            self.assertEqual(out.convert("RGBA").getpixel((10, 10)), (10, 20, 30, 128))

    def test_complete_kit_contains_icons_previews_guide_and_exact_source(self):
        source_hash = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.success("--size", "small=32x32", "--variants", "all")
        kit = self.outputs / "demo"
        self.assertTrue((kit / "preview.png").is_file())
        self.assertTrue((kit / "preview.html").is_file())
        self.assertTrue((kit / "GUIDE.txt").is_file())
        self.assertEqual(hashlib.sha256((kit / "masters" / "source.png").read_bytes()).hexdigest(), source_hash)
        with Image.open(kit / "original" / "app-icons" / "favicon.ico") as ico:
            self.assertEqual(ico.ico.sizes(), {(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)})
        app = json.loads((kit / "original" / "app-icons" / "manifest.webmanifest").read_text())
        self.assertEqual({i["sizes"] for i in app["icons"]}, {"192x192", "512x512"})
        for item in app["icons"]:
            self.assertTrue((kit / "original" / "app-icons" / item["src"]).is_file())
        with zipfile.ZipFile(self.outputs / "demo.zip") as archive:
            names = archive.namelist()
            self.assertIn("demo/preview.png", names)
            self.assertIn("demo/GUIDE.txt", names)
            self.assertFalse(any(name.startswith("/") or ".." in name.split("/") for name in names))
            self.assertFalse(any(".backups" in name for name in names))
        manifest = (kit / "kit.json").read_text()
        self.assertNotIn(str(self.root), manifest)

    def test_maskable_icon_has_an_opaque_background_and_safe_artwork(self):
        Image.new("RGBA", (20, 20), "red").save(self.source)
        self.success("--size", "small=20x20", "--icon-background", "#00ff00")
        with Image.open(self.outputs / "demo" / "original" / "app-icons" / "icon-maskable-192.png") as out:
            self.assertEqual(out.getchannel("A").getextrema(), (255, 255))
            self.assertEqual(out.getpixel((0, 0)), (0, 255, 0, 255))
            self.assertEqual(out.getpixel((96, 96)), (255, 0, 0, 255))
            self.assertEqual(out.getpixel((30, 30)), (0, 255, 0, 255))

    def test_transparent_background_cannot_be_used_for_maskable_icons(self):
        result = self.run_tool("--icon-background", "#ffffff00")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.outputs.exists())

    def test_blank_artwork_is_refused(self):
        Image.new("RGBA", (20, 20), (0, 0, 0, 0)).save(self.source)
        self.assertNotEqual(self.run_tool(*SMALL).returncode, 0)
        self.assertFalse((self.outputs / "demo").exists())

    def test_hidden_files_and_non_images_are_ignored(self):
        (self.inputs / ".hidden.png").write_text("ignore")
        (self.inputs / "notes.txt").write_text("ignore")
        self.success(*SMALL, source=False)
        self.assertTrue((self.outputs / "demo").is_dir())

    def test_group_and_preset_selection(self):
        self.success("--preset", "favicon-32", "--no-icons")
        with Image.open(self.outputs / "demo" / "original" / "favicon-32.png") as out:
            self.assertEqual(out.size, (32, 32))
        self.assertFalse((self.outputs / "demo" / "original" / "favicon-16.png").exists())

    def test_empty_input_returns_actionable_failure(self):
        self.source.unlink()
        result = self.run_tool(*SMALL, source=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("input", (result.stdout + result.stderr).lower())

    def test_all_standard_presets_are_written(self):
        self.success("--no-icons", "--no-preview", "--no-zip")
        expected = {"youtube-watermark-150": 150, "youtube-profile-800": 800,
                    "favicon-16": 16, "favicon-32": 32, "favicon-180": 180,
                    "favicon-192": 192, "favicon-512": 512,
                    "social-linkedin-400": 400, "social-x-400": 400,
                    "social-facebook-500": 500, "social-instagram-320": 320,
                    "doc-header-600": 600, "email-signature-200": 200,
                    "slide-deck-1000": 1000, "master-2048": 2048}
        for name, size in expected.items():
            with Image.open(self.outputs / "demo" / "original" / f"{name}.png") as out:
                self.assertEqual(out.size, (size, size))

    @unittest.skipUnless(importlib.util.find_spec("cairosvg"), "install .[svg] for SVG checks")
    def test_vector_source_is_rendered_and_original_is_preserved(self):
        self.source = self.inputs / "vector.svg"
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><rect width="100" height="50" fill="red"/></svg>'
        self.source.write_text(svg)
        self.success("--size", "banner=100x50", "--padding", "0", "--no-icons")
        kit = self.outputs / "vector"
        self.assertEqual((kit / "masters" / "source.svg").read_text(), svg)
        with Image.open(kit / "original" / "banner.png") as out:
            self.assertEqual(out.getpixel((0, 0)), (255, 0, 0, 255))
        self.assertTrue(json.loads((kit / "kit.json").read_text())["vector_source"])

    @unittest.skipUnless(importlib.util.find_spec("cairosvg"), "install .[svg] for SVG checks")
    def test_svg_external_resources_and_entities_are_refused(self):
        self.source = self.inputs / "unsafe.svg"
        for content in [
            '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><image href="file:///etc/passwd"/></svg>',
            '<!DOCTYPE svg [<!ENTITY secret SYSTEM "file:///etc/passwd">]><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><text>&secret;</text></svg>',
            '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><style>@import "https://example.com/a.css";</style></svg>',
        ]:
            with self.subTest(content=content[:50]):
                self.source.write_text(content)
                self.assertNotEqual(self.run_tool(*SMALL).returncode, 0)
                self.assertFalse((self.outputs / "unsafe").exists())


if __name__ == "__main__":
    unittest.main()
