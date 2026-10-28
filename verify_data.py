"""Verify the supplied input files using only the Python standard library."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def verify_data(figure="all"):
    entries = json.loads((ROOT / "data_manifest.json").read_text())["files"]
    errors = []
    checked = 0
    for entry in entries:
        if figure != "all" and entry["figure"] != int(figure):
            continue
        path = ROOT / entry["file"]
        if not path.is_file():
            errors.append(f"Missing: {entry['file']}")
            continue
        with path.open("rb") as source:
            if source.read(100).startswith(b"version https://git-lfs.github.com/spec/v1"):
                errors.append(f"Old LFS pointer, not data: {entry['file']}")
                continue
            source.seek(0)
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        if digest != entry["sha256"]:
            errors.append(f"Checksum mismatch: {entry['file']}")
        else:
            checked += 1
    if errors:
        hint = "\nFor Figure 4 data, run 'python download_data.py' from the repository root."
        raise SystemExit("Input verification failed:\n" + "\n".join(errors) + hint)
    print(f"Verified {checked} input files.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figure", choices=["all", "3", "4"], default="all")
    verify_data(parser.parse_args().figure)
