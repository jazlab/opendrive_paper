"""Offline checks for release download integrity and installation."""

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import download_data


class DownloadDataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.content = b"original array bytes"
        self.name = "figures/fig4/data/recording/peaks.npy"
        self.entry = {
            "figure": 4, "file": self.name, "bytes": len(self.content),
            "sha256": hashlib.sha256(self.content).hexdigest(),
        }
        self.archive = self.root / "figure4-data.zip"
        self.make_archive({self.name: self.content})

    def make_archive(self, members):
        with zipfile.ZipFile(self.archive, "w") as archive:
            for name, content in members.items():
                archive.writestr(name, content)
        self.release = {
            "repository": "example/repository", "tag": "data-v1",
            "asset": self.archive.name, "bytes": self.archive.stat().st_size,
            "sha256": download_data.sha256(self.archive),
        }
        (self.root / "data_manifest.json").write_text(json.dumps({
            "figure4_release": self.release, "files": [self.entry],
        }))

    def test_verified_install_and_repeat_without_download(self):
        with patch.object(download_data, "ROOT", self.root):
            download_data.download_data(self.archive)
            self.assertEqual((self.root / self.name).read_bytes(), self.content)
            with patch.object(download_data, "fetch_archive") as fetch:
                download_data.download_data()
                fetch.assert_not_called()

    def test_corrupt_archive_is_rejected_before_install(self):
        self.archive.write_bytes(self.archive.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "archive size or SHA-256"):
            download_data.install_archive(self.archive, self.release, [self.entry], self.root)
        self.assertFalse((self.root / self.name).exists())

    def test_wrong_member_checksum_preserves_existing_file(self):
        target = self.root / self.name
        target.parent.mkdir(parents=True)
        target.write_bytes(b"keep this file")
        self.make_archive({self.name: b"x" * len(self.content)})
        with self.assertRaisesRegex(ValueError, "Input checksum mismatch"):
            download_data.install_archive(self.archive, self.release, [self.entry], self.root)
        self.assertEqual(target.read_bytes(), b"keep this file")

    def test_unexpected_path_is_rejected(self):
        self.make_archive({self.name: self.content, "../outside.npy": b"unexpected"})
        with self.assertRaisesRegex(ValueError, "unexpected files"):
            download_data.install_archive(self.archive, self.release, [self.entry], self.root)
        self.assertFalse((self.root / self.name).exists())

    def test_missing_member_is_rejected(self):
        self.make_archive({})
        with self.assertRaisesRegex(ValueError, "missing, duplicate"):
            download_data.install_archive(self.archive, self.release, [self.entry], self.root)

    def test_public_download_needs_no_github_cli(self):
        content = self.archive.read_bytes()
        with patch.object(download_data, "ROOT", self.root), \
             patch.object(download_data.urllib.request, "urlopen", return_value=io.BytesIO(content)), \
             patch.object(download_data.subprocess, "run") as cli:
            download_data.download_data()
            cli.assert_not_called()
        self.assertEqual((self.root / self.name).read_bytes(), self.content)


if __name__ == "__main__":
    unittest.main()
