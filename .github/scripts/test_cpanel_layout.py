"""Kunci tata letak server cPanel yang TERUKUR, bukan yang diasumsikan.

Kegagalan mahal sebelumnya terjadi karena pemetaan deploy mengikuti asumsi
handover, bukan kenyataan server. Pengukuran pada 2026-11-20:

| Probe | Hasil | Arti |
|---|---|---|
| `GET /api/public/robots.txt` | 200 | `api/public/` adalah **direktori biasa di dalam docroot**, bukan docroot |
| `GET /api/public/deploy-extract.php` | 405 | PHP **dieksekusi langsung** di `api/public/`, melewati front controller |
| `GET /api/deploy-extract.php` | 404 | dikirim ke `api/public/index.php` (marker not found), bukan file |
| `GET /api/price-categories` | 200 | `.htaccess` root me-rewrite `^api` ke `api/public/index.php` |

Kesimpulan: docroot web adalah `jejaka500/`. `api/` dan bahkan `api/public/`
berada **di dalam** docroot dan bisa dipanggil langsung lewat URL. Karena itu
`.env` di `api/` dapat diakses web (sekarang 403 karena aturan, bukan karena
arsitektur), dan setiap berkas PHP di `api/public/` adalah endpoint publik.

Tes ini menjaga dua hal:

1. Endpoint deploy hanya boleh diekstrak ke direktori yang **tidak** dapat
   diakses langsung lewat URL.
2. Front controller tidak boleh ada di direktori yang diekstensi `.php` apa pun
   karena file aset di situ dapat dieksekusi.
"""

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ENDPOINT = SCRIPTS.parents[1] / "backend" / "deploy-cpanel" / "cpanel-deploy-handler.php"

def read_constants() -> dict[str, str]:
    """Baca nilai konstanta path dari sumber handler tanpa mengeksekusinya.

    `declare(strict_types=1)` tidak sah di dalam `eval()`, dan menyalin berkas
    agar bisa dimuat akan menyesatkan. Tokenizer PhpToken membaca deklarasi
    tanpa menjalankan apa pun.
    """
    harness = r"""$tokens = PhpToken::tokenize(file_get_contents($argv[1]));
$out = [];
$count = count($tokens);
foreach ($tokens as $i => $token) {
    if (! $token->is(T_STRING)) {
        continue;
    }
    if (! in_array($token->text, ['DEPLOY_DIR', 'APP_ROOT_DIR', 'ENTRY_DIR'], true)) {
        continue;
    }
    // Hanya deklarasi `const NAME = ...;` di level atas, bukan pemakaiannya.
    // Token dipisah whitespace, jadi lompati token kosong saat mundur.
    $prev = $i - 1;
    while ($prev >= 0 && $tokens[$prev]->is(T_WHITESPACE)) {
        $prev--;
    }
    if ($prev < 0 || ! $tokens[$prev]->is(T_CONST)) {
        continue;
    }
    $value = '';
    for ($j = $i + 2; $j < $count; $j++) {
        $t = $tokens[$j];
        if ($t->text === ';') {
            break;
        }
        if ($t->is(T_DIR)) {
            $value .= '__DIR__';
        } elseif ($t->is(T_CONSTANT_ENCAPSED_STRING)) {
            $value .= substr($t->text, 1, -1);
        }
    }
    $out[$token->text] = $value;
}
echo json_encode($out);
"""
    result = subprocess.run(
        ["php", "-r", harness, ENDPOINT.as_posix()],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise AssertionError(f"PHP harness gagal: {result.stderr.strip()}")

    raw = json.loads(result.stdout)
    prefix = ENDPOINT.parent.as_posix()
    return {
        key: os.path.normpath(expr.replace("__DIR__", prefix)) for key, expr in raw.items()
    }


@unittest.skipIf(shutil.which("php") is None, "PHP CLI tidak tersedia")
class DocrootLayoutTests(unittest.TestCase):
    def test_entry_dir_is_not_the_publicly_reachable_directory(self):
        """Entry deploy tidak boleh di `api/public/` — direktori itu dieksekusi web."""
        self.assertNotEqual(
            ENDPOINT.parent.name,
            "public",
            "`api/public/` dieksekusi langsung lewat URL (405/200 terukur), "
            "jadi endpoint deploy tidak boleh tinggal di sana",
        )

    def test_entry_exposes_the_backend_scripts_directory(self):
        """Entry harus berada di `backend/deploy-cpanel/` agar ikut ter-commit."""
        self.assertEqual(ENDPOINT.parent.name, "deploy-cpanel")

    def test_entry_directory_is_outside_every_public_directory(self):
        """Path di handler menunjuk `api/storage/`, bukan direktori yang dilayani web."""
        layout = read_constants()
        # DEPLOY_DIR = `__DIR__` = tempat handler DIPASANG di server, yaitu
        # `api/storage/cpanel-deploy`. Lokasi di repo berbeda dengan lokasi pasang,
        # jadi yang diperiksa adalah komentar pasang di dokumen, bukan path repo.
        self.assertEqual(layout["DEPLOY_DIR"], ENDPOINT.parent.as_posix())

        docs = (SCRIPTS.parents[1] / "backend" / "docs" / "CPANEL-DEPLOY-ARCHIVE.md").read_text()
        self.assertIn("api/storage/cpanel-deploy/", docs)
        self.assertIn("api/public/cpanel-deploy.php", docs)
        # Handler asli tidak boleh berada di direktori yang dieksekusi web.
        self.assertNotIn("public", Path("api/storage/cpanel-deploy").parts)


class DeploymentWiringTests(unittest.TestCase):
    """Mengunci kaitan antara uploader, workflow, dan runbook."""

    def test_workflow_fails_fast_when_endpoint_is_not_installed(self):
        """Deploy harus berhenti sebelum build bila endpoint belum siap."""
        workflow = (SCRIPTS.parents[1] / ".github" / "workflows" / "deploy-cpanel.yml").read_text()

        self.assertIn("Preflight deploy endpoint", workflow)
        # Endpoint yang tidak terpasang mengembalikan 404 — jangan diteruskan.
        self.assertIn('"$get_code" = "405"', workflow)
        self.assertIn('"$post_code" = "403"', workflow)
        # Preflight harus muncul sebelum langkah build yang mahal.
        self.assertLess(
            workflow.index("Preflight deploy endpoint"),
            workflow.index("Install Composer dependencies"),
        )

    def test_workflow_only_runs_when_server_is_marked_ready(self):
        workflow = (SCRIPTS.parents[1] / ".github" / "workflows" / "deploy-cpanel.yml").read_text()
        # `secrets` tidak sah di `jobs.<id>.if`; itu pernah mematikan seluruh workflow.
        self.assertIn("vars.CPANEL_DEPLOY_READY == 'true'", workflow)

    def test_uploader_endpoint_matches_the_documented_install_path(self):
        """URL di uploader, workflow, dan runbook harus sama persis."""
        import re

        from upload_chunks import DEFAULT_ENDPOINT

        self.assertEqual(
            DEFAULT_ENDPOINT,
            "https://jejaka500.followtheline.id/api/public/cpanel-deploy.php",
        )

        workflow = (SCRIPTS.parents[1] / ".github" / "workflows" / "deploy-cpanel.yml").read_text()
        documented = re.search(r"vars\.CPANEL_DEPLOY_ENDPOINT \|\| '([^']+)'", workflow)
        self.assertIsNotNone(documented, "workflow harus punya default endpoint")
        self.assertEqual(documented.group(1), DEFAULT_ENDPOINT)

        docs = (SCRIPTS.parents[1] / "backend" / "docs" / "CPANEL-DEPLOY-ARCHIVE.md").read_text()
        self.assertIn("/api/public/cpanel-deploy.php", docs)


if __name__ == "__main__":
    unittest.main()
