<?php

/**
 * Handler deploy cPanel — berjalan DI LUAR docroot.
 *
 * Berkas ini dipasang di `api/storage/cpanel-deploy/` sehingga request web
 * tidak dapat menjangkaunya. `api/public/cpanel-deploy.php` hanya shim tiga
 * baris yang memuatnya.
 *
 * Mengapa harus di luar docroot: pengukuran 2026-11-20 membuktikan
 * `GET /api/public/deploy-extract.php` mengembalikan 405 — PHP di `api/public/`
 * **dieksekusi langsung lewat web**, melewati front controller Laravel. Endpoint
 * yang hanya mengandalkan tanda tangan di direktori itu menambah permukaan
 * serangan yang tidak perlu.
 *
 * Tata letak server (terukur, bukan asumsi):
 *
 *   /jejaka500/            docroot web (SPA: index.html, assets/, sw.js)
 *   /jejaka500/api/        app root Laravel
 *   /jejaka500/api/public/ direktori biasa di dalam docroot, bukan docroot
 *
 * `.htaccess` root meng-rewrite `^api` ke `api/public/index.php`, dan Filament
 * memakai URL aset top-level (`/css`, `/js`, `/fonts/filament`, `/storage`).
 *
 * Keamanan: HMAC `sha256(secret, timestamp:nonce:archive_sha256)`, secret di
 * `deploy-secret.txt` (0600, di luar docroot), jendela 600 detik, nonce sekali
 * pakai, dan seluruh entri arsip divalidasi sebelum satu berkas pun ditulis.
 */

declare(strict_types=1);

error_reporting(E_ALL);
ini_set('display_errors', '0');
ini_set('log_errors', '1');

if (! is_file(__DIR__.'/deploy-lib.php')) {
    // Tanpa pesan jelas, `require` menghasilkan fatal error yang menyesatkan.
    http_response_code(503);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'deploy-lib.php tidak ditemukan di '.__DIR__."\n";
    echo "Unggah deploy-lib.php ke folder yang sama dengan handler ini.\n";

    exit;
}

require __DIR__.'/deploy-lib.php';

// `__DIR__` = tempat handler dipasang (`api/storage/cpanel-deploy`).
const DEPLOY_DIR = __DIR__;
const APP_ROOT_DIR = __DIR__.'/../..';
const ENTRY_DIR = APP_ROOT_DIR.'/public';

const DEPLOY_SECRET_FILE = DEPLOY_DIR.'/deploy-secret.txt';
const DEPLOY_NONCE_DIR = DEPLOY_DIR.'/nonces';
const DEPLOY_STAGING_DIR = DEPLOY_DIR.'/staging';

const MAX_CHUNK_BYTES = 8 * 1024 * 1024;
const MAX_TOTAL_BYTES = 400 * 1024 * 1024;

function respond(int $status, string $message): never
{
    http_response_code($status);
    header('Content-Type: text/plain; charset=utf-8');
    echo $message."\n";
    exit;
}

function stderr_write(string $message): void
{
    $stream = fopen('php://stderr', 'wb');
    if ($stream !== false) {
        fwrite($stream, $message."\n");
        fclose($stream);
    }
}

function remove_directory(string $directory): void
{
    if (! is_dir($directory)) {
        return;
    }

    foreach (scandir($directory) ?: [] as $entry) {
        if ($entry === '.' || $entry === '..') {
            continue;
        }
        $path = $directory.'/'.$entry;
        is_dir($path) ? remove_directory($path) : @unlink($path);
    }

    @rmdir($directory);
}

/**
 * Buat secret HMAC baru. Hanya lewat CLI; menolak bila secret sudah ada.
 */
function generate_secret(): never
{
    if (is_file(DEPLOY_SECRET_FILE)) {
        stderr_write('Secret sudah ada di '.DEPLOY_SECRET_FILE."\n"
            ."Hapus berkas itu lebih dulu bila memang ingin merotasi, lalu perbarui\n"
            .'secret GitHub CPANEL_DEPLOY_SECRET.');
        exit(1);
    }

    if (! is_dir(DEPLOY_DIR) && ! mkdir(DEPLOY_DIR, 0o755, true) && ! is_dir(DEPLOY_DIR)) {
        stderr_write('Tidak bisa membuat direktori '.DEPLOY_DIR);
        exit(1);
    }

    $secret = bin2hex(random_bytes(32));
    if (file_put_contents(DEPLOY_SECRET_FILE, $secret."\n") === false) {
        stderr_write('Tidak bisa menulis '.DEPLOY_SECRET_FILE);
        exit(1);
    }
    chmod(DEPLOY_SECRET_FILE, 0o600);

    echo $secret."\n";
    exit;
}

if (PHP_SAPI === 'cli') {
    if (in_array('--generate-secret', $_SERVER['argv'] ?? [], true)) {
        generate_secret();
    }

    stderr_write("Bukan untuk dijalankan langsung.\n"
        .'Buat secret: php '.DEPLOY_DIR.'/cpanel-deploy-handler.php --generate-secret');
    exit(1);
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    respond(405, 'POST required');
}

$secret = is_file(DEPLOY_SECRET_FILE)
    ? trim((string) file_get_contents(DEPLOY_SECRET_FILE))
    : '';

$archiveShaHeader = strtolower((string) ($_SERVER['HTTP_X_DEPLOY_SHA256'] ?? ''));
$verification = verify_signature(
    $secret,
    (string) ($_SERVER['HTTP_X_DEPLOY_TIMESTAMP'] ?? ''),
    (string) ($_SERVER['HTTP_X_DEPLOY_NONCE'] ?? ''),
    $archiveShaHeader,
    (string) ($_SERVER['HTTP_X_DEPLOY_SIGNATURE'] ?? ''),
    DEPLOY_NONCE_DIR
);

if (! $verification['ok']) {
    error_log('[cpanel-deploy] auth ditolak: '.$verification['reason']);
    respond(403, 'Forbidden');
}

if (! isset($_FILES['chunk']) || ! is_uploaded_file($_FILES['chunk']['tmp_name'])) {
    respond(400, 'Missing chunk upload');
}

$upload = $_FILES['chunk'];
if (($upload['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK) {
    respond(400, 'Upload error code '.$upload['error']);
}
if (($upload['size'] ?? 0) > MAX_CHUNK_BYTES) {
    respond(413, 'Chunk too large');
}

$index = (int) ($_POST['index'] ?? -1);
$total = (int) ($_POST['total'] ?? 0);
$expectedSha = strtolower((string) ($_SERVER['HTTP_X_DEPLOY_CHUNK_SHA256'] ?? ''));
$actualSha = hash_file('sha256', $upload['tmp_name']);

if ($index < 0 || $total <= 0 || $index >= $total) {
    respond(422, 'Invalid chunk index');
}
if ($expectedSha === '' || ! hash_equals($expectedSha, $actualSha)) {
    respond(422, 'Chunk checksum mismatch');
}

if (! is_dir(DEPLOY_STAGING_DIR)
    && ! mkdir(DEPLOY_STAGING_DIR, 0o700, true)
    && ! is_dir(DEPLOY_STAGING_DIR)) {
    respond(500, 'Cannot create staging directory');
}

$partPath = sprintf('%s/part%04d', DEPLOY_STAGING_DIR, $index);
if (! move_uploaded_file($upload['tmp_name'], $partPath)) {
    respond(500, 'Cannot store chunk');
}
chmod($partPath, 0o644);

$received = count(glob(DEPLOY_STAGING_DIR.'/part*') ?: []);
if ($received < $total) {
    respond(202, sprintf('Accepted chunk %d/%d', $index + 1, $total));
}

// Semua bagian lengkap: gabungkan sesuai urutan index.
$combined = DEPLOY_STAGING_DIR.'/archive.zip';
$handle = fopen($combined, 'wb');
if ($handle === false) {
    remove_directory(DEPLOY_STAGING_DIR);
    respond(500, 'Cannot create combined archive');
}

$totalBytes = 0;
for ($part = 0; $part < $total; $part++) {
    $partPath = sprintf('%s/part%04d', DEPLOY_STAGING_DIR, $part);
    if (! is_file($partPath)) {
        fclose($handle);
        remove_directory(DEPLOY_STAGING_DIR);
        respond(422, 'Missing chunk '.$part);
    }

    $chunkHandle = fopen($partPath, 'rb');
    stream_copy_to_stream($chunkHandle, $handle);
    fclose($chunkHandle);

    $totalBytes += filesize($partPath);
    if ($totalBytes > MAX_TOTAL_BYTES) {
        fclose($handle);
        remove_directory(DEPLOY_STAGING_DIR);
        respond(413, 'Archive too large');
    }
}
fclose($handle);

if ($archiveShaHeader === '' || ! hash_equals($archiveShaHeader, hash_file('sha256', $combined))) {
    remove_directory(DEPLOY_STAGING_DIR);
    respond(422, 'Archive checksum mismatch');
}

$zip = new ZipArchive;
if ($zip->open($combined) !== true) {
    remove_directory(DEPLOY_STAGING_DIR);
    respond(422, 'Archive is not a readable ZIP');
}

if (realpath(ENTRY_DIR) === false || realpath(APP_ROOT_DIR) === false) {
    $zip->close();
    remove_directory(DEPLOY_STAGING_DIR);
    respond(500, 'Target directory unavailable');
}

// Validasi seluruh entri SEBELUM menulis satu file pun.
$plan = [];
for ($entry = 0; $entry < $zip->numFiles; $entry++) {
    $name = (string) $zip->getNameIndex($entry);
    $normalized = str_replace('\\', '/', ltrim($name, '/'));

    $destination = resolve_destination($normalized, ENTRY_DIR, APP_ROOT_DIR);
    if ($destination === null) {
        if ($normalized === 'public' || $normalized === '') {
            continue; // entri direktori
        }

        $zip->close();
        remove_directory(DEPLOY_STAGING_DIR);
        respond(422, 'Unsafe archive entry: '.$name);
    }

    [$base, $relative] = $destination;
    $plan[] = [$entry, $base.'/'.$relative];
}

$extracted = 0;
$written = 0;
foreach ($plan as [$entry, $destination]) {
    $directory = dirname($destination);

    if (! is_dir($directory) && ! mkdir($directory, 0o755, true) && ! is_dir($directory)) {
        $zip->close();
        remove_directory(DEPLOY_STAGING_DIR);
        respond(500, 'Cannot create directory: '.$directory);
    }

    $stream = $zip->getStream($zip->getNameIndex($entry));
    if ($stream === false) {
        $zip->close();
        remove_directory(DEPLOY_STAGING_DIR);
        respond(500, 'Cannot read archive entry: '.$destination);
    }

    $bytes = file_put_contents($destination, $stream);
    fclose($stream);

    if ($bytes === false) {
        $zip->close();
        remove_directory(DEPLOY_STAGING_DIR);
        respond(500, 'Cannot write file: '.$destination);
    }

    chmod($destination, 0o644);
    $written += $bytes;
    $extracted++;
}

$zip->close();
remove_directory(DEPLOY_STAGING_DIR);

respond(200, sprintf(
    'OK extracted=%d written=%d archive_bytes=%d sha256=%s',
    $extracted,
    $written,
    $totalBytes,
    $archiveShaHeader
));
