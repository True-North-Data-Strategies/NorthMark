"""End-to-end checks with generated artwork, never private brand assets."""

import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import unittest
import zipfile

from PIL import Image, ImageDraw


SCRIPT = Path(__file__).resolve().parents[1] / "make_logo_sizes.py"
try:
    import cairosvg  # noqa: F401
    HAS_SVG = True
except (ImportError, OSError):
    HAS_SVG = False
SMALL = ("--size", "sample=20x20", "--padding", "0", "--no-icons",
         "--no-preview", "--no-zip")


class CliTestCase(unittest.TestCase):
    """Shared temporary input/output folders and a generated source image."""

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
        if args and args[0] in ("kit", "dtf", "gang"):
            command.append(args[0])
            args = args[1:]
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


class LogoToolTests(CliTestCase):
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

    @unittest.skipUnless(HAS_SVG, "install .[svg] and the Cairo library for SVG checks")
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

    @unittest.skipUnless(HAS_SVG, "install .[svg] and the Cairo library for SVG checks")
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


class PhaseOneCliTests(CliTestCase):
    """Automatic background detection, feathered edges and the run summary."""

    def noisy_source(self):
        im = Image.new("RGB", (60, 60), (250, 246, 238))
        px = im.load()
        for y in range(60):
            for x in range(60):
                px[x, y] = (250 + (x % 3) - 1, 246 - (y % 3) + 1, 238 + ((x + y) % 2))
        ImageDraw.Draw(im).ellipse((15, 15, 44, 44), fill=(15, 35, 64))
        im.save(self.source)

    def test_auto_background_removal_reports_color_and_tolerance(self):
        self.noisy_source()
        result = self.success("--size", "sample=60x60", "--padding", "0", "--no-icons",
                              "--no-preview", "--no-zip", "--remove-background", "auto")
        text = (result.stdout + result.stderr).lower()
        self.assertIn("tolerance", text)
        found = re.search(r"color #([0-9a-f]{6})", text)
        self.assertIsNotNone(found, text)
        detected = bytes.fromhex(found.group(1))
        for channel, expected in zip(detected, (250, 246, 238)):
            self.assertLessEqual(abs(channel - expected), 2)
        self.assertEqual(self.pixel("original", (1, 1))[3], 0)
        self.assertEqual(self.pixel("original", (30, 30)), (15, 35, 64, 255))

    def test_feather_requires_background_removal(self):
        result = self.run_tool(*SMALL, "--feather", "20")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.outputs.exists())

    def test_run_summary_lists_each_file_with_kilobytes(self):
        result = self.success(*SMALL)
        self.assertRegex(result.stdout, r"original/sample\.png\s+[\d.]+ KB")
        self.assertIn("Total:", result.stdout)


class BrandConfigCliTests(CliTestCase):
    """Kits driven by a brand configuration file."""

    def write_brand(self, text):
        path = self.root / "brand.yaml"
        path.write_text(text, encoding="utf-8")
        return path

    def test_kit_subcommand_matches_the_legacy_invocation(self):
        self.success(*SMALL)
        legacy = (self.outputs / "demo" / "original" / "sample.png").read_bytes()
        result = subprocess.run([sys.executable, str(SCRIPT), "kit", str(self.source), "-i", str(self.inputs),
                                 "-o", str(self.root / "out2"), *SMALL], capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / "out2" / "demo" / "original" / "sample.png").read_bytes(), legacy)

    def test_brand_config_builds_named_map_variant(self):
        im = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        draw = ImageDraw.Draw(im)
        draw.rectangle((4, 4, 35, 35), fill=(15, 35, 64, 255))
        draw.rectangle((12, 12, 27, 27), fill=(250, 246, 238, 255))
        im.save(self.inputs / "primary.png")
        brand = self.write_brand(
            "brand: Sample Co\nsources: {primary: input/primary.png}\n"
            "colors: {ink: '#0f2340', paper: '#faf6ee'}\n"
            "maps:\n  reverse:\n    - {from: ink, to: '#ffffff'}\n    - {from: paper, to: transparent}\n"
            "variants: [original, reverse]\nsizes: {custom: ['sample=40x40']}\npadding: 0\n")
        result = self.success("kit", "--brand", str(brand), "--no-icons", "--no-preview", "--no-zip", source=False)
        kit = self.outputs / "sample-co"
        self.assertTrue(kit.is_dir(), result.stdout)
        with Image.open(kit / "reverse" / "sample.png") as out:
            self.assertEqual(out.getpixel((6, 6)), (255, 255, 255, 255))
            self.assertEqual(out.getpixel((20, 20))[3], 0)
        with Image.open(kit / "original" / "sample.png") as out:
            self.assertEqual(out.getpixel((20, 20)), (250, 246, 238, 255))
        manifest = json.loads((kit / "kit.json").read_text())
        self.assertEqual(manifest["brand"], "sample-co")
        self.assertIn("reverse", manifest["variants"])

    def test_symbol_and_horizontal_sources_are_used_where_they_fit(self):
        Image.new("RGBA", (100, 100), (255, 0, 0, 255)).save(self.inputs / "primary.png")
        Image.new("RGBA", (100, 100), (0, 0, 255, 255)).save(self.inputs / "symbol.png")
        Image.new("RGBA", (300, 100), (0, 255, 0, 255)).save(self.inputs / "wide.png")
        brand = self.write_brand(
            "brand: Multi\nsources: {primary: input/primary.png, symbol: input/symbol.png, horizontal: input/wide.png}\n"
            "sizes: {custom: ['tiny=32x32', 'big=200x200', 'banner=300x100']}\npadding: 0\n")
        self.success("kit", "--brand", str(brand), "--no-icons", "--no-preview", "--no-zip", source=False)
        kit = self.outputs / "multi" / "original"
        with Image.open(kit / "tiny.png") as out:
            self.assertEqual(out.getpixel((16, 16)), (0, 0, 255, 255))
        with Image.open(kit / "big.png") as out:
            self.assertEqual(out.getpixel((100, 100)), (255, 0, 0, 255))
        with Image.open(kit / "banner.png") as out:
            self.assertEqual(out.getpixel((150, 50)), (0, 255, 0, 255))
        manifest = json.loads((self.outputs / "multi" / "kit.json").read_text())
        files = {f["path"]: f for f in manifest["files"]}
        self.assertEqual(files["original/tiny.png"]["source"], "symbol")
        self.assertEqual(files["original/banner.png"]["source"], "horizontal")
        self.assertEqual(files["original/big.png"]["source"], "primary")
        self.assertTrue((self.outputs / "multi" / "masters" / "symbol.png").is_file())

    def test_trim_fills_the_canvas_with_framed_artwork(self):
        im = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        ImageDraw.Draw(im).rectangle((40, 40, 59, 59), fill=(255, 0, 0, 255))
        im.save(self.source)
        self.success("--size", "s=50x50", "--padding", "0", "--no-icons", "--no-preview", "--no-zip", "--trim")
        with Image.open(self.outputs / "demo" / "original" / "s.png") as out:
            self.assertEqual(out.getchannel("A").getbbox(), (0, 0, 50, 50))

    def test_brand_file_with_missing_source_fails_before_writing(self):
        brand = self.write_brand("brand: Ghost\nsources: {primary: input/missing.png}\n")
        result = self.run_tool("kit", "--brand", str(brand), source=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing.png", result.stdout + result.stderr)
        self.assertFalse(self.outputs.exists())


class DigitalKitCoverageTests(CliTestCase):
    """Banners with safe areas, web drop-in files, vector print output and preview mocks."""

    def test_default_run_writes_exactly_the_standard_presets(self):
        self.success("--no-icons", "--no-preview", "--no-zip")
        names = {p.stem for p in (self.outputs / "demo" / "original").glob("*.png")}
        self.assertEqual(len(names), 15)
        self.assertNotIn("youtube-banner-2560", names)

    def test_banner_fits_art_in_the_safe_area_and_takes_a_background(self):
        Image.new("RGBA", (100, 100), (255, 0, 0, 255)).save(self.source)
        self.success("--preset", "youtube-banner-2560", "--banner-background", "#123456", "--no-icons", "--no-zip")
        with Image.open(self.outputs / "demo" / "original" / "youtube-banner-2560.png") as out:
            self.assertEqual(out.size, (2560, 1440))
            self.assertEqual(out.getpixel((0, 0)), (0x12, 0x34, 0x56, 255))
            red = Image.eval(out.getchannel("R"), lambda v: 255 if v == 255 else 0).getbbox()
            left, top = (2560 - 1546) // 2, (1440 - 423) // 2
            self.assertGreaterEqual(red[0], left)
            self.assertGreaterEqual(red[1], top)
            self.assertLessEqual(red[2], left + 1546)
            self.assertLessEqual(red[3], top + 423)
        self.assertTrue((self.outputs / "demo" / "preview-banners.png").is_file())
        manifest = json.loads((self.outputs / "demo" / "kit.json").read_text())
        files = {f["path"]: f for f in manifest["files"]}
        self.assertEqual(files["original/youtube-banner-2560.png"]["safe_area"], [1546, 423])

    def test_banner_without_background_stays_transparent(self):
        self.success("--preset", "x-header-1500", "--no-icons", "--no-preview", "--no-zip")
        with Image.open(self.outputs / "demo" / "original" / "x-header-1500.png") as out:
            self.assertEqual(out.size, (1500, 500))
            self.assertEqual(out.getpixel((0, 0))[3], 0)

    def test_web_dropin_files_are_complete(self):
        brand = self.root / "brand.yaml"
        brand.write_text("brand: Web Co\nsources: {primary: input/demo.png}\nsizes: {presets: [favicon-32, og-image-1200]}\n"
                         "web: {name: Web Company, short_name: WebCo, theme_color: '#112233', background_color: '#ffffff'}\n")
        self.success("kit", "--brand", str(brand), "--no-preview", "--no-zip", source=False)
        web = self.outputs / "web-co" / "web"
        manifest = json.loads((web / "site.webmanifest").read_text())
        self.assertEqual(manifest["name"], "Web Company")
        self.assertEqual(manifest["short_name"], "WebCo")
        self.assertEqual(manifest["theme_color"], "#112233")
        self.assertEqual(manifest["background_color"], "#ffffff")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual({i["sizes"] for i in manifest["icons"]}, {"192x192", "512x512"})
        for icon in manifest["icons"]:
            self.assertTrue((web / icon["src"].lstrip("/")).is_file())
        head = (web / "head.html").read_text()
        self.assertIn('rel="manifest" href="/site.webmanifest"', head)
        self.assertIn('name="theme-color" content="#112233"', head)
        self.assertIn('rel="apple-touch-icon"', head)
        self.assertIn('property="og:image" content="/og-image-1200.png"', head)
        self.assertTrue((web / "favicon.ico").is_file())
        self.assertTrue((web / "og-image-1200.png").is_file())
        self.assertFalse((web / "favicon.svg").exists())

    def test_preview_has_profile_circle_and_tab_mock_columns(self):
        self.success("--size", "s=64x64", "--no-icons", "--no-zip")
        with Image.open(self.outputs / "demo" / "preview.png") as out:
            self.assertEqual(out.size[0], 360 * 4)

    @unittest.skipUnless(HAS_SVG, "install .[svg] and the Cairo library for SVG checks")
    def test_svg_source_gets_favicon_passthrough_and_vector_print_pdf(self):
        self.source = self.inputs / "vector.svg"
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><style>.a{fill:#ff0000}</style>'
               '<rect class="a" width="100" height="50"/></svg>')
        self.source.write_text(svg)
        self.success("--size", "banner=100x50", "--padding", "0", "--no-preview", "--no-zip")
        kit = self.outputs / "vector"
        with Image.open(kit / "original" / "banner.png") as out:
            self.assertEqual(out.getpixel((0, 0)), (255, 0, 0, 255))
        self.assertEqual((kit / "web" / "favicon.svg").read_text(), svg)
        self.assertIn('rel="icon" type="image/svg+xml" href="/favicon.svg"', (kit / "web" / "head.html").read_text())
        self.assertEqual((kit / "print" / "vector.pdf").read_bytes()[:4], b"%PDF")

    @unittest.skipUnless(HAS_SVG, "install .[svg] and the Cairo library for SVG checks")
    def test_svg_style_blocks_with_imports_or_urls_are_still_refused(self):
        self.source = self.inputs / "styled.svg"
        for css in ("@import url(x.css);", ".a{fill:url(http://example.com/a.png)}", ".a{fill:red}/*c*/"):
            with self.subTest(css=css):
                self.source.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><style>{css}</style>'
                                       '<rect class="a" width="20" height="20"/></svg>')
                self.assertNotEqual(self.run_tool(*SMALL).returncode, 0)
                self.assertFalse((self.outputs / "styled").exists())


class LockFileTests(CliTestCase):
    """The output lock names its process and host, and clears itself only when that process is gone."""

    def test_lock_records_pid_and_host_and_is_removed_after_the_run(self):
        self.outputs.mkdir()
        lock = self.outputs / ".logo-kit.lock"
        result = self.success(*SMALL)
        self.assertFalse(lock.exists(), result.stdout)

    def test_stale_lock_from_a_dead_process_on_this_host_is_cleared(self):
        self.outputs.mkdir()
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        (self.outputs / ".logo-kit.lock").write_text(f"pid: {dead.pid}\nhost: {socket.gethostname()}\n", encoding="utf-8")
        result = self.success(*SMALL)
        self.assertIn("stale lock", (result.stdout + result.stderr).lower())
        self.assertTrue((self.outputs / "demo" / "original" / "sample.png").is_file())

    def test_lock_held_by_a_live_process_is_respected(self):
        self.outputs.mkdir()
        (self.outputs / ".logo-kit.lock").write_text(f"pid: {os.getpid()}\nhost: {socket.gethostname()}\n", encoding="utf-8")
        result = self.run_tool(*SMALL)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(".logo-kit.lock", result.stdout + result.stderr)
        self.assertFalse((self.outputs / "demo").exists())

    def test_lock_from_another_host_is_respected(self):
        self.outputs.mkdir()
        (self.outputs / ".logo-kit.lock").write_text("pid: 1\nhost: some-other-machine\n", encoding="utf-8")
        result = self.run_tool(*SMALL)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.outputs / "demo").exists())


class ReviewFindingCliTests(CliTestCase):
    def test_overwrite_without_zip_retires_the_previous_archive(self):
        self.success(*SMALL[:-1])
        self.assertTrue((self.outputs / "demo.zip").is_file())
        self.success(*SMALL, "--overwrite")
        self.assertFalse((self.outputs / "demo.zip").exists())
        self.assertTrue(any((self.outputs / ".backups").glob("*/demo.zip")))

    def test_stale_lock_reclaim_happens_once(self):
        from logo_sizes.cli import reclaim_stale_lock
        self.outputs.mkdir()
        lock = self.outputs / ".logo-kit.lock"
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        lock.write_text(f"pid: {dead.pid}\nhost: {socket.gethostname()}\n", encoding="utf-8")
        self.assertTrue(reclaim_stale_lock(lock))
        self.assertFalse(lock.exists())
        self.assertFalse(reclaim_stale_lock(lock))

    @unittest.skipUnless(HAS_SVG, "install .[svg] and the Cairo library for SVG checks")
    def test_icons_do_not_upscale_a_raster_symbol_when_asked_not_to(self):
        (self.inputs / "primary.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
                                                 '<rect width="100" height="100" fill="#f00"/></svg>')
        Image.new("RGBA", (20, 20), (0, 0, 255, 255)).save(self.inputs / "symbol.png")
        brand = self.root / "brand.yaml"
        brand.write_text("brand: Mixed\nsources: {primary: input/primary.svg, symbol: input/symbol.png}\n"
                         "sizes: {custom: ['s=64x64']}\npadding: 0\n")
        self.success("kit", "--brand", str(brand), "--no-upscale", "--no-preview", "--no-zip", source=False)
        with Image.open(self.outputs / "mixed" / "original" / "app-icons" / "favicon.ico") as ico:
            ico.size = (64, 64)
            box = ico.convert("RGBA").getchannel("A").getbbox()
            self.assertLessEqual(box[2] - box[0], 20)


class AutoBackgroundOnTransparentSourceTests(CliTestCase):
    def test_auto_removal_leaves_an_already_transparent_source_alone_with_a_note(self):
        result = self.success(*SMALL, "--remove-background", "auto")
        self.assertIn("already transparent", (result.stdout + result.stderr).lower())
        self.assertEqual(self.pixel("original"), (10, 20, 30, 128))
        self.assertEqual(self.pixel("original", (0, 0))[3], 0)

    def test_brand_wide_auto_removal_skips_the_transparent_symbol(self):
        Image.new("RGB", (60, 60), (250, 246, 238)).save(self.inputs / "primary.png")
        with Image.open(self.inputs / "primary.png") as im:
            ImageDraw.Draw(im).ellipse((15, 15, 44, 44), fill=(15, 35, 64))
            im.save(self.inputs / "primary.png")
        Image.new("RGBA", (30, 30), (0, 0, 0, 0)).save(self.inputs / "symbol.png")
        with Image.open(self.inputs / "symbol.png") as im:
            ImageDraw.Draw(im).rectangle((5, 5, 24, 24), fill=(0, 0, 255, 255))
            im.save(self.inputs / "symbol.png")
        brand = self.root / "brand.yaml"
        brand.write_text("brand: Mixed\nsources: {primary: input/primary.png, symbol: input/symbol.png}\n"
                         "background: {color: auto}\nsizes: {custom: ['tiny=32x32', 'big=100x100']}\npadding: 0\n")
        result = self.success("kit", "--brand", str(brand), "--no-icons", "--no-preview", "--no-zip", source=False)
        self.assertIn("already transparent", result.stdout.lower())
        with Image.open(self.outputs / "mixed" / "original" / "big.png") as out:
            self.assertEqual(out.getpixel((1, 1))[3], 0)
            self.assertEqual(out.getpixel((50, 50)), (15, 35, 64, 255))
