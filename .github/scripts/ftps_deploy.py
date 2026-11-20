#!/usr/bin/env python3
"""Upload build files over explicit FTPS without deleting remote files.

Files already present remotely with the same content hash and size are skipped,
so a steady-state deploy only transfers what actually changed.
"""

import hashlib
import io
import json
import os
import posixpath
import ssl
import sys
from ftplib import FTP_TLS, error_perm
from pathlib import Path, PurePosixPath

MANIFEST_VERSION = 1


def is_excluded(path: PurePosixPath) -> bool:
    parts = path.parts
    name = path.name

    if any(part in {".git", ".github", "node_modules", "tests", "docker"} for part in parts):
        return True
    if any(part == "storage" for part in parts):
        return True
    # .htaccess di akar docroot milik server (aturan routing SPA -> /api, /admin).
    # .htaccess lain, mis. backend/public/.htaccess, wajib ikut terunggah.
    if path == PurePosixPath(".htaccess"):
        return True
    if name == ".env" or name.startswith(".env."):
        return True
    if name.startswith(".deploy-manifest"):
        return True
    if name in {"phpunit.xml", ".phpunit.result.cache"}:
        return True
    if (
        name == "config.php"
        and any(
            part == "bootstrap" and idx + 1 < len(parts) and parts[idx + 1] == "cache"
            for idx, part in enumerate(parts)
        )
    ):
        return True

    return False


def remote_path(root: str, relative: str) -> str:
    if any(char in "\r\n\0" for char in f"{root}{relative}"):
        raise ValueError("Remote paths must not contain control characters")

    if relative.startswith("/"):
        raise ValueError("Relative paths must be relative, not absolute")

    root_path = PurePosixPath("/", root)
    relative_path = PurePosixPath(relative)

    if ".." in root_path.parts or ".." in relative_path.parts:
        raise ValueError("Remote paths must not contain '..'")

    resolved = posixpath.normpath(posixpath.join(root_path.as_posix(), relative_path.as_posix()))
    if not resolved.startswith(root_path.as_posix()):
        raise ValueError("Resolved remote path escapes target root")

    return resolved


def ensure_remote_directory(ftp: FTP_TLS, directory: str, created: set[str] | None = None) -> None:
    current = "/"
    for part in PurePosixPath(directory).parts:
        if part == "/":
            continue
        current = posixpath.join(current, part)
        if created is not None and current in created:
            continue
        try:
            ftp.mkd(current)
        except error_perm:
            try:
                ftp.cwd(current)
            except error_perm as error:
                raise RuntimeError(f"Remote directory unavailable: {current}") from error
        if created is not None:
            created.add(current)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(ftp: FTP_TLS, manifest_remote: str) -> dict:
    buffer = io.BytesIO()
    try:
        ftp.retrbinary(f"RETR {manifest_remote}", buffer.write)
    except error_perm:
        return {"files": {}}

    try:
        data = json.loads(buffer.getvalue().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"files": {}}

    if not isinstance(data, dict) or data.get("version") != MANIFEST_VERSION:
        return {"files": {}}
    if not isinstance(data.get("files"), dict):
        return {"files": {}}

    return data


def save_manifest(ftp: FTP_TLS, manifest_remote: str, manifest: dict, created: set[str]) -> bool:
    payload = json.dumps(manifest, sort_keys=True).encode("utf-8")
    try:
        ensure_remote_directory(ftp, posixpath.dirname(manifest_remote), created)
        ftp.storbinary(f"STOR {manifest_remote}", io.BytesIO(payload))
    except (error_perm, OSError) as error:
        print(f"Peringatan: gagal menyimpan manifest ({error}); deploy berikutnya mengunggah ulang.", file=sys.stderr)
        return False
    return True


def remote_size(ftp: FTP_TLS, path: str) -> int | None:
    try:
        ftp.voidcmd("TYPE I")
        size = ftp.size(path)
    except (error_perm, OSError):
        return None
    return size


def iter_local_files(source: Path):
    for local in sorted(source.rglob("*")):
        relative = PurePosixPath(local.relative_to(source).as_posix())
        if is_excluded(relative) or local.is_symlink() or not local.is_file():
            continue
        yield local, relative


def deploy(
    source: Path,
    remote_root: str,
    manifest_remote: str | None = None,
    force: bool = False,
) -> dict[str, int]:
    host = os.environ["CPANEL_FTP_HOST"]
    username = os.environ["CPANEL_FTP_USERNAME"]
    password = os.environ["CPANEL_FTP_PASSWORD"]
    port = int(os.environ.get("CPANEL_FTP_PORT", "21"))

    if not source.is_dir():
        raise ValueError(f"Source directory does not exist: {source}")

    context = ssl.create_default_context()
    stats = {"uploaded": 0, "skipped": 0}

    with FTP_TLS(context=context, timeout=60) as ftp:
        ftp.connect(host, port)
        ftp.auth()
        ftp.login(username, password)
        ftp.prot_p()

        previous = {"files": {}} if force or not manifest_remote else load_manifest(ftp, manifest_remote)
        previous_files = previous.get("files", {})
        current_files: dict[str, dict] = {}
        created: set[str] = set()

        for local, relative in iter_local_files(source):
            key = relative.as_posix()
            target = remote_path(remote_root, key)
            size = local.stat().st_size
            digest = sha256_of(local)

            entry = previous_files.get(key)
            unchanged = (
                isinstance(entry, dict)
                and entry.get("sha256") == digest
                and entry.get("size") == size
                and remote_size(ftp, target) == size
            )

            current_files[key] = {"sha256": digest, "size": size}

            if unchanged:
                stats["skipped"] += 1
                continue

            ensure_remote_directory(ftp, posixpath.dirname(target), created)
            with local.open("rb") as file_handle:
                ftp.storbinary(f"STOR {target}", file_handle)
            stats["uploaded"] += 1

        # File yang hilang di sumber sengaja tidak dihapus dari server.
        if manifest_remote and stats["uploaded"] > 0:
            save_manifest(
                ftp,
                manifest_remote,
                {"version": MANIFEST_VERSION, "target": remote_root, "files": current_files},
                created,
            )

    return stats


def main() -> int:
    if len(sys.argv) < 3:
        print(
            "Usage: ftps_deploy.py SOURCE_DIR REMOTE_ROOT [MANIFEST_REMOTE] [--force]",
            file=sys.stderr,
        )
        return 2

    arguments = [item for item in sys.argv[1:] if item != "--force"]
    force = "--force" in sys.argv[3:]
    manifest_remote = arguments[2] if len(arguments) > 2 else None

    try:
        stats = deploy(Path(arguments[0]), arguments[1], manifest_remote, force)
    except Exception as error:
        print(f"FTPS deploy failed: {error}", file=sys.stderr)
        return 1

    print(
        f"FTPS selesai: {stats['uploaded']} file diunggah, {stats['skipped']} tidak berubah; "
        "tidak ada file server yang dihapus."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
