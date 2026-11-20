<?php

/**
 * Generator secret HMAC untuk `deploy-extract.php`.
 *
 * Jalankan SEKALI lewat Terminal cPanel:
 *
 *     php ~/followtheline.id/jejaka500/api/public/deploy-secret.php
 *
 * Perintah mencetak satu secret acak 64 hex. Simpan keluaran itu sebagai
 * secret GitHub `CPANEL_DEPLOY_SECRET`. Secret juga ditulis ke
 * `storage/framework/deploy-secret.txt` (di luar docroot, tidak bisa diakses
 * web) untuk dipakai server.
 *
 * Berbeda dari token sekali pakai, secret ini bertahan: dipakai untuk
 * menandatangani setiap deploy, jadi tidak perlu membuat ulang tiap kali.
 *
 * Menjalankan ulang perintah ini akan MEROTASI secret — server langsung
 * menolak tanda tangan lama. Setelah rotasi, perbarui secret GitHub.
 */

declare(strict_types=1);

const SECRET_PATH = __DIR__.'/../storage/framework/deploy-secret.txt';

$directory = dirname(SECRET_PATH);
if (! is_dir($directory) && ! mkdir($directory, 0o755, true) && ! is_dir($directory)) {
    fwrite(STDERR, "Tidak bisa membuat direktori: {$directory}\n");
    exit(1);
}

if (is_file(SECRET_PATH)) {
    fwrite(
        STDERR,
        "Secret sudah ada di {$SECRET_PATH}.\n".
        "Menjalankan ulang akan merotasi secret dan membuat deploy gagal\n".
        "sampai CPANEL_DEPLOY_SECRET di GitHub diperbarui.\n".
        "Hapus file itu lebih dulu bila memang ingin merotasi.\n"
    );
    exit(1);
}

$secret = bin2hex(random_bytes(32));

if (file_put_contents(SECRET_PATH, $secret."\n") === false) {
    fwrite(STDERR, "Tidak bisa menulis secret ke {$SECRET_PATH}\n");
    exit(1);
}

chmod(SECRET_PATH, 0o600);

echo $secret."\n";
