import asyncio
import tempfile
import unittest
from pathlib import Path

from download_safety import read_response_limited, resolve_existing_path, safe_download_path


class FakeContent:
    def __init__(self, chunks):
        self._chunks = chunks

    async def iter_chunked(self, _size):
        for chunk in self._chunks:
            yield chunk


class DownloadSafetyTests(unittest.TestCase):
    def test_safe_download_path_strips_remote_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(
                safe_download_path(tmpdir, "../../../outside.mod", source="https://example.test/1")
            )

            self.assertEqual(destination.parent, Path(tmpdir).resolve())
            self.assertTrue(destination.name.endswith("_outside.mod"))

    def test_resolve_existing_path_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "archive"
            root.mkdir()
            track = root / "track.sap"
            track.write_bytes(b"SAP")

            self.assertEqual(resolve_existing_path(str(root), "track.sap"), str(track.resolve()))
            self.assertIsNone(resolve_existing_path(str(root), "../track.sap"))

    def test_read_response_limited_rejects_oversized_content(self):
        response = type("Response", (), {"content": FakeContent([b"1234", b"56"])})()

        with self.assertRaises(ValueError):
            asyncio.run(read_response_limited(response, max_bytes=5))
