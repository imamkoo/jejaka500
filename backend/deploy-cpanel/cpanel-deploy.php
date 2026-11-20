<?php

/**
 * Shim endpoint deploy — memuat handler dari LUAR docroot.
 *
 * Seluruh logika (verifikasi HMAC, penggabungan potongan, ekstraksi) ada di
 * `api/storage/cpanel-deploy/cpanel-deploy-handler.php`, sehingga request web
 * tidak dapat menjangkau berkas aslinya.
 *
 * Berkas ini berada di `api/public/` karena hanya direktori itu yang
 * mengeksekusi PHP langsung — `.htaccess` root meng-rewrite `^api` ke
 * `api/public/index.php` untuk semua nama yang bukan berkas fisik.
 *
 * Endpoint: https://jejaka500.followtheline.id/api/public/cpanel-deploy.php
 */

declare(strict_types=1);

$handler = __DIR__.'/../storage/cpanel-deploy/cpanel-deploy-handler.php';

if (! is_file($handler)) {
    http_response_code(503);
    header('Content-Type: text/plain; charset=utf-8');
    echo "Deploy handler belum terpasang\n";
    exit;
}

require $handler;
