#!/usr/bin/env python3
"""Upload build files over explicit FTPS without deleting remote files."""

import os
import posixpath
import ssl
import sys
from ftplib import FTP_TLS, error_perm
from pathlib import Path, PurePosixPath


def is_excluded(path: PurePosixPath) -> bool:
    parts = path.parts
    name = path.name

    if any(part == ".git" or part == ".github" or part == "node_modules" for part in parts):
        return True
    if any(part == "storage" for part in parts):
        return True
    if name == ".htaccess" or name == ".env" or name.startswith(".env."):
        return True
    if "tests" in parts or "docker" in parts:
        return True
    if name in {"phpunit.xml", ".phpunit.result.cache"}:
        return True
    if path.as_posix().startswith("bootstrap/cache/") and name.endswith(".php"):
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


def ensure_remote_directory(ftp: FTP_TLS, directory: str) -> None:
    current = "/"
    for part in PurePosixPath(directory).parts:
        if part == "/":
            continue
        current = posixpath.join(current, part)
        try:
            ftp.mkd(current)
        except error_perm:
            try:
                ftp.cwd(current)
            except error_perm as error:
                raise RuntimeError(f"Remote directory unavailable: {current}") from error


def deploy(source: Path, remote_root: str) -> int:
    host = os.environ["CPANEL_FTP_HOST"]
    username = os.environ["CPANEL_FTP_USERNAME"]
    password = os.environ["CPANEL_FTP_PASSWORD"]
    port = int(os.environ.get("CPANEL_FTP_PORT", "21"))

    if not source.is_dir():
        raise ValueError(f"Source directory does not exist: {source}")

    context = ssl.create_default_context()
    uploaded = 0

    with FTP_TLS(context=context, timeout=30) as ftp:
        ftp.connect(host, port)
        ftp.auth()
        ftp.login(username, password)
        ftp.prot_p()

        for local in sorted(source.rglob("*")):
            relative = PurePosixPath(local.relative_to(source).as_posix())
            if is_excluded(relative) or local.is_symlink() or not local.is_file():
                continue

            target = remote_path(remote_root, relative.as_posix())
            parent = posixpath.dirname(target)
            ensure_remote_directory(ftp, parent)

            with local.open("rb") as file_handle:
                ftp.storbinary(f"STOR {target}", file_handle)
            uploaded += 1

    return uploaded


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: ftps_deploy.py SOURCE_DIR REMOTE_ROOT", file=sys.stderr)
        return 2

    try:
        count = deploy(Path(sys.argv[1]), sys.argv[2])
    except Exception as error:
        print(f"FTPS deploy failed: {error}", file=sys.stderr)
        return 1

    print(f"Uploaded {count} files over verified explicit FTPS; no remote files deleted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
