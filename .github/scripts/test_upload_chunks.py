"""Tes uploader bertahap (tanpa jaringan nyata)."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from upload_chunks import upload_chunks


def _make_chunks(directory: Path, payloads: list[bytes]) -> list[dict]:
    import hashlib

    chunks = []
    offset = 0
    for index, payload in enumerate(payloads):
        path = directory / f"part{index:04d}"
        path.write_bytes(payload)
        chunks.append(
            {
                "index": index,
                "path": str(path),
                "offset": offset,
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
        offset += len(payload)
    return chunks


class UploadChunksTests(unittest.TestCase):
    def test_sends_every_chunk_in_index_order(self):
        with TemporaryDirectory() as temp_dir:
            chunks = _make_chunks(Path(temp_dir), [b"a" * 10, b"b" * 20, b"c" * 30])
            calls = []

            def fake_urlopen(request, timeout):
                calls.append(request.get_full_url())
                response = MagicMock()
                response.status = 202
                response.read.return_value = b"Accepted"
                response.__enter__ = lambda self=response: self
                response.__exit__ = lambda *args: False
                return response

            with patch("upload_chunks.urllib.request.urlopen", side_effect=fake_urlopen):
                results = upload_chunks(chunks, "f" * 64, "https://example.test/x", "tok")

            self.assertEqual(len(results), 3)
            self.assertEqual(len(calls), 3)

    def test_permanent_error_is_not_retried(self):
        import urllib.error

        with TemporaryDirectory() as temp_dir:
            chunks = _make_chunks(Path(temp_dir), [b"x" * 10])

            def fake_urlopen(request, timeout):
                raise urllib.error.HTTPError(
                    "https://example.test/x", 422, "Unprocessable", {}, None
                )

            sleep_calls = []
            with patch("upload_chunks.urllib.request.urlopen", side_effect=fake_urlopen):
                with self.assertRaises(RuntimeError) as ctx:
                    upload_chunks(
                        chunks, "f" * 64, "https://example.test/x", "tok",
                        sleep=lambda seconds: sleep_calls.append(seconds),
                    )

            self.assertIn("422", str(ctx.exception))
            self.assertEqual(sleep_calls, [], "kesalahan permanen tidak boleh diulang")

    def test_transient_error_is_retried_and_eventually_succeeds(self):
        import urllib.error

        with TemporaryDirectory() as temp_dir:
            chunks = _make_chunks(Path(temp_dir), [b"x" * 10])
            attempts = {"count": 0}

            def fake_urlopen(request, timeout):
                attempts["count"] += 1
                if attempts["count"] == 1:
                    raise urllib.error.URLError("connection reset")
                response = MagicMock()
                response.status = 200
                response.read.return_value = b"OK extracted=1"
                response.__enter__ = lambda self=response: self
                response.__exit__ = lambda *args: False
                return response

            with patch("upload_chunks.urllib.request.urlopen", side_effect=fake_urlopen):
                results = upload_chunks(
                    chunks, "f" * 64, "https://example.test/x", "tok",
                    sleep=lambda seconds: None,
                )

            self.assertEqual(attempts["count"], 2)
            self.assertEqual(results[-1][0], 200)

    def test_rejects_chunk_whose_size_changed_after_split(self):
        with TemporaryDirectory() as temp_dir:
            chunks = _make_chunks(Path(temp_dir), [b"x" * 10])
            Path(chunks[0]["path"]).write_bytes(b"y" * 99)

            with self.assertRaises(ValueError):
                upload_chunks(chunks, "f" * 64, "https://example.test/x", "tok")


if __name__ == "__main__":
    unittest.main()
