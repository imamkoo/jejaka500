<?php

use App\Models\District;
use App\Services\RegistrationService;

/**
 * JEJAKA500 dan GEMMA449 berbagi satu akun Midtrans (satu PT). Midtrans menyimpan
 * riwayat `order_id` secara global, jadi `registration_code` (yang dipakai sebagai
 * `order_id`) wajib punya namespace per produk.
 */
function makePrefixDistrict(string $name, string $code): District
{
    return District::query()->create([
        'name' => $name,
        'code' => $code,
    ]);
}

it('prefixes the smart code with the product prefix', function () {
    $district = makePrefixDistrict('Cilandak', '3171030');

    $registration = RegistrationService::register([
        'district_id' => $district->id,
        'education_level' => 'SMP',
        'edition' => 'reguler',
        'name' => 'Uji Prefix',
        'phone_number' => '6281000099801',
        'school_name' => 'SMPN 1 Cilandak',
    ]);

    expect($registration->registration_code)
        ->toStartWith(RegistrationService::ORDER_CODE_PREFIX.'-3171030-REGULER-SMP-');
});

it('keeps the random tail as the last segment so existing lookups still resolve', function () {
    $district = makePrefixDistrict('Gambir', '310003');

    $registration = RegistrationService::register([
        'district_id' => $district->id,
        'education_level' => 'SMA',
        'edition' => 'reguler',
        'name' => 'Uji Ekor',
        'phone_number' => '6281000099802',
        'school_name' => 'SMAN 1 Jakarta',
    ]);

    $code = $registration->registration_code;
    $tail = substr(strrchr($code, '-'), 1);

    expect($tail)->toHaveLength(4)
        ->and(preg_match('/^[A-Z0-9]{4}$/', $tail))->toBe(1);
});
