"""Readable run summaries: every file, its size, and every warning."""


def format_kb(size):
    return f"{size / 1024:.1f} KB"


def print_file_table(files, indent="  ", limit=None):
    """Print one line per file with its size, then a total line.

    ``files`` holds dicts with ``path`` and ``bytes``. ``limit`` folds a long
    list after that many lines so summaries for big kits stay readable.
    """
    shown = files if limit is None else files[:limit]
    width = max((len(entry["path"]) for entry in shown), default=0)
    for entry in shown:
        print(f"{indent}{entry['path']:<{width}}  {format_kb(entry['bytes']):>10}")
    if limit is not None and len(files) > limit:
        print(f"{indent}... {len(files) - limit} more file(s)")
    total = sum(entry["bytes"] for entry in files)
    print(f"{indent}Total: {len(files)} file(s), {format_kb(total)}")
