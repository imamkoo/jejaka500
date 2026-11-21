<?php

use App\Models\Registration;
use App\Services\Midtrans\SnapTokenService;
use Illuminate\Support\Facades\Http;

/**
 * Regresi 2026-11-21: transaksi Snap yang dibuat lewat API mengirim notifikasi
 * ke endpoint default Midtrans (`<snap-base>/snap/v1/notification`) karena
 * payload tidak memuat `callbacks.notification_url`. Akibatnya backend tidak
 * pernah menerima webhook dan `payment_status` tertahan di `pending`.
 */
function makePendingRegistration(): Registration
{
    return Registration::query()->create([
        'batch_id' => null,
        'district_id' => null,
        'education_level' => 'UMUM',
        'institution_type' => 'UMUM',
        'name' => 'Uji Callback',
        'phone_number' => '6281234567890',
        'school_name' => 'TEST',
        'registration_code' => 'TEST-CB-'.strtoupper(substr(md5((string) mt_rand()), 0, 6)),
        'page_number' => 1,
        'edition' => 'reguler',
        'base_price' => 20000,
        'total_payment' => 20000,
        'payment_status' => 'pending',
    ]);
}

it('sends callbacks.notification_url and callbacks.finish in the Snap payload', function () {
    config([
        'midtrans.notification_url' => 'https://example.test/api/midtrans/notification',
        'midtrans.finish_redirect_url' => 'https://example.test/booking/finished',
    ]);

    Http::fake([
        '*/snap/v1/transactions' => Http::response(['token' => 'snap-token-cb'], 200),
    ]);

    $registration = makePendingRegistration();

    (new SnapTokenService)->createTokenForRegistration($registration);

    Http::assertSent(function ($request) {
        $callbacks = $request->data()['callbacks'] ?? null;

        return $callbacks === [
            'finish' => 'https://example.test/booking/finished',
            'notification' => 'https://example.test/api/midtrans/notification',
        ];
    });
});

it('omits callbacks entirely when neither URL is configured', function () {
    config([
        'midtrans.notification_url' => null,
        'midtrans.finish_redirect_url' => null,
    ]);

    Http::fake([
        '*/snap/v1/transactions' => Http::response(['token' => 'snap-token-nocb'], 200),
    ]);

    (new SnapTokenService)->createTokenForRegistration(makePendingRegistration());

    Http::assertSent(function ($request) {
        return ! array_key_exists('callbacks', $request->data());
    });
});

it('still sends callbacks when only the notification URL is configured', function () {
    config([
        'midtrans.notification_url' => 'https://example.test/api/midtrans/notification',
        'midtrans.finish_redirect_url' => '   ',
    ]);

    Http::fake([
        '*/snap/v1/transactions' => Http::response(['token' => 'snap-token-one'], 200),
    ]);

    (new SnapTokenService)->createTokenForRegistration(makePendingRegistration());

    Http::assertSent(function ($request) {
        return ($request->data()['callbacks'] ?? null) === [
            'notification' => 'https://example.test/api/midtrans/notification',
        ];
    });
});
