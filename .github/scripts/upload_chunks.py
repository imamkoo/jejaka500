"""Kirim arsip deploy ke endpoint cPanel secara bertahap.

Server menolak body request di atas 8 MiB, jadi arsip dipotong lebih dulu oleh
`build_archive.chunk_archive` lalu dikirim satu per satu. Endpoint menggabungkan
dan mengekstrak setelah bagian terakhir diterima.

Token dikirim lewat header dan bersifat sekali pakai: habis setelah satu deploy
sukses. Token dibuat di server dengan `deploy-token.php` (lihat dokumentasi).
"""

import hashlib
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_ENDPOINT = "https://jejaka500.followtheline.id/api/deploy-extract.php"


def upload_chunks(
    chunks: list[dict],
    archive_sha256: str,
    endpoint: str,
    token: str,
    *,
    timeout: int = 300,
    retries: int = 3,
    sleep=time.sleep,
) -> list[tuple[int, str]]:
    """Kirim setiap bagian; ulangi bila gagal sementara.

    Mengembalikan daftar (status, body) per bagian. Bagian terakhir yang
    memicu respons 200 berarti server sudah menggabungkan dan mengekstrak.
    """
    if not chunks:
        raise ValueError("Daftar bagian kosong")

    total = len(chunks)
    results: list[tuple[int, str]] = []

    for chunk in sorted(chunks, key=lambda item: item["index"]):
        payload = Path(chunk["path"]).read_bytes()
        digest = hashlib.sha256(payload).hexdigest()

        if len(payload) != chunk["size"]:
            raise ValueError(f"Ukuran bagian {chunk['index']} berubah sejak dipotong")

        boundary = f"----jejaka{chunk['index']:04d}{os.urandom(8).hex()}"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="index"\r\n\r\n{chunk["index"]}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="total"\r\n\r\n{total}\r\n'
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="chunk"; filename="part.bin"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + payload + f"\r\n--{boundary}--\r\n".encode()

        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            request = urllib.request.Request(endpoint, data=body, method="POST")
            request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
            request.add_header("X-Deploy-Token", token)
            request.add_header("X-Deploy-Chunk-Sha256", digest)
            request.add_header("X-Deploy-Sha256", archive_sha256)

            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    results.append((response.status, response.read().decode("utf-8", "replace")))
                break
            except urllib.error.HTTPError as error:
                text = error.read().decode("utf-8", "replace")
                if error.code in {400, 403, 413, 422}:
                    # Kesalahan permanen: jangan diulang.
                    raise RuntimeError(
                        f"Bagian {chunk['index']} ditolak server ({error.code}): {text.strip()}"
                    ) from error
                last_error = RuntimeError(f"{error.code}: {text.strip()}")
            except (urllib.error.URLError, TimeoutError) as error:
                last_error = error

            if attempt < retries:
                sleep(2 * attempt)

        else:
            raise RuntimeError(
                f"Bagian {chunk['index']} gagal setelah {retries} percobaan: {last_error}"
            )

    return results


def main() -> int:
    token = os.environ.get("CPANEL_DEPLOY_TOKEN", "")
    if not token:
        print("CPANEL_DEPLOY_TOKEN belum diisi", file=sys.stderr)
        return 2

    if len(sys.argv) < 3:
        print("Usage: upload_chunks.py MANIFEST_JSON CHUNKS_DIR [ENDPOINT]", file=sys.stderr)
        return 2

    import json

    manifest = json.loads(Path(sys.argv[1]).read_text())
    chunks = manifest["chunks"]
    endpoint = sys.argv[3] if len(sys.argv) > 3 else os.environ.get(
        "CPANEL_DEPLOY_ENDPOINT", DEFAULT_ENDPOINT
    )

    started = time.time()
    results = upload_chunks(chunks, manifest["sha256"], endpoint, token)
    elapsed = time.time() - started

    status, body = results[-1]
    print(f"{len(results)} bagian terkirim dalam {elapsed:.1f}s; status akhir {status}")
    print(body)
    return 0 if status == 200 and body.startswith("OK") else 1


if __name__ == "__main__":
    raise SystemExit(main())
