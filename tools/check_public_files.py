"""Reject tracked private assets and obvious credentials before publishing."""

from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
ARTWORK = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".svg",
           ".ico", ".pdf", ".zip", ".ai", ".eps", ".psd", ".pem", ".key"}
PRIVATE_FOLDERS = {"local-assets", "logo-input", "logo-exports", "exports", "output"}
# Generated demo images for the README are the only tracked artwork allowed.
DEMO_IMAGE_FOLDER = ("docs", "images")
DEMO_IMAGE_EXTENSIONS = {".png"}
DEMO_IMAGE_MAX_BYTES = 500_000
SECRET = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})")


def main():
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    paths = [Path(name.decode("utf-8")) for name in result.stdout.split(b"\0") if name]
    failures, demo_images = [], []
    for path in paths:
        if path.parts[:-1] == DEMO_IMAGE_FOLDER and path.suffix.lower() in DEMO_IMAGE_EXTENSIONS:
            try:
                size = int(subprocess.run(["git", "cat-file", "-s", ":" + path.as_posix()], cwd=ROOT,
                                          capture_output=True, check=True, text=True).stdout)
            except (ValueError, OSError, subprocess.CalledProcessError):
                failures.append(f"README demo image is unreadable: {path}")
                continue
            if size > DEMO_IMAGE_MAX_BYTES:
                failures.append(f"README demo image is over {DEMO_IMAGE_MAX_BYTES:,} bytes: {path}")
            else:
                demo_images.append(path)
            continue
        if path.parts[0] in PRIVATE_FOLDERS or path.suffix.lower() in ARTWORK or path.name.startswith(".env"):
            failures.append(f"Private or generated file is tracked: {path}")
            continue
        try:
            staged = subprocess.run(["git", "show", ":" + path.as_posix()], cwd=ROOT,
                                    capture_output=True, check=True)
            content = staged.stdout.decode("utf-8")
        except (UnicodeError, OSError, subprocess.CalledProcessError):
            failures.append(f"Tracked file is unreadable or binary: {path}")
            continue
        if SECRET.search(content):
            failures.append(f"Possible credential in tracked file: {path}")
    for failure in failures:
        print(failure, file=sys.stderr)
    if not paths:
        print("No tracked files to check. Stage the public files first.", file=sys.stderr)
        return 1
    if failures:
        return 1
    for image in demo_images:
        print(f"README demo image: {image.as_posix()}")
    print(f"PASS: {len(paths) - len(demo_images)} tracked text files and {len(demo_images)} README demo image(s); "
          "no other artwork, private folders or obvious credentials.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
