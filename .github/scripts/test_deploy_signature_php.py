"""Tes perilaku verifikasi tanda tangan HMAC (dijalankan lewat PHP CLI).

Memuat `deploy-lib.php` — sumber yang sama dengan handler produksi — sehingga
klien Python dan server PHP terbukti memakai perhitungan yang identik, dan
replay maupun tanda tangan basi benar-benar ditolak.
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from upload_chunks import build_signature

LIB = Path(__file__).resolve().parents[2] / "backend" / "deploy-cpanel" / "deploy-lib.php"

HARNESS = r"""require $argv[1];

$cases = json_decode($argv[2], true);
$out = [];
foreach ($cases as $case) {
    $out[] = verify_signature(
        $case['secret'],
        $case['timestamp'],
        $case['nonce'],
        $case['archive'],
        $case['signature'],
        $case['nonce_dir'],
        $case['now']
    );
}
echo json_encode($out);
"""


@unittest.skipIf(shutil.which("php") is None, "PHP CLI tidak tersedia")
class SignatureVerificationTests(unittest.TestCase):
    def _verify(self, cases):
        result = subprocess.run(
            ["php", "-r", HARNESS, LIB.as_posix(), json.dumps(cases)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr.strip())
        return json.loads(result.stdout)

    def test_python_signature_is_accepted_by_php(self):
        with TemporaryDirectory() as nonce_dir:
            cases = []
            for index in range(3):
                cases.append(
                    {
                        "secret": "s3cret",
                        "timestamp": "1700000000",
                        "nonce": f"nonce-{index}",
                        "archive": "a" * 64,
                        "signature": "",
                        "nonce_dir": nonce_dir,
                        "now": 1700000000,
                    }
                )
            for case in cases:
                case["signature"] = build_signature(
                    case["secret"], case["timestamp"], case["nonce"], case["archive"]
                )

            results = self._verify(cases)

            self.assertEqual([r["ok"] for r in results], [True, True, True], results)

    def test_replayed_nonce_is_rejected(self):
        with TemporaryDirectory() as nonce_dir:
            base = {
                "secret": "s3cret",
                "timestamp": "1700000000",
                "nonce": "same-nonce",
                "archive": "b" * 64,
                "nonce_dir": nonce_dir,
                "now": 1700000000,
            }
            base["signature"] = build_signature(
                base["secret"], base["timestamp"], base["nonce"], base["archive"]
            )

            results = self._verify([base, dict(base)])

            self.assertTrue(results[0]["ok"])
            self.assertFalse(results[1]["ok"])
            self.assertEqual(results[1]["reason"], "replayed nonce")

    def test_stale_timestamp_and_bad_signature_are_rejected(self):
        with TemporaryDirectory() as nonce_dir:
            stale = {
                "secret": "s3cret",
                "timestamp": "1700000000",
                "nonce": "stale",
                "archive": "c" * 64,
                "nonce_dir": nonce_dir,
                "now": 1700000000 + 601,
            }
            stale["signature"] = build_signature(
                stale["secret"], stale["timestamp"], stale["nonce"], stale["archive"]
            )

            forged = {
                "secret": "s3cret",
                "timestamp": "1700000000",
                "nonce": "forged",
                "archive": "d" * 64,
                "signature": "0" * 64,
                "nonce_dir": nonce_dir,
                "now": 1700000000,
            }

            results = self._verify([stale, forged])

            self.assertFalse(results[0]["ok"])
            self.assertEqual(results[0]["reason"], "expired")
            self.assertFalse(results[1]["ok"])
            self.assertEqual(results[1]["reason"], "bad signature")

    def test_missing_server_secret_rejects_everything(self):
        with TemporaryDirectory() as nonce_dir:
            case = {
                "secret": "",
                "timestamp": "1700000000",
                "nonce": "x",
                "archive": "e" * 64,
                "signature": build_signature("s3cret", "1700000000", "x", "e" * 64),
                "nonce_dir": nonce_dir,
                "now": 1700000000,
            }

            results = self._verify([case])

            self.assertFalse(results[0]["ok"])
            self.assertEqual(results[0]["reason"], "server secret missing")


if __name__ == "__main__":
    unittest.main()
