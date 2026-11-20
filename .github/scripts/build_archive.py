#!/usr/bin/env python3
"""Bungkus hasil build menjadi satu arsip ZIP untuk diunggah ke cPanel.

Mengunggah puluhan ribu file satu per satu lewat FTPS butuh jam dan mudah
terputus. Satu ZIP bisa diunggah dalam hitungan menit, lalu diekstrak di
server oleh `backend/public/deploy-extract.php` yang dikunci token.

Arsip tidak boleh memuat rahasia atau state runtime: `.env`, `storage/`,
`tests/`, `docker/`, dan `node_modules/` selalu dibuang.
"""

import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath

EXCLUDED_PARTS = {".git", ".github", "node_modules", "tests", "docker", "storage"}

FILE_MODE = 0o644
DIR_MODE = 0o755

# Server menolak body request di atas 8 MiB (413 dari PHP). Sisakan ruang untuk
# overhead multipart dan header, dan jangan pernah melewati batas itu.
SERVER_BODY_LIMIT_BYTES = 8 * 1024 * 1024
DEFAULT_CHUNK_BYTES = 4 * 1024 * 1024


def EXCLUDED_FROM_ARCHIVE(path: PurePosixPath) -> bool:
    """True bila path tidak boleh masuk arsip deploy."""
    name = path.name

    if any(part in EXCLUDED_PARTS for part in path.parts):
        return True
    if name == ".env" or name.startswith(".env."):
        return True
    if name.startswith(".deploy-manifest") or name.startswith("deploy-upload"):
        return True
    if name in {"phpunit.xml", ".phpunit.result.cache"}:
        return True
    if path == PurePosixPath("public/deploy-extract.php"):
        return True
    if path == PurePosixPath("public/deploy-token.php"):
        return True
    if (
        name == "config.php"
        and any(
            part == "bootstrap" and idx + 1 < len(path.parts) and path.parts[idx + 1] == "cache"
            for idx, part in enumerate(path.parts)
        )
    ):
        return True

    return False


def _iter_included(source: Path):
    for local in sorted(source.rglob("*")):
        if local.is_symlink() or not local.is_file():
            continue
        relative = PurePosixPath(local.relative_to(source).as_posix())
        if EXCLUDED_FROM_ARCHIVE(relative):
            continue
        yield local, relative


def _digest_included(source: Path) -> str:
    """Digest isi file (bukan biner zip) agar stabil antar-build."""
    digest = hashlib.sha256()
    for local, relative in _iter_included(source):
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(local.read_bytes()).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def build_archive(source: Path, archive: Path) -> dict:
    source = Path(source)
    archive = Path(archive)

    if not source.is_dir():
        raise ValueError(f"Source directory does not exist: {source}")

    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        archive.unlink()

    file_count = 0
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for local, relative in _iter_included(source):
            name = relative.as_posix()
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100000 | FILE_MODE) << 16
            bundle.writestr(info, local.read_bytes())
            file_count += 1

    payload = archive.read_bytes()

    return {
        "file_count": file_count,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "content_digest": _digest_included(source),
    }


def chunk_archive(
    archive: Path,
    output_dir: Path,
    chunk_bytes: int = DEFAULT_CHUNK_BYTES,
) -> list[dict]:
    """Potong arsip menjadi bagian-bagian yang aman dikirim per request.

    Server menolak body di atas 8 MiB, jadi arsip 40+ MiB harus dipecah.
    Setiap bagian dicatat bersama offset dan hash-nya agar server bisa
    menggabungkan ulang dengan urutan dan isi yang terverifikasi.
    """
    archive = Path(archive)
    output_dir = Path(output_dir)

    if chunk_bytes > SERVER_BODY_LIMIT_BYTES:
        raise ValueError(
            f"chunk_bytes {chunk_bytes} melebihi batas body server {SERVER_BODY_LIMIT_BYTES}"
        )
    if chunk_bytes <= 0:
        raise ValueError("chunk_bytes harus positif")
    if not archive.is_file():
        raise ValueError(f"Archive does not exist: {archive}")

    output_dir.mkdir(parents=True, exist_ok=True)

    chunks: list[dict] = []
    offset = 0
    index = 0

    with archive.open("rb") as handle:
        while True:
            payload = handle.read(chunk_bytes)
            if not payload:
                break

            part = output_dir / f"{archive.name}.part{index:04d}"
            part.write_bytes(payload)

            chunks.append(
                {
                    "index": index,
                    "name": part.name,
                    "path": str(part),
                    "offset": offset,
                    "size": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )

            offset += len(payload)
            index += 1

    return chunks


def main() -> int:
    if len(sys.argv) < 4:
        print(
            "Usage: build_archive.py SOURCE_DIR ARCHIVE_PATH MANIFEST_PATH "
            "[CHUNK_BYTES] [CHUNKS_DIR]",
            file=sys.stderr,
        )
        return 2

    source = Path(sys.argv[1])
    archive = Path(sys.argv[2])
    manifest_path = Path(sys.argv[3])
    chunk_bytes = int(sys.argv[4]) if len(sys.argv) > 4 else DEFAULT_CHUNK_BYTES
    chunks_dir = Path(sys.argv[5]) if len(sys.argv) > 5 else archive.parent / "chunks"

    try:
        manifest = build_archive(source, archive)
        chunks = chunk_archive(archive, chunks_dir, chunk_bytes=chunk_bytes)
    except Exception as error:
        print(f"build_archive failed: {error}", file=sys.stderr)
        return 1

    manifest["chunks"] = chunks
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))

    print(
        f"Arsip: {archive} — {manifest['file_count']} file, "
        f"{manifest['bytes'] / 1024 / 1024:.1f} MiB, {len(chunks)} bagian"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
