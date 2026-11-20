<?php

/**
 * Generator token sekali pakai untuk `deploy-extract.php`.
 *
 * Jalankan lewat Terminal cPanel:
 *
 *     php ~/jejaka500/api/public/deploy-token.php
 *
 * Token ditulis ke `storage/framework/deploy-token.txt` (di luar docroot) dan
 * hanya berlaku untuk satu kali ekstraksi. Setelah dipakai, `deploy-extract.php`
 * menghapusnya. Simpan output perintah ini di secret `CPANEL_DEPLOY_TOKEN`.
 */

declare(strict_types=1);

const TOKEN_PATH = __DIR__.'/../storage/framework/deploy-token.txt';

$directory = dirname(TOKEN_PATH);
if (! is_dir($directory) && ! mkdir($directory, 0o755, true) && ! is_dir($directory)) {
    fwrite(STDERR, "Tidak bisa membuat direktori: {$directory}\n");
    exit(1);
}

$token = bin2hex(random_bytes(32));

if (file_put_contents(TOKEN_PATH, $token."\n") === false) {
    fwrite(STDERR, "Tidak bisa menulis token ke {$TOKEN_PATH}\n");
    exit(1);
}

chmod(TOKEN_PATH, 0o600);

echo $token."\n";
