import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

test('navigateFallbackDenylist excludes both /api/ and /admin routes from SPA fallback', () => {
  const content = readFileSync(new URL('../vite.config.ts', import.meta.url), 'utf-8');
  const match = content.match(/navigateFallbackDenylist:\s*(\[[^\]]+\])/);
  assert.ok(match, 'navigateFallbackDenylist should be defined in vite.config.ts');

  const patterns = [...match[1].matchAll(/\/((?:\\.|[^/])*)\/([a-z]*)/g)].map(
    ([, source, flags]) => new RegExp(source, flags)
  );
  assert.ok(patterns.length > 0, 'at least one denylist pattern should be configured');

  const shouldBeExcluded = [
    '/api',
    '/api/price-categories',
    '/api/register',
    '/api/midtrans/notification',
    '/admin',
    '/admin/',
    '/admin/login',
    '/admin/registrations',
    '/admin/filament/assets/app.js',
    '/livewire/livewire.js',
    '/livewire/update',
    '/up',
  ];

  for (const path of shouldBeExcluded) {
    const isExcluded = patterns.some((p) => p.test(path));
    assert.strictEqual(
      isExcluded,
      true,
      `Expected path "${path}" to be excluded by navigateFallbackDenylist but it was not`
    );
  }

  const shouldNotBeExcluded = [
    '/',
    '/index.html',
    '/pendaftaran',
    '/status',
    '/kontribusi',
    '/administrator-not-admin',
  ];

  for (const path of shouldNotBeExcluded) {
    const isExcluded = patterns.some((p) => p.test(path));
    assert.strictEqual(
      isExcluded,
      false,
      `Expected SPA route "${path}" to NOT be excluded by navigateFallbackDenylist but it was matched`
    );
  }
});
