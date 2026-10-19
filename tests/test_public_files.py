"""Exercise the publishing guard against real staged files in disposable repos."""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


CHECKER = Path(__file__).resolve().parents[1] / "tools" / "check_public_files.py"


@unittest.skipUnless(shutil.which("git"), "git is needed to check public-file protection")
class PublicFileChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "tools").mkdir()
        shutil.copy2(CHECKER, self.root / "tools" / CHECKER.name)
        self.git("init", "-q")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True, check=True)

    def check(self):
        return subprocess.run([sys.executable, str(self.root / "tools" / CHECKER.name)],
                              cwd=self.root, capture_output=True, text=True)

    def test_public_text_can_be_published(self):
        (self.root / "README.md").write_text("A reusable public image utility.\n")
        self.git("add", "README.md")
        self.assertEqual(self.check().returncode, 0)

    def test_private_material_is_refused_even_if_force_added(self):
        (self.root / ".gitignore").write_text("local-assets/\n")
        (self.root / "local-assets").mkdir()
        (self.root / "local-assets" / "product.txt").write_text("private sample")
        self.git("add", "-f", "local-assets/product.txt")
        self.assertNotEqual(self.check().returncode, 0)

    def test_staged_secret_is_found_even_when_working_copy_is_clean(self):
        path = self.root / "settings.txt"
        path.write_text("ghp_" + "X" * 40)
        self.git("add", "settings.txt")
        path.write_text("safe working copy")
        self.assertNotEqual(self.check().returncode, 0)

    def test_binary_and_artwork_files_are_refused(self):
        for name in ("image.png", "data.bin"):
            with self.subTest(name=name):
                (self.root / name).write_bytes(b"\xff\x00\xfe")
                self.git("add", name)
                self.assertNotEqual(self.check().returncode, 0)
                self.git("rm", "--cached", name)

    def test_readme_demo_image_is_allowed_in_docs_images(self):
        folder = self.root / "docs" / "images"
        folder.mkdir(parents=True)
        (folder / "demo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        self.git("add", "docs/images/demo.png")
        self.assertEqual(self.check().returncode, 0)

    def test_artwork_outside_docs_images_is_refused(self):
        for name in ("docs/other.png", "docs/images/nested/demo.png", "docs/images/demo.jpg"):
            with self.subTest(name=name):
                path = self.root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"\x89PNG\r\n\x1a\n")
                self.git("add", name)
                self.assertNotEqual(self.check().returncode, 0)
                self.git("rm", "--cached", "-q", name)

    def test_oversized_readme_demo_image_is_refused(self):
        folder = self.root / "docs" / "images"
        folder.mkdir(parents=True)
        (folder / "big.png").write_bytes(b"\x00" * 500_001)
        self.git("add", "docs/images/big.png")
        self.assertNotEqual(self.check().returncode, 0)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(shutil.which("git"), "git is needed to check public-file protection")
class PrivateTermTests(PublicFileChecks):
    """Tracked YAML and CSV must not mention terms listed in the ignored private-terms file."""

    def test_private_terms_in_tracked_yaml_or_csv_are_refused(self):
        (self.root / "local-assets").mkdir()
        (self.root / "local-assets" / "private-terms.txt").write_text("SecretBrand\n# comment\n\nNT-0000000\n")
        (self.root / "examples").mkdir()
        (self.root / "examples" / "brand.yaml").write_text("brand: secretbrand co\n")
        self.git("add", "examples/brand.yaml")
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("examples/brand.yaml", result.stderr)
        self.assertNotIn("SecretBrand", result.stderr + result.stdout)
        (self.root / "examples" / "brand.yaml").write_text("brand: example co\n")
        (self.root / "examples" / "orders.csv").write_text("order,qty\nNT-0000000,2\n")
        self.git("add", "examples/brand.yaml", "examples/orders.csv")
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("examples/orders.csv", result.stderr)

    def test_without_a_terms_file_yaml_passes_and_the_check_says_so(self):
        (self.root / "settings.yaml").write_text("brand: example co\n")
        self.git("add", "settings.yaml")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("private-terms", result.stdout)

    def test_private_terms_only_apply_to_yaml_and_csv(self):
        (self.root / "local-assets").mkdir()
        (self.root / "local-assets" / "private-terms.txt").write_text("SecretBrand\n")
        (self.root / "notes.md").write_text("SecretBrand appears in prose documentation.\n")
        self.git("add", "notes.md")
        self.assertEqual(self.check().returncode, 0)
