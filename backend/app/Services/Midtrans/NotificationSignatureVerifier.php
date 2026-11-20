<?php

namespace App\Services\Midtrans;

final class NotificationSignatureVerifier
{
    /**
     * @param  array<string, mixed>  $payload
     */
    public function isAuthentic(array $payload): bool
    {
        $signatureKey = $payload['signature_key'] ?? null;
        $orderId = $payload['order_id'] ?? null;
        $statusCode = $payload['status_code'] ?? null;
        $grossAmount = $payload['gross_amount'] ?? null;
        $verificationKey = config('midtrans.signature_secret_key') ?: config('midtrans.server_key');

        if (! is_string($signatureKey) || $signatureKey === '' || ! is_string($verificationKey) || $verificationKey === '') {
            return false;
        }

        if ($orderId === null || $statusCode === null || $grossAmount === null) {
            return false;
        }

        $orderId = (string) $orderId;
        $statusCode = (string) $statusCode;
        $grossAmount = (string) $grossAmount;

        $expected = hash('sha512', $orderId.$statusCode.$grossAmount.$verificationKey);

        return hash_equals(strtolower($expected), strtolower($signatureKey));
    }
}
