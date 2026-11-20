"""Tes perilaku pemetaan tujuan deploy, dijalankan lewat PHP CLI.

Mengeksekusi `resolve_destination()` dari `deploy-extract.php` sungguhan, bukan
mencocokkan teks sumber. Ini menangkap kesalahan tata letak yang paling mahal:
`public/index.php` yang mendarat sebagai `index.php` di app root akan menimpa
front controller SPA di docroot.
"""

import shutil
import subprocess
import unittest
from pathlib import Path

ENDPOINT = Path(__file__).resolve().parents[2] / "backend" / "public" / "deploy-extract.php"

# Memuat hanya deklarasi fungsi tanpa menjalankan alur request endpoint.
HARNESS = r"""$source = file_get_contents($argv[1]);
$stripped = preg_replace('/^<\?php/', '', $source, 1);

// Potong tepat sebelum alur request dimulai.
$marker = 'if (($_SERVER[\'REQUEST_METHOD\']';
$position = strpos($stripped, $marker);
if ($position === false) {
    fwrite(STDERR, "marker not found\n");
    exit(2);
}

eval(substr($stripped, 0, $position));

$cases = json_decode($argv[2], true);
$out = [];
foreach ($cases as $case) {
    $result = resolve_destination($case);
    $out[$case] = [
        'allowed' => $result !== null,
        'base' => $result === null ? null : ($result[0] === PUBLIC_DIR ? 'public' : 'app-root'),
        'relative' => $result === null ? null : $result[1],
    ];
}
echo json_encode($out);
"""


@unittest.skipIf(shutil.which("php") is None, "PHP CLI tidak tersedia")
class DestinationMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json

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
            "public/deploy-extract.php",
            "public/deploy-secret.php",
            "../escape.php",
            "app/../../escape.php",
            "/absolute.php",
            "public",
        ]

        result = subprocess.run(
            ["php", "-r", HARNESS, ENDPOINT.as_posix(), json.dumps(cases)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            raise AssertionError(f"PHP harness gagal: {result.stderr.strip()}")

        cls.mapping = json.loads(result.stdout)

    def test_public_assets_go_to_docroot_public(self):
        for name in ["public/index.php", "public/.htaccess", "public/build/manifest.json"]:
            with self.subTest(name=name):
                entry = self.mapping[name]
                self.assertTrue(entry["allowed"])
                self.assertEqual(entry["base"], "public")
                self.assertEqual(entry["relative"], name[len("public/"):])

    def test_index_php_never_lands_at_app_root(self):
        entry = self.mapping["public/index.php"]
        # relatif terhadap docroot `public/`, bukan app root `/api`.
        self.assertEqual(entry["relative"], "index.php")
        self.assertEqual(entry["base"], "public")

    def test_application_code_goes_to_app_root(self):
        for name in ["artisan", "app/Models/User.php", "vendor/autoload.php", "routes/web.php"]:
            with self.subTest(name=name):
                entry = self.mapping[name]
                self.assertTrue(entry["allowed"])
                self.assertEqual(entry["base"], "app-root")
                self.assertEqual(entry["relative"], name)

    def test_secrets_and_runtime_state_are_refused(self):
        for name in [
            ".env",
            "storage/logs/laravel.log",
            "bootstrap/cache/config.php",
            "public/deploy-extract.php",
            "public/deploy-secret.php",
            "../escape.php",
            "app/../../escape.php",
            "/absolute.php",
            "public",
        ]:
            with self.subTest(name=name):
                self.assertFalse(self.mapping[name]["allowed"], f"{name} harus ditolak")


if __name__ == "__main__":
    unittest.main()
