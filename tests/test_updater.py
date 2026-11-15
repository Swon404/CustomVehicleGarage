import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vehiclegarage import updater
from vehiclegarage.app import GarageApp
from types import SimpleNamespace
from unittest.mock import Mock


class Response(io.BytesIO):
    def geturl(self):
        return "https://github.com/download"


def release_data(version="0.2.1", content=b"new executable"):
    tag = f"v{version}"
    return {
        "tag_name": tag,
        "assets": [{
            "name": updater.ASSET_NAME,
            "browser_download_url": f"https://github.com/Swon404/CustomVehicleGarage/releases/download/{tag}/{updater.ASSET_NAME}",
            "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
        }],
    }


class UpdateTests(unittest.TestCase):
    def test_release_comparison_and_verified_download(self):
        content = b"new executable"
        data = release_data(content=content)
        with patch.object(updater, "VERSION", "0.1.1"), patch.object(
            updater, "urlopen", side_effect=[Response(json.dumps(data).encode()), Response(content)]
        ):
            release = updater.latest_release()
            self.assertIsNotNone(release)
            self.assertEqual(release.version, "0.2.1")
            with tempfile.TemporaryDirectory() as temp:
                target = Path(temp) / "update.exe"
                updater.download_release(release, target)
                self.assertEqual(target.read_bytes(), content)

    def test_current_or_older_version_does_not_update(self):
        with patch.object(updater, "VERSION", "0.2.1"), patch.object(
            updater, "urlopen", return_value=Response(json.dumps(release_data()).encode())
        ):
            self.assertIsNone(updater.latest_release())

    def test_rejects_invalid_asset_metadata(self):
        data = release_data()
        data["assets"][0]["browser_download_url"] = "https://example.com/update.exe"
        with patch.object(updater, "VERSION", "0.1.1"), patch.object(
            updater, "urlopen", return_value=Response(json.dumps(data).encode())
        ):
            with self.assertRaisesRegex(updater.UpdateError, "expected GitHub asset"):
                updater.latest_release()

    def test_bad_digest_deletes_download(self):
        release = updater.Release("0.2.1", "https://github.com/download", "0" * 64)
        with tempfile.TemporaryDirectory() as temp, patch.object(
            updater, "urlopen", return_value=Response(b"corrupt")
        ):
            target = Path(temp) / "update.exe"
            with self.assertRaisesRegex(updater.UpdateError, "SHA-256"):
                updater.download_release(release, target)
            self.assertFalse(target.exists())

    def test_source_checkout_cannot_replace_python_executable(self):
        with patch.object(updater.sys, "frozen", False, create=True):
            with self.assertRaisesRegex(updater.UpdateError, "Windows executable"):
                updater.install_release(updater.Release("0.2.1", "", ""))

    def test_startup_shows_update_button_only_for_new_release(self):
        release = updater.Release("0.2.1", "https://github.com/download", "a" * 64)
        with patch("vehiclegarage.app.OFFICIAL_RELEASE", True):
            for result in (None, release):
                app = SimpleNamespace(
                    update_button=Mock(), update_status=Mock(), nav_buttons={"setup": Mock()},
                    available_release=None,
                    _run_in_background=lambda work, done, result=result: done(result, None),
                )
                GarageApp._check_update(app)
                self.assertEqual(app.update_button.pack.called, result is not None)
                self.assertEqual(app.available_release, result)

    def test_development_build_does_not_offer_update(self):
        app = SimpleNamespace(update_status=Mock(), _run_in_background=Mock())
        with patch("vehiclegarage.app.OFFICIAL_RELEASE", False):
            GarageApp._check_update(app)
        app._run_in_background.assert_not_called()
        self.assertIn("Development build", app.update_status.config.call_args.kwargs["text"])

    @unittest.skipUnless(os.name == "nt", "Windows updater")
    def test_installer_starts_a_no_window_helper_for_frozen_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            work.mkdir()
            target = root / "CustomVehicleGarage.exe"
            target.touch()
            def download(_release, destination):
                destination.write_bytes(b"verified test download")
            with patch.object(updater.sys, "frozen", True, create=True), \
                    patch.object(updater.sys, "executable", str(target)), \
                    patch.object(updater.tempfile, "mkdtemp", return_value=str(work)), \
                    patch.object(updater, "download_release", side_effect=download), \
                    patch.object(updater.subprocess, "Popen") as popen:
                updater.install_release(updater.Release("0.2.1", "", ""))
            flags = popen.call_args.kwargs["creationflags"]
            self.assertTrue(flags & subprocess.CREATE_NO_WINDOW)
            self.assertFalse(flags & subprocess.DETACHED_PROCESS)
            script = (work / "install.ps1").read_text(encoding="utf-8")
            self.assertIn("PYINSTALLER_RESET_ENVIRONMENT", script)


if __name__ == "__main__":
    unittest.main()
