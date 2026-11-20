<?php

/**
 * Fungsi murni untuk deploy cPanel: pemetaan tujuan dan verifikasi tanda tangan.
 *
 * Dipisahkan dari handler supaya tes bisa memuat berkas ini langsung (tanpa
 * `eval()`, yang tidak sah bersama `declare(strict_types=1)`) dan tanpa
 * mengeksekusi alur request.
 *
 * Berkas ini tidak boleh melakukan I/O atau mengeluarkan output saat dimuat.
 */

declare(strict_types=1);

// Toleransi clock skew antara server dan runner GitHub.
const SIGNATURE_WINDOW_SECONDS = 600;

// Artefak deploy tidak boleh menimpa rahasia, state runtime, atau konfigurasi
// server. `.htaccess` root (routing SPA) TIDAK boleh tertimpa; sebaliknya
// `public/.htaccess` milik Laravel memang harus ikut ter-deploy.
const FORBIDDEN_PATHS = [
    '.env',
    'storage/',
    'bootstrap/cache/config.php',
    'php.ini',
    '.user.ini',
    '.htaccess',
];

// Shim dan handler tidak ikut diganti agar deploy tidak menimpa dirinya sendiri.
const FORBIDDEN_EXACT = [
    'public/cpanel-deploy.php',
];

const PUBLIC_PREFIX = 'public/';

/**
 * Petakan nama entri arsip ke (direktori tujuan, path relatif).
 *
 * @param  string  $entryDir  Docroot Laravel (`api/public`).
 * @param  string  $appRoot  App root Laravel (`api`).
 * @return array{0: string, 1: string}|null null bila entri tidak boleh ditulis
 */
function resolve_destination(string $normalized, string $entryDir, string $appRoot): ?array
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
        return [$entryDir, substr($normalized, strlen(PUBLIC_PREFIX))];
    }

    return [$appRoot, $normalized];
}

/**
 * Verifikasi tanda tangan HMAC.
 *
 * @return array{ok: bool, reason: string}
 */
function verify_signature(
    string $secret,
    string $timestamp,
    string $nonce,
    string $archiveSha,
    string $signature,
    string $nonceDir,
    ?int $now = null
): array {
    if ($secret === '') {
        return ['ok' => false, 'reason' => 'server secret missing'];
    }
    if ($signature === '' || $nonce === '' || $timestamp === '') {
        return ['ok' => false, 'reason' => 'missing signature'];
    }
    if (! ctype_digit($timestamp)) {
        return ['ok' => false, 'reason' => 'bad timestamp'];
    }

    $now = $now ?? time();
    if (abs($now - (int) $timestamp) > SIGNATURE_WINDOW_SECONDS) {
        return ['ok' => false, 'reason' => 'expired'];
    }

    $expected = hash_hmac('sha256', $timestamp.':'.$nonce.':'.$archiveSha, $secret);
    if (! hash_equals($expected, strtolower($signature))) {
        return ['ok' => false, 'reason' => 'bad signature'];
    }

    // Nonce sekali pakai: replay dalam jendela waktu tetap ditolak meski
    // tanda tangan sah. File penanda berumur sama dengan jendela waktu.
    if (! is_dir($nonceDir)
        && ! mkdir($nonceDir, 0o700, true)
        && ! is_dir($nonceDir)) {
        return ['ok' => false, 'reason' => 'nonce store unavailable'];
    }

    foreach (glob($nonceDir.'/*') ?: [] as $stale) {
        if (is_file($stale) && filemtime($stale) < $now - SIGNATURE_WINDOW_SECONDS * 2) {
            @unlink($stale);
        }
    }

    $marker = $nonceDir.'/'.hash('sha256', $nonce);
    // `x` gagal bila file sudah ada -> atomik, tanpa race antar request paralel.
    $handle = @fopen($marker, 'x');
    if ($handle === false) {
        return ['ok' => false, 'reason' => 'replayed nonce'];
    }
    fclose($handle);
    @chmod($marker, 0o600);

    return ['ok' => true, 'reason' => 'ok'];
}
