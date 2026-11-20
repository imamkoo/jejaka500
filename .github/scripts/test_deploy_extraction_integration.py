"""Tes integrasi: ekstraksi arsip sungguhan ke pohon direktori tiruan.

Memalsukan tata letak server (`jejaka500/api` + `jejaka500/api/public`) dan
menjalankan handler melalui PHP CLI dengan request web tiruan. Ini menangkap
kesalahan yang tidak terlihat dari membaca kode: berkas mendarat di tempat yang
tidak dilayani, `.env` tertimpa, atau ekstraksi meninggalkan sampah di staging.
"""

import hashlib

import shutil
import subprocess
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

HANDLER = Path(__file__).resolve().parents[2] / "backend" / "deploy-cpanel" / "cpanel-deploy-handler.php"
LIB = HANDLER.with_name("deploy-lib.php")

# Tiru request web yang sah: satu potongan, tanda tangan benar.
# Fungsi `verify_signature()` dipakai dari lib agar harapan dan pelaksanaan sama.
RUNNER = r"""// Tata letak server: $argv[2] = app root (`api`), handler dipasang di
// `storage/cpanel-deploy`. Konstanta handler dihitung dari `__DIR__`, jadi
// berkas handler disalin ke lokasi itu oleh tes.
$appRoot = $argv[1];
$deployDir = $appRoot.'/storage/cpanel-deploy';

$secret = 'test-secret';
file_put_contents($deployDir.'/deploy-secret.txt', $secret."\n");

$chunk = $argv[2];
$archiveSha = $argv[3];
$timestamp = (string) time();
$nonce = 'integration-nonce';

// Salin potongan ke lokasi unggahan tiruan.
$upload = $deployDir.'/uploaded-part';
copy($chunk, $upload);

$_SERVER['REQUEST_METHOD'] = 'POST';
$_SERVER['HTTP_X_DEPLOY_SHA256'] = $archiveSha;
$_SERVER['HTTP_X_DEPLOY_TIMESTAMP'] = $timestamp;
$_SERVER['HTTP_X_DEPLOY_NONCE'] = $nonce;
$_SERVER['HTTP_X_DEPLOY_SIGNATURE'] = hash_hmac(
    'sha256',
    $timestamp.':'.$nonce.':'.$archiveSha,
    $secret
);
$_SERVER['HTTP_X_DEPLOY_CHUNK_SHA256'] = hash_file('sha256', $upload);
$_POST['index'] = '0';
$_POST['total'] = '1';
$_FILES['chunk'] = [
    'tmp_name' => $upload,
    'size' => filesize($upload),
    'error' => UPLOAD_ERR_OK,
];

// `is_uploaded_file()` gagal untuk berkas biasa; longgarkan hanya di harness.
$handler = file_get_contents($argv[4]);
// SAPI di harness adalah `cli`, sama seperti produksi. Ganti guard CLI agar
// alur web dijalankan seperti saat request HTTP sungguhan.
$handler = str_replace(
    "if (PHP_SAPI === 'cli') {",
    "if (false) {",
    $handler
);
$handler = str_replace(
    "is_uploaded_file(\$_FILES['chunk']['tmp_name'])",
    "is_file(\$_FILES['chunk']['tmp_name'])",
    $handler
);
$handler = str_replace(
    'move_uploaded_file($upload[\'tmp_name\'], $partPath)',
    'rename($upload[\'tmp_name\'], $partPath)',
    $handler
);
$tmp = $argv[5];
file_put_contents($tmp, $handler);

include $tmp;
"""


def ziparchive_available() -> bool:
    """`ZipArchive` wajib ada; server cPanel punya ekstensi ini (terukur), lokal belum tentu."""
    if shutil.which("php") is None:
        return False
    result = subprocess.run(
        ["php", "-r", "echo class_exists('ZipArchive') ? '1' : '0';"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip() == "1"


@unittest.skipUnless(ziparchive_available(), "ekstensi zip PHP tidak tersedia")
class ExtractionIntegrationTests(unittest.TestCase):
    def _run(self, root: Path, archive: Path) -> subprocess.CompletedProcess:
        deploy_dir = root / "storage" / "cpanel-deploy"
        deploy_dir.mkdir(parents=True, exist_ok=True)
        # Handler menghitung path dari `__DIR__`, jadi harus benar-benar di sini —
        # termasuk salinan yang di-patch, agar `__DIR__` tetap sama.
        shutil.copy(LIB, deploy_dir / "deploy-lib.php")
        patched = deploy_dir / "cpanel-deploy-handler.php"

        archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()

        return subprocess.run(
            [
                "php",
                "-r",
                RUNNER,
                root.as_posix(),
                archive.as_posix(),
                archive_sha,
                HANDLER.as_posix(),
                patched.as_posix(),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=root,
        )

    def test_real_archive_lands_in_the_served_layout(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "jejaka500" / "api"
            (root / "public").mkdir(parents=True)
            (root / ".env").write_text("APP_KEY=asli\n")
            (root / "public" / "index.php").write_text("<?php // lama\n")

            archive = Path(temp_dir) / "build.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("artisan", "#!/usr/bin/env php\n")
                zf.writestr("app/Models/User.php", "<?php class User {}\n")
                zf.writestr("public/index.php", "<?php // baru\n")
                zf.writestr("public/build/manifest.json", "{}")
                zf.writestr(".env", "APP_KEY=dari-arsip\n")  # harus ditolak
                zf.writestr("storage/logs/laravel.log", "x")  # harus ditolak

            result = self._run(root, archive)

            # `.env` berisi entri terlarang -> seluruh arsip ditolak utuh.
            self.assertIn("Unsafe archive entry", result.stdout, result.stdout + result.stderr)
            self.assertEqual((root / ".env").read_text(), "APP_KEY=asli\n")
            self.assertEqual((root / "public" / "index.php").read_text(), "<?php // lama\n")

    def test_clean_archive_extracts_and_cleans_staging(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "jejaka500" / "api"
            (root / "public").mkdir(parents=True)

            archive = Path(temp_dir) / "build.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("artisan", "#!/usr/bin/env php\n")
                zf.writestr("app/Models/User.php", "<?php class User {}\n")
                zf.writestr("public/index.php", "<?php // baru\n")
                zf.writestr("public/build/manifest.json", "{}")

            result = self._run(root, archive)

            self.assertIn("OK extracted=", result.stdout, result.stdout + result.stderr)
            self.assertEqual((root / "artisan").read_text(), "#!/usr/bin/env php\n")
            self.assertTrue((root / "app" / "Models" / "User.php").is_file())
            # Docroot Laravel menerima isi `public/`, bukan `index.php` di app root.
            self.assertEqual((root / "public" / "index.php").read_text(), "<?php // baru\n")
            self.assertFalse((root / "index.php").exists(), "tidak boleh ada index.php di app root")
            # Staging dibersihkan agar sinkronisasi FTP berikutnya tidak menyalinnya.
            staging = root / "storage" / "cpanel-deploy" / "staging"
            self.assertFalse(staging.exists(), "staging harus dibersihkan")

    def test_tampered_archive_is_rejected(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "jejaka500" / "api"
            (root / "public").mkdir(parents=True)

            archive = Path(temp_dir) / "build.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("artisan", "asli\n")

            # Hitung hash dari isi ASLI, lalu ubah arsipnya sebelum dikirim.
            original_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("artisan", "berubah\n")

            deploy_dir = root / "storage" / "cpanel-deploy"
            deploy_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(LIB, deploy_dir / "deploy-lib.php")

            result = subprocess.run(
                [
                    "php",
                    "-r",
                    RUNNER,
                    root.as_posix(),
                    archive.as_posix(),
                    original_sha,
                    HANDLER.as_posix(),
                    (deploy_dir / "cpanel-deploy-handler.php").as_posix(),
                ],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=root,
            )

            combined = result.stdout + result.stderr
            self.assertNotIn("OK extracted=", combined, f"arsip rusak tidak boleh diekstrak: {combined}")
            self.assertIn("checksum", combined.lower(), combined)
            self.assertFalse((root / "artisan").exists(), "tidak boleh ada berkas yang ditulis")