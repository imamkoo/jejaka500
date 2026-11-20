"""Tes tanda tangan deploy berbasis HMAC (opsi B).

Menggantikan token sekali pakai yang harus dibuat manual di server tiap deploy.
Workflow menandatangani (secret, timestamp, nonce) dan server memverifikasinya
dengan secret yang sama. Secret tidak pernah dikirim lewat jaringan.

Format tanda tangan:

    message = f"{timestamp}:{nonce}:{archive_sha256}"
    signature = hex(hmac_sha256(secret, message))

Aturan yang dijaga:
- Timestamp basi (di luar jendela) ditolak, supaya tanda tangan yang bocor
  lewat log tidak bisa dipakai ulang.
- Nonce sekali pakai, supaya replay dalam jendela waktu tetap ditolak.
- Secret tidak pernah masuk ke header.
"""

import hashlib
import hmac
import unittest

from upload_chunks import (
    SIGNATURE_WINDOW_SECONDS,
    build_signature,
    sign_headers,
)


class SignatureTests(unittest.TestCase):
    def test_window_is_short_enough_to_limit_replay(self):
        self.assertLessEqual(SIGNATURE_WINDOW_SECONDS, 15 * 60)
        self.assertGreaterEqual(SIGNATURE_WINDOW_SECONDS, 60)

    def test_signature_is_hmac_sha256_of_timestamp_nonce_and_archive(self):
        secret = "s3cret-value"
        timestamp = "1700000000"
        nonce = "abc123"
        archive = "f" * 64

        expected = hmac.new(
            secret.encode(), f"{timestamp}:{nonce}:{archive}".encode(), hashlib.sha256
        ).hexdigest()

        self.assertEqual(build_signature(secret, timestamp, nonce, archive), expected)

    def test_signature_changes_with_every_input(self):
        args = ["secret-a", "1700000000", "nonce", "f" * 64]
        base = build_signature(*args)

        self.assertNotEqual(base, build_signature("secret-b", *args[1:]))
        self.assertNotEqual(base, build_signature(args[0], "1700000001", *args[2:]))
        self.assertNotEqual(base, build_signature(args[0], args[1], "other", args[3]))
        self.assertNotEqual(base, build_signature(*args[:3], "0" * 64))

    def test_headers_never_contain_the_secret(self):
        secret = "super-secret-do-not-leak"
        headers = sign_headers(
            secret, timestamp="1700000000", nonce="n1", archive_sha256="f" * 64
        )

        for name, value in headers.items():
            self.assertNotIn(secret, value, f"{name} membocorkan secret")
            self.assertNotIn(secret, name)

        self.assertIn("X-Deploy-Timestamp", headers)
        self.assertIn("X-Deploy-Nonce", headers)
        self.assertIn("X-Deploy-Signature", headers)

    def test_nonce_is_unique_per_call(self):
        signatures = {
            sign_headers("s", timestamp="1700000000", nonce=None, archive_sha256="f" * 64)[
                "X-Deploy-Nonce"
            ]
            for _ in range(20)
        }
        self.assertEqual(len(signatures), 20, "nonce harus unik tiap pemanggilan")

    def test_rejects_empty_secret(self):
        with self.assertRaises(ValueError):
            build_signature("", "1700000000", "n", "f" * 64)


if __name__ == "__main__":
    unittest.main()
