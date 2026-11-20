"""Tes untuk alur deploy berbasis arsip ZIP bertahap.

Strategi lama mengunggah ±20.000 file satu per satu lewat FTPS; itu memakan
1 jam 46 menit tanpa selesai. Strategi baru: bungkus build menjadi ZIP, potong
menjadi bagian kecil (server menolak body >8 MiB), unggah lewat HTTPS, lalu
minta server menggabungkan dan mengekstraknya.

Arsip 42,6 MiB / 20.007 file terbukti terlalu besar untuk satu request.
"""

import hashlib
import unittest
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from build_archive import (
    EXCLUDED_FROM_ARCHIVE,
    build_archive,
    chunk_archive,
    DEFAULT_CHUNK_BYTES,
)


class ChunkingTests(unittest.TestCase):
    def test_chunks_respect_server_body_limit(self):
        # PHP menolak body melebihi 8 MiB; sisakan ruang untuk overhead multipart.
        self.assertLess(DEFAULT_CHUNK_BYTES, 8 * 1024 * 1024)
        self.assertGreaterEqual(DEFAULT_CHUNK_BYTES, 1 * 1024 * 1024)

    def test_splits_archive_and_keeps_byte_order(self):
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "payload.bin"
            source.write_bytes(bytes(range(256)) * 4096)  # 1 MiB

            chunks = chunk_archive(source, Path(temp_dir), chunk_bytes=256 * 1024)

            self.assertEqual(len(chunks), 4)
            self.assertEqual([c["index"] for c in chunks], [0, 1, 2, 3])
            self.assertEqual(sum(c["size"] for c in chunks), source.stat().st_size)

            with_bad_index = [c for c in chunks if c["index"] != 0]
            self.assertTrue(with_bad_index)
            self.assertEqual(with_bad_index[0]["offset"], 256 * 1024)
            # Setiap bagian punya hash sendiri agar server bisa memverifikasi.
            self.assertTrue(all(len(c["sha256"]) == 64 for c in chunks))

    def test_never_exceeds_requested_chunk_size(self):
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "payload.bin"
            source.write_bytes(b"y" * (1024 * 1024 + 12345))

            chunks = chunk_archive(source, Path(temp_dir), chunk_bytes=200_000)

            for chunk in chunks:
                self.assertLessEqual(chunk["size"], 200_000)

    def test_refuses_chunk_size_above_server_limit(self):
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "payload.bin"
            source.write_bytes(b"z" * 1024)

            with self.assertRaises(ValueError):
                chunk_archive(source, Path(temp_dir), chunk_bytes=9 * 1024 * 1024)


class ArchiveExclusionTests(unittest.TestCase):
    def test_excludes_env_storage_and_tests_from_archive(self):
        for path in [
            ".env",
            ".env.production",
            "storage/logs/laravel.log",
            "tests/Feature/ExampleTest.php",
            "docker/php.ini",
            ".git/config",
            "node_modules/x.js",
            "bootstrap/cache/config.php",
        ]:
            with self.subTest(path=path):
                self.assertTrue(
                    EXCLUDED_FROM_ARCHIVE(PurePosixPath(path)),
                    f"{path} harus dikecualikan dari arsip deploy",
                )

    def test_keeps_runtime_files_needed_by_laravel(self):
        for path in [
            "public/index.php",
            "public/.htaccess",
            "vendor/autoload.php",
            "app/Http/Controllers/Controller.php",
            "bootstrap/app.php",
            "artisan",
        ]:
            with self.subTest(path=path):
                self.assertFalse(
                    EXCLUDED_FROM_ARCHIVE(PurePosixPath(path)),
                    f"{path} wajib ada di arsip deploy",
                )


class BuildArchiveTests(unittest.TestCase):
    def test_creates_zip_with_normalized_permissions_and_no_env(self):
        import zipfile

        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "src"
            (source / "app").mkdir(parents=True)
            (source / "storage" / "logs").mkdir(parents=True)
            (source / "app" / "Kernel.php").write_text("<?php // kernel")
            (source / "storage" / "logs" / "laravel.log").write_text("secret")
            (source / ".env").write_text("APP_KEY=secret")
            (source / "artisan").write_text("#!/usr/bin/env php")

            archive = Path(temp_dir) / "deploy.zip"
            manifest = build_archive(source, archive)

            self.assertTrue(archive.is_file())
            with zipfile.ZipFile(archive) as bundle:
                names = bundle.namelist()
                infos = {info.filename: info for info in bundle.infolist()}

            self.assertIn("app/Kernel.php", names)
            self.assertIn("artisan", names)
            self.assertNotIn(".env", names)
            self.assertNotIn("storage/logs/laravel.log", names)

            # Server mengekstrak sebagai user cPanel; mode file harus 644/755.
            self.assertEqual(infos["app/Kernel.php"].external_attr >> 16 & 0o777, 0o644)
            self.assertTrue(all(not name.startswith("/") for name in names))
            self.assertTrue(all(".." not in name.split("/") for name in names))

            self.assertEqual(manifest["file_count"], len(names))
            self.assertEqual(manifest["sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertGreater(manifest["bytes"], 0)

    def test_manifest_is_deterministic_for_unchanged_tree(self):
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "src"
            source.mkdir()
            (source / "a.php").write_text("<?php echo 1;")

            first = build_archive(source, Path(temp_dir) / "one.zip")
            # Zip menyimpan timestamp; isi file sama -> hash isi harus sama.
            second = build_archive(source, Path(temp_dir) / "two.zip")

            self.assertEqual(first["file_count"], second["file_count"])
            self.assertEqual(first["content_digest"], second["content_digest"])

    def test_refuses_to_build_from_missing_source(self):
        with TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                build_archive(Path(temp_dir) / "missing", Path(temp_dir) / "out.zip")


class ExtractEndpointContractTests(unittest.TestCase):
    """Kontrak yang harus dipenuhi endpoint PHP di server."""

    def test_public_assets_land_in_docroot_and_code_lands_above_it(self):
        source = (
            Path(__file__).resolve().parents[2] / "backend" / "public" / "deploy-extract.php"
        ).read_text()

        # Lawan `rsync backend/ -> /api`: `/api` adalah app root Laravel, docroot
        # adalah `/api/public`. Jadi arsip tanpa prefiks mendarat di app root, dan
        # `public/*` dipetakan ke docroot `public/` (mempertahankan `.htaccess`
        # Laravel). Front controller `public/index.php` TIDAK boleh menjadi
        # `index.php` di app root karena akan menimpa SPA.
        self.assertIn("PUBLIC_PREFIX", source)
        self.assertIn("APP_ROOT_DIR", source)
        self.assertIn("strlen(PUBLIC_PREFIX)", source)
        self.assertIn("substr(", source)

        # Jangan pernah menulis index.php di app root.
        self.assertNotIn(
            "APP_ROOT_DIR.'/index.php'",
            source,
            "index.php di app root akan menimpa front controller SPA",
        )
        # Helper deploy tidak boleh menimpa dirinya sendiri.
        self.assertIn("'public/deploy-extract.php'", source)

    def test_endpoint_source_rejects_path_traversal_and_requires_signature(self):
        endpoint = Path(__file__).resolve().parents[2] / "backend" / "public" / "deploy-extract.php"
        self.assertTrue(endpoint.is_file(), "backend/public/deploy-extract.php harus ada")

        source = endpoint.read_text()
        secret_generator = endpoint.with_name("deploy-secret.php").read_text()

        self.assertIn("hash_hmac", source, "autentikasi memakai HMAC")
        self.assertIn("hash_equals", source, "tanda tangan dibandingkan constant-time")
        self.assertIn("random_bytes", secret_generator, "secret harus acak")
        self.assertIn("__DIR__", source, "target harus relatif terhadap direktori endpoint")
        self.assertIn("unlink", source, "penanda nonce wajib dibersihkan")
        self.assertIn("ZipArchive", source)
        self.assertNotIn("shell_exec", source)
        self.assertNotIn("exec(", source)
        # Server menolak body >8 MiB, jadi endpoint harus menerima potongan.
        self.assertIn("MAX_CHUNK_BYTES", source)
        self.assertIn("move_uploaded_file", source)
        # Token statis sudah digantikan tanda tangan; jangan kembali ke sana.
        self.assertNotIn("X-Deploy-Token", source)

    def test_endpoint_rejects_entries_escaping_target_directory(self):
        source = (
            Path(__file__).resolve().parents[2] / "backend" / "public" / "deploy-extract.php"
        ).read_text()
        # Normalisasi entri arsip sebelum ditulis ke disk.
        self.assertIn("str_contains($normalized, '..')", source)
        self.assertIn("str_starts_with($normalized, '/')", source)
        # Validasi harus terjadi sebelum loop penulisan.
        self.assertLess(
            source.index("str_contains($normalized, '..')"),
            source.index("file_put_contents"),
            "validasi entri harus mendahului penulisan file",
        )


if __name__ == "__main__":
    unittest.main()
