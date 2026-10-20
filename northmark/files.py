"""Small file helpers shared by the output writers."""

import hashlib


def sha256_file(path, chunk_size=1 << 20):
    """SHA-256 of a file read in chunks, so large sheets never sit in memory for hashing."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()
