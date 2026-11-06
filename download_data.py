"""Download and verify the Figure 4 data from the versioned GitHub release."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent


def sha256(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def matches(path, entry):
    return (path.is_file() and path.stat().st_size == entry["bytes"]
            and sha256(path) == entry["sha256"])


def fetch_archive(release, destination):
    url = (f"https://github.com/{release['repository']}/releases/download/"
           f"{release['tag']}/{release['asset']}")
    print(f"Downloading {release['asset']} from release {release['tag']}...", flush=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as response, destination.open("wb") as out:
            shutil.copyfileobj(response, out, length=1024 * 1024)
    except urllib.error.HTTPError as error:
        if error.code not in (401, 403, 404):
            raise RuntimeError(f"GitHub download failed (HTTP {error.code}).") from error
        # Private repositories need authentication. gh keeps credentials out of URLs.
        gh = shutil.which("gh")
        if gh is None:
            raise RuntimeError(
                "Release unavailable without authentication. For a private repository, "
                "install GitHub CLI and run 'gh auth login', or download the release "
                "asset in your browser and run 'python download_data.py --archive PATH'."
            ) from error
        destination.unlink(missing_ok=True)
        result = subprocess.run(
            [gh, "release", "download", release["tag"], "--repo", release["repository"],
             "--pattern", release["asset"], "--dir", str(destination.parent)],
            capture_output=True, text=True,
        )
        if result.returncode:
            raise RuntimeError(
                "GitHub CLI could not download the release. Check 'gh auth status' and "
                "repository access, or use --archive with a browser-downloaded asset."
            )
    except urllib.error.URLError as error:
        raise RuntimeError("Download failed. Check your connection or use --archive.") from error


def install_archive(archive, release, entries, root):
    """Validate the archive and every member before installing any data files."""
    root = Path(root).resolve()
    archive = Path(archive)
    if not matches(archive, release):
        raise ValueError("Release archive size or SHA-256 checksum does not match the manifest.")
    expected = {entry["file"]: entry for entry in entries}
    with tempfile.TemporaryDirectory(prefix=".figure4-data-", dir=root) as temporary:
        staging = Path(temporary)
        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
            if len(names) != len(set(names)) or set(names) != set(expected):
                raise ValueError("Release archive contains missing, duplicate, or unexpected files.")
            for name, entry in expected.items():
                relative = Path(name)
                destination = (root / relative).resolve()
                if relative.is_absolute() or ".." in relative.parts or not destination.is_relative_to(root):
                    raise ValueError("Unsafe data path in manifest.")
                if bundle.getinfo(name).file_size != entry["bytes"]:
                    raise ValueError(f"Unexpected uncompressed size: {name}")
                target = staging / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(name) as source, target.open("wb") as out:
                    shutil.copyfileobj(source, out, length=1024 * 1024)
                if not matches(target, entry):
                    raise ValueError(f"Input checksum mismatch: {name}")
        for name in expected:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            (staging / name).replace(target)


def download_data(archive=None):
    manifest = json.loads((ROOT / "data_manifest.json").read_text())
    entries = [entry for entry in manifest["files"] if entry["figure"] == 4]
    release = manifest["figure4_release"]
    if all(matches(ROOT / entry["file"], entry) for entry in entries):
        print("All Figure 4 data files already match their checksums; no download needed.")
        return
    if archive is not None:
        install_archive(Path(archive).expanduser(), release, entries, ROOT)
    else:
        with tempfile.TemporaryDirectory(prefix="opendrive-download-") as temporary:
            downloaded = Path(temporary) / release["asset"]
            fetch_archive(release, downloaded)
            install_archive(downloaded, release, entries, ROOT)
    print(f"Installed and verified {len(entries)} Figure 4 data files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Use a previously downloaded figure4-data.zip.")
    args = parser.parse_args()
    try:
        download_data(args.archive)
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
        raise SystemExit(str(error)) from error
