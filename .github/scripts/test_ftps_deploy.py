import unittest
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from ftps_deploy import deploy, is_excluded, remote_path


class FtpsDeploySafetyTests(unittest.TestCase):
    def test_excludes_env_storage_and_htaccess(self):
        excluded = [
            ".env",
            ".env.production",
            "api/.env",
            "api/storage/logs/laravel.log",
            "assets/.htaccess",
        ]

        for path in excluded:
            with self.subTest(path=path):
                self.assertTrue(is_excluded(PurePosixPath(path)))

    def test_allows_application_and_built_spa_files(self):
        allowed = [
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
            (source / ".htaccess").write_text("protected")
            (source / "api").mkdir()
            (source / "api" / ".env").write_text("secret")
            (source / "api" / "controller.php").write_text("controller")
            (source / "api" / "storage").mkdir()
            (source / "api" / "storage" / "file.txt").write_text("preserve")

            ftp = MagicMock()
            ftp_factory.return_value.__enter__.return_value = ftp
            environment = {
                "CPANEL_FTP_HOST": "ftp.example.test",
                "CPANEL_FTP_USERNAME": "deploy@example.test",
                "CPANEL_FTP_PASSWORD": "not-printed",
                "CPANEL_FTP_PORT": "21",
            }

            with patch.dict("os.environ", environment, clear=False):
                uploaded = deploy(source, "/")

        ftp.connect.assert_called_once_with("ftp.example.test", 21)
        ftp.auth.assert_called_once_with()
        ftp.login.assert_called_once_with("deploy@example.test", "not-printed")
        ftp.prot_p.assert_called_once_with()
        self.assertEqual(uploaded, 2)
        stored_paths = [call.args[0] for call in ftp.storbinary.call_args_list]
        self.assertCountEqual(stored_paths, ["STOR /index.html", "STOR /api/controller.php"])
        ftp.delete.assert_not_called()
        ftp.rmd.assert_not_called()


if __name__ == "__main__":
    unittest.main()
