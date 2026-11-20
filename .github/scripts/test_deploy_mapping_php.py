"""Tes perilaku pemetaan tujuan deploy, dijalankan lewat PHP CLI.

Memuat `deploy-lib.php` — sumber yang sama yang dipakai handler produksi —
sehingga tes mengunci perilaku nyata, bukan salinan logika.

Kesalahan tata letak paling mahal: `public/*` mendarat di tempat yang tidak
dilayani web. Pengukuran 2026-11-20 menunjukkan `api/public/` adalah docroot
Laravel efektif (request `/api/...` di-rewrite ke `api/public/index.php`).
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[2] / "backend" / "deploy-cpanel" / "deploy-lib.php"

HARNESS = r"""require $argv[1];

$cases = json_decode($argv[2], true);
$out = [];
foreach ($cases as $case) {
    $result = resolve_destination($case, '/srv/api/public', '/srv/api');
    $out[$case] = [
        'allowed' => $result !== null,
        'base' => $result === null ? null : ($result[0] === '/srv/api/public' ? 'public' : 'app-root'),
        'relative' => $result === null ? null : $result[1],
    ];
}
echo json_encode($out);
"""


@unittest.skipIf(shutil.which("php") is None, "PHP CLI tidak tersedia")
class DestinationMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cases = [
            "public/index.php",
            "public/.htaccess",
            "public/build/manifest.json",
            "artisan",
            "app/Models/User.php",
            "vendor/autoload.php",
            "routes/web.php",
            ".env",
            "storage/logs/laravel.log",
            "bootstrap/cache/config.php",
            "php.ini",
            ".user.ini",
            ".htaccess",
            "public/cpanel-deploy.php",
            "../escape.php",
            "app/../../escape.php",
            "/absolute.php",
            "public",
        ]

        result = subprocess.run(
            ["php", "-r", HARNESS, LIB.as_posix(), json.dumps(cases)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            raise AssertionError(f"PHP harness gagal: {result.stderr.strip()}")

        cls.mapping = json.loads(result.stdout)

    def test_public_assets_go_to_laravel_docroot(self):
        for name in ["public/index.php", "public/.htaccess", "public/build/manifest.json"]:
            with self.subTest(name=name):
                entry = self.mapping[name]
                self.assertTrue(entry["allowed"])
                self.assertEqual(entry["base"], "public")
                self.assertEqual(entry["relative"], name[len("public/"):])

    def test_application_code_goes_to_app_root(self):
        for name in ["artisan", "app/Models/User.php", "vendor/autoload.php", "routes/web.php"]:
            with self.subTest(name=name):
                entry = self.mapping[name]
                self.assertTrue(entry["allowed"])
                self.assertEqual(entry["base"], "app-root")
                self.assertEqual(entry["relative"], name)

    def test_public_htaccess_is_deployed_but_root_htaccess_is_not(self):
        # `public/.htaccess` milik Laravel dan memang harus ikut ter-deploy.
        self.assertTrue(self.mapping["public/.htaccess"]["allowed"])
        # `.htaccess` root mengatur routing SPA; menimpanya akan mematikan situs.
        self.assertFalse(self.mapping[".htaccess"]["allowed"])

    def test_secrets_runtime_state_and_helpers_are_refused(self):
        for name in [
            ".env",
            "storage/logs/laravel.log",
            "bootstrap/cache/config.php",
            "php.ini",
            ".user.ini",
            "public/cpanel-deploy.php",
            "../escape.php",
            "app/../../escape.php",
            "/absolute.php",
            "public",
        ]:
            with self.subTest(name=name):
                self.assertFalse(self.mapping[name]["allowed"], f"{name} harus ditolak")


if __name__ == "__main__":
    unittest.main()
