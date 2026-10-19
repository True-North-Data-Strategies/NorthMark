"""DTF transfer outputs: exact sizes, honest DPI, hardened alpha, thin lines and mockups."""

import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

from logo_sizes.dtf import (choose_variants_for_garments, effective_dpi, fit_inches, harden_alpha,
                            load_placements, placement_box, thin_strokes)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "make_logo_sizes.py"
HAS_REPORTLAB = importlib.util.find_spec("reportlab") is not None


class PlacementDataTests(unittest.TestCase):
    def test_placements_file_carries_sources_and_dates(self):
        data = load_placements()
        self.assertEqual(data["checked"].isoformat(), "2026-10-18")
        self.assertIn("placement_guide", data["sources"])
        adult = data["audiences"]["adult"]
        for name in ("left-chest", "center-chest", "full-front", "sleeve", "back-collar",
                     "upper-back", "full-back", "oversize"):
            self.assertIn("average", adult[name])
            self.assertIn("range", adult[name])
            self.assertIn("position", adult[name])
        self.assertEqual(placement_box(data, "adult", "full-back"), (12.0, 14.0))
        self.assertEqual(placement_box(data, "youth", "left-chest"), (2.5, 1.5))
        self.assertEqual(placement_box(data, "adult", "full-back", {"full-back": {"width_in": 11, "height_in": 15.16}}),
                         (11.0, 15.16))
        with self.assertRaises(ValueError):
            placement_box(data, "womens", "sleeve")

    def test_template_headers_match_the_order_sheet(self):
        from logo_sizes.dtf import ORDER_SHEET_COLUMNS
        header = (ROOT / "examples" / "templates" / "order-sheet.csv").read_text().strip().split(",")
        self.assertEqual(header, list(ORDER_SHEET_COLUMNS))


class GeometryTests(unittest.TestCase):
    def test_fit_inches_keeps_aspect_and_rounds_to_hundredths(self):
        self.assertEqual(fit_inches(827, 1140, 12, 14), (10.16, 14.0))
        self.assertEqual(fit_inches(1000, 500, 3.5, 2.0), (3.5, 1.75))

    def test_effective_dpi_verdicts_and_needed_pixels(self):
        verdict = effective_dpi(827, 1140, 10.16, 14.0)
        self.assertEqual(verdict.dpi, 81)
        self.assertEqual(verdict.level, "fail")
        self.assertEqual(verdict.needed, (3048, 4200))
        self.assertEqual(effective_dpi(2000, 2000, 4, 4).level, "ok")
        self.assertEqual(effective_dpi(1000, 1000, 4, 4).level, "warn")


class AlphaTests(unittest.TestCase):
    def soft_disc(self):
        big = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
        ImageDraw.Draw(big).ellipse((40, 40, 359, 359), fill=(20, 40, 80, 255))
        return big.resize((100, 100), Image.Resampling.LANCZOS)

    def test_harden_keeps_at_most_a_one_pixel_soft_edge(self):
        soft = self.soft_disc()
        hardened, remaining = harden_alpha(soft)
        histogram = hardened.getchannel("A").histogram()
        semi_before = sum(soft.getchannel("A").histogram()[1:255])
        self.assertLess(remaining, semi_before)
        self.assertEqual(remaining, sum(histogram[1:255]))
        self.assertEqual(hardened.getpixel((50, 50))[3], 255)
        self.assertEqual(hardened.getpixel((2, 2))[3], 0)
        # Every remaining soft pixel touches a fully transparent neighbour.
        alpha = hardened.getchannel("A")
        for y in range(1, 99):
            for x in range(1, 99):
                value = alpha.getpixel((x, y))
                if 0 < value < 255:
                    neighbours = [alpha.getpixel((x + dx, y + dy)) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
                    self.assertIn(0, neighbours)

    def test_choke_shrinks_the_artwork_by_one_pixel_per_side(self):
        soft = self.soft_disc()
        plain, _ = harden_alpha(soft)
        choked, _ = harden_alpha(soft, choke=1)
        box_plain = plain.getchannel("A").getbbox()
        box_choked = choked.getchannel("A").getbbox()
        self.assertEqual(box_choked[0], box_plain[0] + 1)
        self.assertEqual(box_choked[2], box_plain[2] - 1)

    def test_thin_strokes_are_measured_against_the_minimum(self):
        image = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((10, 10, 59, 59), fill=(0, 0, 0, 255))
        draw.line((70, 10, 70, 110), fill=(0, 0, 0, 255), width=2)
        report = thin_strokes(image, min_px=6)
        self.assertGreater(report.fraction, 0.05)
        self.assertLessEqual(report.thinnest_px, 2)
        block_only = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        ImageDraw.Draw(block_only).rectangle((10, 10, 59, 59), fill=(0, 0, 0, 255))
        self.assertEqual(thin_strokes(block_only, min_px=6).fraction, 0)


class GarmentTests(unittest.TestCase):
    def test_variant_recommendation_prefers_contrast(self):
        navy = Image.new("RGBA", (20, 20), (20, 40, 80, 255))
        white = Image.new("RGBA", (20, 20), (255, 255, 255, 255))
        garments = {"white": (255, 255, 255), "navy": (31, 42, 68)}
        recommendation, flags = choose_variants_for_garments({"original": navy, "white": white}, garments)
        self.assertEqual(recommendation["white"], "original")
        self.assertEqual(recommendation["navy"], "white")
        self.assertIn(("original", "navy"), flags)
        self.assertNotIn(("white", "navy"), flags)


class DtfCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.outputs = self.root / "out"
        self.source = self.root / "demo.png"
        image = Image.new("RGBA", (300, 350), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 149, 349), fill=(200, 30, 30, 255))
        draw.rectangle((150, 0, 299, 349), fill=(30, 30, 200, 255))
        image.save(self.source)

    def run_dtf(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "dtf", *args, "-o", str(self.outputs)],
                              capture_output=True, text=True, cwd=self.root, timeout=120)

    def test_left_chest_output_is_exact_size_at_300_dpi_and_not_mirrored(self):
        result = self.run_dtf(str(self.source), "--placement", "left-chest")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        path = self.outputs / "demo" / "dtf" / "adult" / "left-chest" / "original" / "demo-left-chest-1.71x2.00in.png"
        self.assertTrue(path.is_file(), result.stdout)
        with Image.open(path) as out:
            self.assertEqual(out.size, (513, 600))
            self.assertEqual(tuple(round(v) for v in out.info["dpi"]), (300, 300))
            self.assertEqual(out.getpixel((50, 300))[:3], (200, 30, 30))
            self.assertEqual(out.getpixel((460, 300))[:3], (30, 30, 200))
        self.assertIn("1.71 x 2.00 in", result.stdout)
        self.assertRegex(result.stdout, r"source (DPI|dpi) 175")
        with (self.outputs / "demo" / "dtf" / "order-sheet.csv").open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["width_in"], "1.71")
        self.assertEqual(rows[0]["height_in"], "2.00")
        self.assertEqual(rows[0]["width_px"], "513")
        self.assertEqual(rows[0]["source_dpi"], "175")
        self.assertEqual(rows[0]["qty"], "")
        self.assertTrue((self.outputs / "demo" / "dtf" / "mockups" / "left-chest-original-on-white.png").is_file())
        self.assertTrue((self.outputs / "demo" / "dtf" / "mockups" / "left-chest-original-on-navy.png").is_file())
        card = "press-card.pdf" if HAS_REPORTLAB else "press-card.png"
        self.assertTrue((self.outputs / "demo" / "dtf" / card).is_file())

    def test_low_dpi_output_is_refused_unless_allowed(self):
        Image.new("RGBA", (100, 100), (200, 30, 30, 255)).save(self.source)
        result = self.run_dtf(str(self.source), "--placement", "left-chest")
        self.assertNotEqual(result.returncode, 0)
        folder = self.outputs / "demo" / "dtf" / "adult" / "left-chest" / "original"
        self.assertFalse(folder.exists() and any(folder.iterdir()))
        with (self.outputs / "demo" / "dtf" / "order-sheet.csv").open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["file"], "")
        self.assertIn("50 DPI", rows[0]["warnings"])
        self.assertIn("600x600", rows[0]["warnings"])
        allowed = self.run_dtf(str(self.source), "--placement", "left-chest", "--allow-low-dpi", "--overwrite")
        self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)
        self.assertTrue((folder / "demo-left-chest-2.00x2.00in.png").is_file())
        self.assertIn("enlarged", allowed.stdout.lower())

    def test_brand_file_drives_placements_symbol_variants_and_uvdtf(self):
        Image.new("RGBA", (400, 400), (20, 40, 80, 255)).save(self.root / "symbol.png")
        brand = self.root / "brand.yaml"
        brand.write_text(
            "brand: Sample Co\nsources: {primary: demo.png, symbol: symbol.png}\n"
            "colors: {ink: '#14285'}\n".replace("#14285", "#142850") +
            "maps: {reverse: [{from: ink, to: '#ffffff'}]}\n"
            "variants: [original, reverse]\n"
            "dtf: {placements: [left-chest], variants: [original, reverse], garments: [white, navy],\n"
            "      symbol_for: [left-chest]}\n"
            "uvdtf: {sizes: [{name: sticker-2x3, width_in: 2, height_in: 3}]}\n", encoding="utf-8")
        order = self.root / "order.yaml"
        order.write_text("order: test\nitems:\n  - {design: sample-co, placement: left-chest, variant: reverse, qty: 3}\n")
        result = self.run_dtf("--brand", str(brand), "--order", str(order), "--allow-low-dpi")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        dtf = self.outputs / "sample-co" / "dtf"
        chest = dtf / "adult" / "left-chest"
        self.assertTrue((chest / "original" / "sample-co-left-chest-2.00x2.00in.png").is_file())
        self.assertTrue((chest / "reverse" / "sample-co-left-chest-2.00x2.00in.png").is_file())
        with Image.open(chest / "reverse" / "sample-co-left-chest-2.00x2.00in.png") as out:
            self.assertEqual(out.getpixel((300, 300))[:3], (255, 255, 255))
        sticker = dtf / "uvdtf" / "sticker-2x3" / "original"
        self.assertTrue((sticker / "sample-co-sticker-2x3-2.00x2.33in.png").is_file())
        self.assertFalse(any(dtf.glob("mockups/sticker-*")))
        with (dtf / "order-sheet.csv").open() as handle:
            rows = {(r["placement"], r["variant"]): r for r in csv.DictReader(handle)}
        self.assertEqual(rows[("left-chest", "reverse")]["qty"], "3")
        self.assertEqual(rows[("left-chest", "original")]["qty"], "")
        self.assertEqual(rows[("left-chest", "original")]["garment_colors"], "white")
        self.assertEqual(rows[("left-chest", "reverse")]["garment_colors"], "navy")
        self.assertEqual(rows[("sticker-2x3", "original")]["audience"], "uvdtf")
        manifest = json.loads((dtf / "dtf.json").read_text())
        self.assertEqual(manifest["recommendations"]["left-chest"]["navy"], "reverse")

    def test_dry_run_writes_nothing(self):
        result = self.run_dtf(str(self.source), "--placement", "full-back", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.outputs.exists())
        self.assertIn("full-back", result.stdout)


if __name__ == "__main__":
    unittest.main()


try:
    import cairosvg  # noqa: F401
    HAS_SVG = True
except (ImportError, OSError):
    HAS_SVG = False


class VectorDtfTests(unittest.TestCase):
    @unittest.skipUnless(HAS_SVG, "install .[svg] and the Cairo library for SVG checks")
    def test_vector_source_reaches_300_dpi_even_when_the_art_is_a_small_part_of_the_viewbox(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "mark.svg"
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000">'
                              '<rect x="300" y="250" width="400" height="500" fill="#102040"/></svg>')
            result = subprocess.run([sys.executable, str(SCRIPT), "dtf", str(source), "--placement", "full-back",
                                     "-o", str(root / "out")], capture_output=True, text=True, timeout=240)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("enlarged", result.stdout.lower())
            self.assertRegex(result.stdout, r"source DPI (3\d\d|[4-9]\d\d|\d{4,}) OK")
            path = root / "out" / "mark" / "dtf" / "adult" / "full-back" / "original" / "mark-full-back-11.20x14.00in.png"
            self.assertTrue(path.is_file(), result.stdout)
