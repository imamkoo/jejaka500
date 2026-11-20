<?php

use App\Models\District;
use App\Models\Registration;
use App\Services\Midtrans\NotificationSignatureVerifier;

it('verifies signature using signature_secret_key when configured', function () {
    config()->set('midtrans.signature_secret_key', 'secret-key-xyz');
    config()->set('midtrans.server_key', 'server-key-abc');

    $orderId = 'ORDER-TEST-001';
    $statusCode = '200';
    $grossAmount = '50000';
    $validSignature = hash('sha512', $orderId.$statusCode.$grossAmount.'secret-key-xyz');

    $verifier = new NotificationSignatureVerifier();

    expect($verifier->isAuthentic([
        'order_id' => $orderId,
        'status_code' => $statusCode,
        'gross_amount' => $grossAmount,
        'signature_key' => $validSignature,
    ]))->toBeTrue();

    $oldKeySignature = hash('sha512', $orderId.$statusCode.$grossAmount.'server-key-abc');
    expect($verifier->isAuthentic([
        'order_id' => $orderId,
        'status_code' => $statusCode,
        'gross_amount' => $grossAmount,
        'signature_key' => $oldKeySignature,
    ]))->toBeFalse();
});

it('falls back to server_key when signature_secret_key is empty for legacy compatibility', function () {
    config()->set('midtrans.signature_secret_key', null);
    config()->set('midtrans.server_key', 'legacy-server-key-123');

    $orderId = 'ORDER-LEGACY-002';
    $statusCode = '200';
    $grossAmount = '20000';
    $validLegacySignature = hash('sha512', $orderId.$statusCode.$grossAmount.'legacy-server-key-123');

    $verifier = new NotificationSignatureVerifier();

    expect($verifier->isAuthentic([
        'order_id' => $orderId,
        'status_code' => $statusCode,
        'gross_amount' => $grossAmount,
        'signature_key' => $validLegacySignature,
    ]))->toBeTrue();
});

it('processes midtrans notification successfully when signature_secret_key is set', function () {
    config()->set('midtrans.signature_secret_key', 'secret-webhook-key-999');
    config()->set('midtrans.server_key', 'server-api-key-111');

    $district = District::query()->create([
        'name' => 'Gambir',
        'code' => '310003',
    ]);

    $registrationResponse = $this->postJson('/api/register', [
        'district_id' => $district->id,
        'education_level' => 'SMA',
        'edition' => 'reguler',
        'name' => 'Fauzan Hakim',
        'phone_number' => '6281234567891',
        'school_name' => 'SMAN 1 Jakarta',
    ])->assertCreated();

    $code = $registrationResponse->json('data.registration_code');
    $total = (string) $registrationResponse->json('data.financial.total_payment');

    $signature = hash('sha512', $code.'200'.$total.'secret-webhook-key-999');

    $this->postJson('/api/midtrans/notification', [
        'order_id' => $code,
        'status_code' => '200',
        'gross_amount' => $total,
        'transaction_status' => 'settlement',
        'signature_key' => $signature,
    ])
        ->assertSuccessful()
        ->assertJsonPath('success', true);

    expect(Registration::query()->where('registration_code', $code)->value('payment_status'))->toBe('success');
});
