"""Guard konfigurasi workflow deploy.

Kesalahan `secrets.*` di `jobs.<id>.if` membuat GitHub menolak seluruh workflow:
run dibuat lalu langsung gagal tanpa job, dengan log yang tidak bisa dibaca dari
CLI. Itu pernah terjadi di `main` dan mematikan rantai deploy diam-diam.
"""

import unittest
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
DEPLOY = WORKFLOWS / "deploy-cpanel.yml"


def _job_level_if_blocks(text: str) -> list[str]:
    """Ambil blok `if:` yang berada di level job (indentasi 4 spasi)."""
    lines = text.splitlines()
    blocks = []
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith("if:") or len(line) - len(stripped) != 4:
            continue
        block = [line]
        for follow in lines[index + 1:]:
            if follow.strip() and (len(follow) - len(follow.lstrip())) <= 4:
                break
            block.append(follow)
        blocks.append("\n".join(block))
    return blocks


class WorkflowContextTests(unittest.TestCase):
    def test_deploy_job_condition_avoids_forbidden_contexts(self):
        text = DEPLOY.read_text()
        blocks = _job_level_if_blocks(text)

        self.assertTrue(blocks, "job deploy harus punya kondisi eksplisit")

        for block in blocks:
            with self.subTest(block=block.strip().splitlines()[0]):
                self.assertNotIn(
                    "secrets.",
                    block,
                    "context secrets tidak tersedia di jobs.<id>.if; gunakan vars",
                )
                self.assertNotIn("env.", block, "context env tidak tersedia di jobs.<id>.if")

    def test_deploy_gated_by_explicit_ready_variable(self):
        text = DEPLOY.read_text()
        blocks = _job_level_if_blocks(text)
        joined = "\n".join(blocks)
        self.assertIn("vars.CPANEL_DEPLOY_READY", joined)
        self.assertIn(
            "== 'true'",
            joined,
            "harus aktif hanya bila CPANEL_DEPLOY_READY bernilai true",
        )

    def test_no_workflow_uses_ftp_credentials(self):
        for path in sorted(WORKFLOWS.glob("*.yml")):
            with self.subTest(workflow=path.name):
                text = path.read_text()
                self.assertNotIn("CPANEL_FTP_PASSWORD", text)
                self.assertNotIn("ftps_deploy.py", text)


if __name__ == "__main__":
    unittest.main()
