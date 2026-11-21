<?php

return [
    'merchant_id' => env('MIDTRANS_MERCHANT_ID'),
    'client_key' => env('MIDTRANS_CLIENT_KEY'),
    'server_key' => env('MIDTRANS_SERVER_KEY'),
    'signature_secret_key' => env('MIDTRANS_SIGNATURE_SECRET_KEY'),
    'is_production' => filter_var(env('MIDTRANS_IS_PRODUCTION', false), FILTER_VALIDATE_BOOLEAN),
    /**
     * URL webhook yang dikirim di payload Snap (`callbacks.notification_url`).
     *
     * Tanpa ini, transaksi yang dibuat lewat Snap API mengirim notifikasi ke
     * endpoint default Midtrans (`<snap-base>/snap/v1/notification`), bukan ke
     * backend kita — terukur 2026-11-21 pada akun Sandbox JEJAKA500. Dashboard
     * Midtrans hanya berlaku untuk transaksi yang dibuat lewat UI mereka.
     */
    'notification_url' => env('MIDTRANS_NOTIFICATION_URL'),
    /** Halaman yang dibuka pembeli setelah pembayaran selesai (`callbacks.finish`). */
    'finish_redirect_url' => env('MIDTRANS_FINISH_REDIRECT_URL'),
    /**
     * Set true di production. Di Mac/Homebrew kadang file CA bundle hilang sehingga cURL error
     * "error adding trust anchors from file" — sementara bisa false hanya di lokal.
     */
    'verify_ssl' => filter_var(env('MIDTRANS_SSL_VERIFY', true), FILTER_VALIDATE_BOOLEAN),
    /** Path opsional ke cacert.pem (mis. unduh dari https://curl.se/ca/cacert.pem). */
    'cainfo' => env('MIDTRANS_CAINFO'),
];
