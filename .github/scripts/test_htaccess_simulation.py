"""Simulasi aturan `.htaccess` root cPanel terhadap rute yang terukur nyata.

Mengubah `.htaccess` root bisa mematikan seluruh situs (aset SPA, SPA fallback,
API, admin). Berkas ini memetakan setiap rute ke keputusan yang diharapkan,
lalu mensimulasikan urutan `RewriteRule` agar perubahan aturan tertangkap
sebelum menyentuh server.

**Batas simulasi (jujur):** regex di sini hanya memeriksa pola `RewriteRule`.
LiteSpeed juga memperhitungkan `RewriteCond` (`-f`/`-d`) dan menyajikan berkas
fisik lebih dulu — itu sebabnya `/api/public/robots.txt` dilayani sebagai berkas
di server nyata, meski di simulasi terlihat jatuh ke pola `^api`. Simulasi ini
mengunci hal yang memang bisa dikunci statis: apakah sebuah rute **terblokir
`[F]`** atau tidak.

| Rute | Status terukur 2026-11-20 | Harapan |
|---|---|---|
| `/` `/up` `/api/price-categories` `/admin/login` | 200 | tetap 200 |
| `/css/filament/...` | 200 `text/css` | tidak diblokir |
| `/api/public/deploy-extract.php` | 405 (executed!) | harus diblokir |
| `/api/.env` | 403 | tetap 403 |
"""

import re
import unittest
from pathlib import Path

RULES_FILE = Path(__file__).resolve().parents[2] / "deploy" / "cpanel" / "htaccess-root.txt"


def parse_rules(text: str) -> list[tuple[str, str]]:
    """Ambil `(pola, aksi)` dari RewriteRule, abaikan komentar."""
    rules = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("RewriteRule"):
            continue
        parts = line.split()
        rules.append((parts[1], " ".join(parts[2:])))
    return rules


def apply_rules(path: str, rules: list[tuple[str, str]]) -> str:
    """Kembalikan aksi pertama yang cocok, atau 'passthrough'."""
    subject = path.lstrip("/")
    for pattern, action in rules:
        if re.search(pattern, subject):
            return action
    return "passthrough"


class RootHtaccessSimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = parse_rules(RULES_FILE.read_text())

    def test_deploy_helpers_are_forbidden(self):
        for path in (
            "/api/public/deploy-extract.php",
            "/api/public/deploy-secret.php",
            "/api/deploy-extract.php",
        ):
            with self.subTest(path=path):
                action = apply_rules(path, self.rules)
                self.assertIn("[F", action, f"{path} -> {action}")

    def test_deploy_shim_is_allowed_and_decided_by_php(self):
        """Shim harus sampai ke PHP; penolakan tanpa tanda tangan terjadi di kode."""
        action = apply_rules("/api/public/cpanel-deploy.php", self.rules)
        self.assertNotIn("[F", action, f"shim tidak boleh diblokir: {action}")

    def test_laravel_front_controller_is_never_blocked(self):
        for path in ("/api/public/index.php", "/api/public/build/manifest.json"):
            with self.subTest(path=path):
                self.assertNotIn("[F", apply_rules(path, self.rules), path)

    def test_secrets_in_api_are_forbidden(self):
        for path in ("/api/.env", "/api/composer.json", "/api/artisan"):
            with self.subTest(path=path):
                self.assertIn("[F", apply_rules(path, self.rules), path)

    def test_api_requests_still_reach_laravel(self):
        for path in ("/api/price-categories", "/api/webhook/midtrans", "/up", "/admin/login"):
            with self.subTest(path=path):
                action = apply_rules(path, self.rules)
                self.assertIn("index.php", action, f"{path} -> {action}")

    def test_spa_and_assets_are_not_intercepted_by_deny_rules(self):
        # Aset SPA dan rute publik tidak boleh terkena `[F]`.
        for path in ("/", "/assets/app.js", "/favicon-32.png", "/css/filament/filament/app.css"):
            with self.subTest(path=path):
                action = apply_rules(path, self.rules)
                self.assertNotIn("[F", action, f"{path} tidak boleh diblokir: {action}")

    def test_livewire_and_admin_prefixes_are_preserved(self):
        text = RULES_FILE.read_text()
        for prefix in ("api", "admin", "livewire", "up"):
            with self.subTest(prefix=prefix):
                self.assertIn(f"^{prefix}", text)


if __name__ == "__main__":
    unittest.main()
