import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vehiclegarage import updater


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


if __name__ == "__main__":
    unittest.main()
