"""Reject tracked private assets and obvious credentials before publishing."""

from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
ARTWORK = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".svg",
           ".ico", ".pdf", ".zip", ".ai", ".eps", ".psd", ".pem", ".key"}
PRIVATE_FOLDERS = {"local-assets", "logo-input", "logo-exports", "exports", "output"}
SECRET = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})")


def main():
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    paths = [Path(name.decode("utf-8")) for name in result.stdout.split(b"\0") if name]
    failures = []
    for path in paths:
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
    print(f"PASS: {len(paths)} tracked text files; no artwork, private folders or obvious credentials.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
