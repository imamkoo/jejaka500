<?php

/**
 * Penerima arsip deploy untuk cPanel (mode bertahap).
 *
 * Server menolak body request di atas 8 MiB, sedangkan arsip backend ±43 MiB.
 * Karena itu workflow mengirim arsip sebagai beberapa bagian. Endpoint ini
 * menyimpan tiap bagian, lalu saat bagian terakhir tiba ia menggabungkan,
 * memverifikasi SHA-256, dan mengekstrak ke direktori tujuan.
 *
 * Tata letak tujuan (dipetakan dari Bash `rsync backend/ -> /api`):
 *
 *   /api/public/                isi `public/`  (index.php, .htaccess, build/, css/, js/)
 *   /api/                       seluruh kode    (app/, vendor/, artisan, routes/, ...)
 *
 * Keamanan:
 * - Token sekali pakai di `storage/framework/deploy-token.txt` (di luar docroot),
 *   dibuat lewat Terminal dengan `deploy-token.php`.
 * - Setiap entri arsip divalidasi sebelum satu file pun ditulis.
 * - `.env`, `storage/`, `bootstrap/cache/config.php`, dan helper deploy sendiri
 *   tidak pernah ditimpa.
 */

declare(strict_types=1);

// `rsync backend/ -> /api` menaruh app root Laravel di `/api` dan docroot di
// `/api/public`. Endpoint ini hidup di docroot, jadi app root adalah satu level
// di atasnya.
const APP_ROOT_DIR = __DIR__.'/..';
const PUBLIC_DIR = __DIR__;
const DEPLOY_TOKEN_FILE = APP_ROOT_DIR.'/storage/framework/deploy-token.txt';
const DEPLOY_STAGING_DIR = APP_ROOT_DIR.'/storage/framework/deploy-staging';

const PUBLIC_PREFIX = 'public/';
const MAX_CHUNK_BYTES = 8 * 1024 * 1024;
const MAX_TOTAL_BYTES = 400 * 1024 * 1024;

// Artefak deploy tidak boleh menimpa rahasia atau state runtime.
const FORBIDDEN_PATHS = [
    '.env',
    'storage/',
    'bootstrap/cache/config.php',
];

// Helper deploy tidak perlu ikut tergantikan; juga mencegah versi lain menimpa
// endpoint yang sedang dipakai.
const FORBIDDEN_EXACT = [
    'public/deploy-extract.php',
    'public/deploy-token.php',
];

function respond(int $status, string $message): never
{
    http_response_code($status);
    header('Content-Type: text/plain; charset=utf-8');
    echo $message."\n";
    exit;
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
 * Petakan nama entri arsip ke (direktori tujuan, path relatif).
 *
 * @return array{0: string, 1: string}|null null bila entri tidak boleh ditulis
 */
function resolve_destination(string $normalized): ?array
{
    if ($normalized === '' || str_contains($normalized, '..') || str_starts_with($normalized, '/')) {
        return null;
    }

    foreach (FORBIDDEN_PATHS as $forbidden) {
        if ($normalized === $forbidden || str_starts_with($normalized, $forbidden)) {
            return null;
        }
    }

    foreach (FORBIDDEN_EXACT as $blocked) {
        if ($normalized === $blocked) {
            return null;
        }
    }

    if ($normalized === 'public') {
        return null; // direktori, bukan berkas
    }

    if (str_starts_with($normalized, PUBLIC_PREFIX)) {
        return [PUBLIC_DIR, substr($normalized, strlen(PUBLIC_PREFIX))];
    }

    return [APP_ROOT_DIR, $normalized];
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    respond(405, 'POST required');
}

$providedToken = (string) ($_SERVER['HTTP_X_DEPLOY_TOKEN'] ?? '');
if ($providedToken === '' || ! is_file(DEPLOY_TOKEN_FILE)) {
    respond(403, 'Forbidden');
}

$expectedToken = trim((string) file_get_contents(DEPLOY_TOKEN_FILE));
if ($expectedToken === '' || ! hash_equals($expectedToken, $providedToken)) {
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
chmod($partPath, 0o600);

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

$archiveSha = strtolower((string) ($_SERVER['HTTP_X_DEPLOY_SHA256'] ?? ''));
if ($archiveSha === '' || ! hash_equals($archiveSha, hash_file('sha256', $combined))) {
    remove_directory(DEPLOY_STAGING_DIR);
    respond(422, 'Archive checksum mismatch');
}

$zip = new ZipArchive;
if ($zip->open($combined) !== true) {
    remove_directory(DEPLOY_STAGING_DIR);
    respond(422, 'Archive is not a readable ZIP');
}

$publicDir = realpath(PUBLIC_DIR);
$appRoot = realpath(APP_ROOT_DIR);
if ($publicDir === false || $appRoot === false) {
    $zip->close();
    remove_directory(DEPLOY_STAGING_DIR);
    respond(500, 'Target directory unavailable');
}

// Validasi seluruh entri SEBELUM menulis satu file pun.
$plan = [];
for ($entry = 0; $entry < $zip->numFiles; $entry++) {
    $name = (string) $zip->getNameIndex($entry);
    $normalized = str_replace('\\', '/', ltrim($name, '/'));

    $destination = resolve_destination($normalized);
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

// Token sekali pakai: habis setelah ekstraksi sukses.
@unlink(DEPLOY_TOKEN_FILE);

respond(200, sprintf(
    'OK extracted=%d written=%d archive_bytes=%d sha256=%s',
    $extracted,
    $written,
    $totalBytes,
    $archiveSha
));
