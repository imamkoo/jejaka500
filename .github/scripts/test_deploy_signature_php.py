"""Tes perilaku verifikasi tanda tangan di endpoint PHP (dijalankan lewat PHP CLI).

Menjalankan `verify_signature()` dari `deploy-extract.php` sungguhan untuk
memastikan server dan klien memakai perhitungan yang sama, serta menolak
replay dan tanda tangan basi.
"""

import hashlib
import hmac
import json
import secrets
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ENDPOINT = Path(__file__).resolve().parents[2] / "backend" / "public" / "deploy-extract.php"

HARNESS = r"""$source = file_get_contents($argv[1]);
$stripped = preg_replace('/^<\?php/', '', $source, 1);

$marker = 'if (($_SERVER[\'REQUEST_METHOD\']';
$position = strpos($stripped, $marker);
if ($position === false) {
    fwrite(STDERR, "marker not found\n");
    exit(2);
}

eval(substr($stripped, 0, $position));

// Arahkan penyimpanan nonce ke direktori sementara: tes tidak boleh menulis
// ke `backend/storage` milik repo (pernah menghapus berkas .gitignore).
define('TEST_NONCE_DIR', $argv[3]);

$cases = json_decode($argv[2], true);
$out = [];
foreach ($cases as $index => $case) {
    $result = verify_signature(
        $case['secret'],
        $case['timestamp'],
        $case['nonce'],
        $case['archive'],
        $case['signature'],
        $case['now'],
        TEST_NONCE_DIR
    );
    $out[] = $result;
}
echo json_encode($out);
"""


def signature(secret: str, timestamp: str, nonce: str, archive: str) -> str:
    message = f"{timestamp}:{nonce}:{archive}"
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


@unittest.skipIf(shutil.which("php") is None, "PHP CLI tidak tersedia")
class SignatureVerificationTests(unittest.TestCase):
    SECRET = "shared-secret-123"
    ARCHIVE = "a" * 64
    NOW = 1_700_000_000

    def _verify(self, cases: list[dict]) -> list[dict]:
        with TemporaryDirectory() as nonce_dir:
            result = subprocess.run(
                [
                    "php",
                    "-r",
                    HARNESS,
                    ENDPOINT.as_posix(),
                    json.dumps(cases),
                    str(Path(nonce_dir) / "deploy-nonces"),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
        if result.returncode != 0:
            raise AssertionError(f"PHP harness gagal: {result.stderr.strip()}")
        return json.loads(result.stdout)

    def _case(self, *, secret=None, timestamp=None, nonce=None, archive=None, sig=None, now=None):
        secret = secret or self.SECRET
        timestamp = str(timestamp if timestamp is not None else self.NOW)
        # Nonce unik per kasus: penanda nonce di server persisten, jadi nonce
        # tetap akan membuat tes gagal pada run kedua.
        nonce = nonce if nonce is not None else secrets.token_hex(8)
        archive = archive or self.ARCHIVE
        return {
            "secret": secret,
            "timestamp": timestamp,
            "nonce": nonce,
            "archive": archive,
            "signature": sig if sig is not None else signature(secret, timestamp, nonce, archive),
            "now": now if now is not None else self.NOW,
        }

    def test_accepts_valid_signature_from_python(self):
        results = self._verify([self._case()])
        self.assertTrue(results[0]["ok"], results[0])

    def test_rejects_tampered_archive_hash(self):
        case = self._case()
        case["archive"] = "b" * 64  # tanda tangan tetap milik arsip lama
        results = self._verify([case])
        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["reason"], "bad signature")

    def test_rejects_wrong_secret(self):
        case = self._case()
        case["secret"] = "secret-lain"
        results = self._verify([case])
        self.assertFalse(results[0]["ok"])

    def test_rejects_expired_timestamp(self):
        stale = self.NOW - 3600
        results = self._verify([self._case(timestamp=stale)])
        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["reason"], "expired")

    def test_rejects_timestamp_from_the_future(self):
        future = self.NOW + 3600
        results = self._verify([self._case(timestamp=future)])
        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["reason"], "expired")

    def test_rejects_replayed_nonce(self):
        case = self._case()
        results = self._verify([case, case])
        self.assertTrue(results[0]["ok"], results[0])
        self.assertFalse(results[1]["ok"])
        self.assertIn("replay", results[1]["reason"])

    def test_rejects_empty_secret_configuration(self):
        case = self._case(secret="")
        case["signature"] = signature("x", case["timestamp"], case["nonce"], case["archive"])
        results = self._verify([case])
        self.assertFalse(results[0]["ok"])

    def test_rejects_missing_signature(self):
        case = self._case(sig="")
        results = self._verify([case])
        self.assertFalse(results[0]["ok"])

    def test_rejects_non_numeric_timestamp(self):
        case = self._case()
        case["timestamp"] = "not-a-number"
        results = self._verify([case])
        self.assertFalse(results[0]["ok"])


if __name__ == "__main__":
    unittest.main()
