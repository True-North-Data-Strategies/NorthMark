"""Gang-sheet packing and output with generated artwork."""

import csv
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

from logo_sizes.gang import (CUT_LIST_COLUMNS, GangItem, cost_compare, load_job, pack, upload_warning)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "make_logo_sizes.py"
HAS_REPORTLAB = importlib.util.find_spec("reportlab") is not None
FEET = (24.0, 60.0, 120.0)


def item(name, width, height, qty=1):
    return GangItem(key=name, design=name, file=Path(f"{name}.png"), width_in=width, height_in=height, qty=qty)


def separated(a, b, gap):
    """True when two placed boxes are at least ``gap`` apart in x or y."""
    return (a.x_in + a.width_in + gap <= b.x_in + 1e-6 or b.x_in + b.width_in + gap <= a.x_in + 1e-6
            or a.y_in + a.height_in + gap <= b.y_in + 1e-6 or b.y_in + b.height_in + gap <= a.y_in + 1e-6)


class PackingTests(unittest.TestCase):
    def test_no_overlaps_and_gap_and_margin_are_respected(self):
        items = [item("a", 10, 11, 3), item("b", 3.5, 2, 6), item("c", 12, 14, 1), item("d", 4, 6, 2)]
        sheets = pack(items, 22, FEET, gap=0.25, margin=0.25, rotate=True)
        placed = [p for sheet in sheets for p in sheet.placements]
        self.assertEqual(len(placed), 12)
        for sheet in sheets:
            for p in sheet.placements:
                self.assertGreaterEqual(p.x_in, 0.25 - 1e-6)
                self.assertGreaterEqual(p.y_in, 0.25 - 1e-6)
                self.assertLessEqual(p.x_in + p.width_in, 22 - 0.25 + 1e-6)
                self.assertLessEqual(p.y_in + p.height_in, sheet.length_in - 0.25 + 1e-6)
            for index, a in enumerate(sheet.placements):
                for b in sheet.placements[index + 1:]:
                    self.assertTrue(separated(a, b, 0.25), (a, b))

    def test_layout_is_deterministic_regardless_of_input_order(self):
        items = [item("a", 10, 11, 2), item("b", 3.5, 2, 4), item("c", 12, 14, 1)]
        first = pack(items, 22, FEET, 0.25, 0.25, True)
        shuffled = list(items)
        random.Random(3).shuffle(shuffled)
        second = pack(shuffled, 22, FEET, 0.25, 0.25, True)
        self.assertEqual([(s.length_in, [(p.key, p.copy, p.x_in, p.y_in, p.rotated) for p in s.placements]) for s in first],
                         [(s.length_in, [(p.key, p.copy, p.x_in, p.y_in, p.rotated) for p in s.placements]) for s in second])

    def test_shortest_standard_length_that_fits_is_chosen(self):
        four = pack([item("a", 10, 11, 4)], 22, FEET, 0.25, 0.25, False)
        self.assertEqual([s.length_in for s in four], [24.0])
        six = pack([item("a", 10, 11, 6)], 22, FEET, 0.25, 0.25, False)
        self.assertEqual([s.length_in for s in six], [60.0])
        self.assertGreater(four[0].utilization, 0.8)

    def test_rotation_packs_tighter_and_can_be_disabled(self):
        items = [item("wide", 11, 6, 4)]
        self.assertEqual([s.length_in for s in pack(items, 22, FEET, 0.25, 0.25, rotate=True)], [24.0])
        self.assertEqual([s.length_in for s in pack(items, 22, FEET, 0.25, 0.25, rotate=False)], [60.0])
        self.assertTrue(all(p.rotated for p in pack(items, 22, FEET, 0.25, 0.25, rotate=True)[0].placements))

    def test_jobs_longer_than_the_longest_sheet_are_split(self):
        # Three rows of two; a 24 in sheet holds two rows, so the third row needs a second sheet.
        sheets = pack([item("a", 10, 11, 6)], 22, (24.0,), 0.25, 0.25, False)
        self.assertEqual([len(s.placements) for s in sheets], [4, 2])
        self.assertTrue(all(s.length_in == 24.0 for s in sheets))

    def test_oversize_item_is_refused(self):
        with self.assertRaises(ValueError):
            pack([item("huge", 23, 23)], 22, FEET, 0.25, 0.25, True)
        with self.assertRaises(ValueError):
            pack([item("tall", 5, 30)], 22, (24.0,), 0.25, 0.25, True)


class JobFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        Image.new("RGBA", (300, 450), (200, 0, 0, 255)).save(self.root / "sticker.png", dpi=(300, 300))
        exports = self.root / "exports" / "demo" / "dtf" / "adult" / "full-back" / "original"
        exports.mkdir(parents=True)
        Image.new("RGBA", (600, 900), (0, 0, 200, 255)).save(exports / "demo-full-back-2.00x3.00in.png", dpi=(300, 300))

    def test_yaml_and_csv_jobs_resolve_the_same_items(self):
        (self.root / "job.yaml").write_text(
            "job: sample\nsheet: {width_in: 22, gap_in: 0.25, margin_in: 0.25}\nitems:\n"
            "  - {design: demo, placement: full-back, variant: original, qty: 2}\n"
            "  - {file: sticker.png, width_in: 1, height_in: 1.5, qty: 1}\n")
        (self.root / "job.csv").write_text(
            "design,placement,variant,file,width_in,height_in,qty\n"
            "demo,full-back,original,,,,2\n"
            ",,,sticker.png,1,1.5,1\n")
        yaml_job = load_job(self.root / "job.yaml", self.root / "exports")
        csv_job = load_job(self.root / "job.csv", self.root / "exports")
        for job in (yaml_job, csv_job):
            self.assertEqual([(i.design, i.width_in, i.height_in, i.qty) for i in job.items],
                             [("demo", 2.0, 3.0, 2), ("sticker", 1.0, 1.5, 1)])
            self.assertTrue(job.items[0].file.is_file())
        self.assertEqual(yaml_job.name, "sample")
        self.assertEqual(csv_job.name, "job")

    def test_template_header_matches_the_cut_list(self):
        header = (ROOT / "examples" / "templates" / "cut-list.csv").read_text().strip().split(",")
        self.assertEqual(header, list(CUT_LIST_COLUMNS))
        job_header = (ROOT / "examples" / "templates" / "gang-job.csv").read_text().strip().split(",")
        self.assertEqual(job_header, ["design", "placement", "variant", "file", "width_in", "height_in", "qty"])

    def test_missing_dtf_output_is_an_actionable_error(self):
        (self.root / "job.yaml").write_text("job: sample\nitems:\n  - {design: ghost, placement: full-back, qty: 1}\n")
        with self.assertRaises(ValueError) as caught:
            load_job(self.root / "job.yaml", self.root / "exports")
        self.assertIn("ghost", str(caught.exception))
        self.assertIn("dtf", str(caught.exception).lower())


class CostTests(unittest.TestCase):
    def test_upload_warning_triggers_above_the_ceiling(self):
        self.assertIsNone(upload_warning(10_000_000, 50))
        self.assertIn("MB", upload_warning(60_000_000, 50))

    def test_cost_compare_uses_configured_prices_and_bulk_tiers(self):
        tiers = [{"min_qty": 1, "max_qty": 14, "percent": 0}, {"min_qty": 15, "max_qty": 49, "percent": 20}]
        prices = {"currency": "USD", "gang_sheet_by_length_ft": {2: 10.0, 5: 20.0}, "by_size": {"full-back": 3.0}}
        sheets_ft = [2, 5]
        items = [item("full-back", 10, 11, 20)]
        report = cost_compare(sheets_ft, items, prices, tiers)
        self.assertEqual(report["gang_total"], 30.0)
        self.assertEqual(report["gang_per_transfer"], 1.5)
        self.assertEqual(report["by_size_total"], 48.0)
        self.assertEqual(report["by_size_discount_percent"], 20)
        self.assertIn("$30.00", report["summary"])


class GangCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.outputs = self.root / "out"
        self.outputs.mkdir()
        Image.new("RGBA", (300, 450), (200, 0, 0, 255)).save(self.root / "red.png", dpi=(300, 300))
        Image.new("RGBA", (600, 300), (0, 0, 200, 255)).save(self.root / "blue.png", dpi=(300, 300))
        (self.root / "job.yaml").write_text(
            "job: tiny\nsheet: {width_in: 4, lengths_in: [6, 12], gap_in: 0.25, margin_in: 0.25}\nitems:\n"
            "  - {file: red.png, width_in: 1, height_in: 1.5, qty: 3}\n"
            "  - {file: blue.png, width_in: 2, height_in: 1, qty: 2}\n")

    def run_gang(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "gang", *args, "-o", str(self.outputs)],
                              capture_output=True, text=True, cwd=self.root, timeout=120)

    def test_job_produces_sheet_files_layout_cut_list_and_preview(self):
        result = self.run_gang("job.yaml")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        folder = self.outputs / "gang-sheets" / "tiny"
        sheet = folder / "sheet-22x6.png"
        pngs = sorted(folder.glob("sheet-*.png"))
        self.assertEqual(len(pngs), 1, result.stdout)
        self.assertEqual(pngs[0].name, "sheet-4x6.png")
        with Image.open(pngs[0]) as out:
            self.assertEqual(out.size, (1200, 1800))
            self.assertEqual(tuple(round(v) for v in out.info["dpi"]), (300, 300))
        layout = json.loads((folder / "layout.json").read_text())
        self.assertEqual(layout["sheets"][0]["width_in"], 4)
        self.assertEqual(sum(len(s["items"]) for s in layout["sheets"]), 5)
        first = layout["sheets"][0]["items"][0]
        with Image.open(pngs[0]) as out:
            x = round((first["x_in"] + first["width_in"] / 2) * 300)
            y = round((first["y_in"] + first["height_in"] / 2) * 300)
            self.assertIn(out.getpixel((x, y))[:3], [(200, 0, 0), (0, 0, 200)])
            self.assertEqual(out.getpixel((1, 1))[3], 0)
        with (folder / "cut-list.csv").open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 5)
        self.assertEqual(set(rows[0]), set(CUT_LIST_COLUMNS))
        self.assertTrue((folder / "preview.png").is_file())
        self.assertIn("utilization", result.stdout.lower())
        if HAS_REPORTLAB:
            self.assertTrue((folder / "sheet-4x6.pdf").is_file())
        else:
            self.assertIn("pdf", result.stdout.lower())

    def test_dry_run_reports_the_layout_without_writing(self):
        result = self.run_gang("job.yaml", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.outputs / "gang-sheets").exists())
        self.assertIn("4 x 6 in", result.stdout)

    def test_existing_job_output_needs_overwrite(self):
        self.assertEqual(self.run_gang("job.yaml").returncode, 0)
        self.assertNotEqual(self.run_gang("job.yaml").returncode, 0)
        again = self.run_gang("job.yaml", "--overwrite")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertTrue(any((self.outputs / ".backups").glob("*/tiny/layout.json")))


if __name__ == "__main__":
    unittest.main()
