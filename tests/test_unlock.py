import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from vehiclegarage import unlock
from vehiclegarage.app import GarageApp


CODE = [f"{i:08X} {i + 1:08X}" for i in range(28)]
HASH = hashlib.sha256("\n".join(CODE).encode("ascii")).hexdigest()


class Response:
    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size):
        return self.content


class UnlockTests(unittest.TestCase):
    def test_selects_and_verifies_each_region_from_pinned_revision(self):
        blocks = []
        for region in ("USA", "PAL", "JAP", "KOR"):
            blocks.append(f"<pre>\nLicense Unlock {region} [Wiimm]\n" + "\n".join(CODE) + "\n</pre>")
        content = json.dumps({
            "query": {"pages": [{"revisions": [{
                "revid": unlock.REVISION, "slots": {"main": {"content": "\n".join(blocks)}}
            }]}]}
        }).encode()
        regions = {key: (name, HASH) for key, (name, _) in unlock.REGIONS.items()}
        with patch.object(unlock, "REGIONS", regions), patch.object(unlock.urllib.request, "urlopen", return_value=Response(content)):
            for game in ("RMCE01", "RMCP01", "RMCJ01", "RMCK01"):
                with self.subTest(game=game):
                    self.assertEqual(unlock.fetch_code(game), CODE)
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                unlock.fetch_code("RMCX01")

    def test_rejects_modified_download(self):
        content = json.dumps({
            "query": {"pages": [{"revisions": [{
                "revid": unlock.REVISION, "slots": {"main": {
                    "content": "<pre>\nLicense Unlock USA [Wiimm]\n" + "\n".join(CODE) + "\n</pre>"
                }}
            }]}]}
        }).encode()
        with patch.object(unlock.urllib.request, "urlopen", return_value=Response(content)):
            with self.assertRaisesRegex(ValueError, "failed verification"):
                unlock.fetch_code("RMCE01")

    def test_preserves_other_settings_and_codes_and_is_idempotent(self):
        original = (
            "# My settings\r\n[Core]\r\nCPUThread = True\r\nEnableCheats = False\r\n"
            "[Gecko]\r\n$Other [Author]\r\n01234567 89ABCDEF\r\n"
            "[Gecko_Enabled]\r\n$Other\r\n[Gecko_Disabled]\r\n$Another\r\n"
            f"${unlock.CODE_NAME}\r\n[Video]\r\nSetting = 1\r\n"
        )
        result = unlock.configure_text(original, CODE)
        self.assertIn("CPUThread = True\r\nEnableCheats = True", result)
        self.assertIn("$Other [Author]\r\n01234567 89ABCDEF", result)
        self.assertIn("[Gecko_Enabled]\r\n$Other\r\n" + f"${unlock.CODE_NAME}", result)
        self.assertIn("[Gecko_Disabled]\r\n$Another\r\n", result)
        self.assertIn("[Video]\r\nSetting = 1", result)
        self.assertEqual(unlock.configure_text(result, CODE), result)

    def test_install_backup_and_region_specific_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = root / "GameSettings"
            settings.mkdir()
            target = settings / "RMCK01.ini"
            original = b"[Core]\nCPUThread = True\n"
            target.write_bytes(original)
            actual, backup = unlock.install(root, "RMCK01", CODE)
            self.assertEqual(actual, target)
            self.assertIsNotNone(backup)
            self.assertEqual(backup.read_bytes(), original)
            self.assertIn("EnableCheats = True", target.read_text())
            self.assertEqual(unlock.install(root, "RMCK01", CODE), (target, None))
            self.assertFalse((settings / "RMCE01.ini").exists())

    def test_rejects_ambiguous_or_modified_configuration_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = root / "GameSettings"
            settings.mkdir()
            target = settings / "RMCE01.ini"
            original = "[Core]\nEnableCheats = False\n[Core]\nCPUThread = True\n"
            target.write_text(original)
            with self.assertRaisesRegex(ValueError, "multiple"):
                unlock.install(root, "RMCE01", CODE)
            self.assertEqual(target.read_text(), original)
            target.write_text(f"[Gecko]\n${unlock.CODE_NAME} [Wiimm]\nBAD CODE\n")
            with self.assertRaisesRegex(ValueError, "was changed"):
                unlock.install(root, "RMCE01", CODE)
            (settings / "RMCE01r0.ini").touch()
            with self.assertRaisesRegex(ValueError, "revision-specific"):
                unlock.install(root, "RMCE01", CODE)

    def test_button_configures_selected_game_only_after_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tool, exe, image = root / "DolphinTool.exe", root / "Dolphin.exe", root / "game.rvz"
            for path in (tool, exe, image):
                path.touch()
            app = SimpleNamespace(
                _require_stock=lambda: True,
                settings=SimpleNamespace(game_id="RMCK01", dolphintool=str(tool), disc=str(image)),
                unlock_button=Mock(), install_status=Mock(),
                _run_in_background=lambda work, done: done(work(), None),
            )
            with patch("vehiclegarage.app.dolphin.find_folders", return_value=SimpleNamespace(user_dir=root)), \
                 patch("vehiclegarage.app.disc.read_game_id", return_value="RMCK01"), \
                 patch("vehiclegarage.app.unlock.fetch_code", return_value=CODE), \
                 patch("vehiclegarage.app.messagebox.askyesno", return_value=False), \
                 patch("vehiclegarage.app.messagebox.showinfo") as info:
                GarageApp._setup_unlock(app)
                self.assertFalse((root / "GameSettings").exists())
                info.assert_not_called()
            with patch("vehiclegarage.app.dolphin.find_folders", return_value=SimpleNamespace(user_dir=root)), \
                 patch("vehiclegarage.app.disc.read_game_id", return_value="RMCK01"), \
                 patch("vehiclegarage.app.unlock.fetch_code", return_value=CODE), \
                 patch("vehiclegarage.app.messagebox.askyesno", return_value=True), \
                 patch("vehiclegarage.app.messagebox.showinfo") as info:
                GarageApp._setup_unlock(app)
                self.assertTrue((root / "GameSettings" / "RMCK01.ini").is_file())
                info.assert_called_once()


if __name__ == "__main__":
    unittest.main()
