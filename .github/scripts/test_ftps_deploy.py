import json
import sys
import unittest
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from ftps_deploy import deploy, is_excluded, main, remote_path


class FtpsDeploySafetyTests(unittest.TestCase):
    def test_excludes_env_storage_manifest_and_docroot_htaccess_only(self):
        excluded = [
            ".env",
            ".env.production",
            ".htaccess",
            ".deploy-manifest.json",
            "api/.env",
            "api/.env.local",
            "api/storage/logs/laravel.log",
            "api/tests/Feature/ExampleTest.php",
            "api/docker/php.ini",
            "bootstrap/cache/config.php",
            "api/bootstrap/cache/config.php",
        ]
        for path in excluded:
            with self.subTest(path=path):
                self.assertTrue(is_excluded(PurePosixPath(path)))

    def test_allows_laravel_public_htaccess_and_app_files(self):
        allowed = [
            "api/public/.htaccess",
            "api/app/Http/Controllers/Controller.php",
            "api/vendor/autoload.php",
            "index.html",
            "assets/app-12345678.js",
        ]
        for path in allowed:
            with self.subTest(path=path):
                self.assertFalse(is_excluded(PurePosixPath(path)))

    def test_maps_files_under_ftp_account_root(self):
        self.assertEqual(
            remote_path("/", "api/app/Http/Controller.php"),
            "/api/app/Http/Controller.php",
        )
        self.assertEqual(
            remote_path("/release", "assets/app.js"),
            "/release/assets/app.js",
        )

    def test_rejects_remote_path_traversal_and_absolute_files(self):
        invalid_paths = [
            ("/", "../outside.txt"),
            ("/../home", "file.txt"),
            ("/api", "/outside-account.txt"),
            ("/", "nested/../outside.txt"),
        ]
        for root, relative in invalid_paths:
            with self.subTest(root=root, relative=relative):
                with self.assertRaises(ValueError):
                    remote_path(root, relative)

    def test_rejects_control_characters_in_remote_paths(self):
        with self.assertRaises(ValueError):
            remote_path("/", "assets/ok.js\r\nDELE /important")

    @patch("ftps_deploy.FTP_TLS")
    def test_deploy_uses_explicit_tls_and_only_stores_allowed_files(self, ftp_factory):
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir)
            (source / "index.html").write_text("spa")
            (source / ".htaccess").write_text("live-docroot-htaccess-must-not-upload")
            (source / "api").mkdir()
            (source / "api" / ".env").write_text("secret")
            (source / "api" / "controller.php").write_text("controller")
            (source / "api" / "public").mkdir()
            (source / "api" / "public" / ".htaccess").write_text("laravel-rewrite")
            (source / "api" / "storage").mkdir()
            (source / "api" / "storage" / "file.txt").write_text("preserve")

            ftp = MagicMock()
            ftp.size.return_value = None
            ftp_factory.return_value.__enter__.return_value = ftp
            environment = {
                "CPANEL_FTP_HOST": "ftp.example.test",
                "CPANEL_FTP_USERNAME": "deploy@example.test",
                "CPANEL_FTP_PASSWORD": "not-printed",
                "CPANEL_FTP_PORT": "21",
            }

            with patch.dict("os.environ", environment, clear=False):
                stats = deploy(source, "/")

        ftp.connect.assert_called_once_with("ftp.example.test", 21)
        ftp.auth.assert_called_once_with()
        ftp.login.assert_called_once_with("deploy@example.test", "not-printed")
        ftp.prot_p.assert_called_once_with()
        self.assertEqual(stats["uploaded"], 3)
        self.assertEqual(stats["skipped"], 0)
        stored_paths = [call.args[0] for call in ftp.storbinary.call_args_list]
        self.assertCountEqual(
            stored_paths,
            [
                "STOR /index.html",
                "STOR /api/controller.php",
                "STOR /api/public/.htaccess",
            ],
        )
        ftp.delete.assert_not_called()
        ftp.rmd.assert_not_called()

    @patch("ftps_deploy.FTP_TLS")
    def test_incremental_skip_when_manifest_and_size_match(self, ftp_factory):
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir)
            file_a = source / "a.txt"
            file_b = source / "b.txt"
            file_a.write_text("unchanged")
            file_b.write_text("new content")

            import hashlib

            digest_a = hashlib.sha256(b"unchanged").hexdigest()
            manifest_json = json.dumps(
                {
                    "version": 1,
                    "target": "/",
                    "files": {
                        "a.txt": {"sha256": digest_a, "size": len(b"unchanged")},
                    },
                }
            ).encode("utf-8")

            ftp = MagicMock()
            # simulate reading existing manifest
            def fake_retrbinary(cmd, callback):
                if cmd == "RETR /.manifest.json":
                    callback(manifest_json)
                else:
                    raise Exception("unexpected RETR")

            ftp.retrbinary.side_effect = fake_retrbinary
            # remote_size for a.txt matches; b.txt is None
            def fake_size(path):
                if path == "/a.txt":
                    return len(b"unchanged")
                return None

            ftp.size.side_effect = fake_size
            ftp_factory.return_value.__enter__.return_value = ftp

            environment = {
                "CPANEL_FTP_HOST": "ftp.example.test",
                "CPANEL_FTP_USERNAME": "deploy@example.test",
                "CPANEL_FTP_PASSWORD": "not-printed",
                "CPANEL_FTP_PORT": "21",
            }

            with patch.dict("os.environ", environment, clear=False):
                stats = deploy(source, "/", manifest_remote="/.manifest.json")

        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(stats["uploaded"], 1)
        stored = [call.args[0] for call in ftp.storbinary.call_args_list]
        self.assertIn("STOR /b.txt", stored)
        self.assertIn("STOR /.manifest.json", stored)
        self.assertNotIn("STOR /a.txt", stored)

    @patch("ftps_deploy.FTP_TLS")
    def test_deploy_fails_when_manifest_save_fails(self, ftp_factory):
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir)
            (source / "file.txt").write_text("hello")

            ftp = MagicMock()
            ftp.size.return_value = None

            def fail_on_manifest(cmd, _buf):
                if cmd.startswith("STOR /.deploy-manifest"):
                    from ftplib import error_perm
                    raise error_perm("550 Permission denied")

            ftp.storbinary.side_effect = fail_on_manifest
            ftp_factory.return_value.__enter__.return_value = ftp

            environment = {
                "CPANEL_FTP_HOST": "ftp.example.test",
                "CPANEL_FTP_USERNAME": "deploy@example.test",
                "CPANEL_FTP_PASSWORD": "not-printed",
                "CPANEL_FTP_PORT": "21",
            }

            with patch.dict("os.environ", environment, clear=False):
                with self.assertRaises(RuntimeError):
                    deploy(source, "/", manifest_remote="/.deploy-manifest.json")

    @patch("ftps_deploy.FTP_TLS")
    def test_ignores_manifest_when_target_root_mismatches(self, ftp_factory):
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir)
            (source / "file.txt").write_text("content")

            import hashlib
            digest = hashlib.sha256(b"content").hexdigest()
            mismatched_manifest = json.dumps(
                {
                    "version": 1,
                    "target": "/other-root",
                    "files": {
                        "file.txt": {"sha256": digest, "size": len(b"content")},
                    },
                }
            ).encode("utf-8")

            ftp = MagicMock()
            ftp.retrbinary.side_effect = lambda cmd, callback: callback(mismatched_manifest)
            ftp.size.return_value = len(b"content")
            ftp_factory.return_value.__enter__.return_value = ftp

            environment = {
                "CPANEL_FTP_HOST": "ftp.example.test",
                "CPANEL_FTP_USERNAME": "deploy@example.test",
                "CPANEL_FTP_PASSWORD": "not-printed",
                "CPANEL_FTP_PORT": "21",
            }

            with patch.dict("os.environ", environment, clear=False):
                stats = deploy(source, "/api", manifest_remote="/.manifest.json")

            # Target mismatch causes full manifest rejection; file must be re-uploaded.
            self.assertEqual(stats["skipped"], 0)
            self.assertEqual(stats["uploaded"], 1)

    @patch("ftps_deploy.deploy")
    def test_cli_recognizes_force_flag_before_positional_arguments(self, deploy_mock):
        deploy_mock.return_value = {"uploaded": 0, "skipped": 0}

        with patch.object(sys, "argv", ["ftps_deploy.py", "--force", "backend", "/api", "/m.json"]):
            exit_code = main()

        self.assertEqual(exit_code, 0)
        args = deploy_mock.call_args.args
        self.assertEqual(args[0], Path("backend"))
        self.assertEqual(args[1], "/api")
        self.assertEqual(args[2], "/m.json")
        self.assertTrue(args[3])

    @patch("ftps_deploy.deploy")
    def test_cli_defaults_to_incremental_when_force_flag_is_absent(self, deploy_mock):
        deploy_mock.return_value = {"uploaded": 0, "skipped": 0}

        with patch.object(sys, "argv", ["ftps_deploy.py", "frontend/dist", "/", "/m.json"]):
            exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertFalse(deploy_mock.call_args.args[3])



if __name__ == "__main__":
    unittest.main()
