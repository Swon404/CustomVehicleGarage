import json
import queue
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from vehiclegarage import dolphin, export
from vehiclegarage.app import GarageApp


class DolphinFolderTests(unittest.TestCase):
    def test_portable_install_uses_user_folder_beside_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "Dolphin.exe"
            (Path(tmp) / "portable.txt").write_text("")
            folders = dolphin.find_folders(exe)
            self.assertEqual(folders.riivolution, Path(tmp) / "User" / "Load" / "Riivolution")
            self.assertEqual(folders.sd_sync, Path(tmp) / "User" / "Load" / "WiiSDSync")

    def test_configured_sd_sync_folder_is_read_from_dolphin_ini(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "Dolphin.exe"
            (Path(tmp) / "portable.txt").write_text("")
            config = Path(tmp) / "User" / "Config"
            config.mkdir(parents=True)
            (config / "Dolphin.ini").write_text("[General]\nWiiSDCardSyncFolder = D:/MySD/\n")
            self.assertEqual(dolphin.find_folders(exe).sd_sync, Path("D:/MySD/"))

    def test_launch_uses_enabled_patch_and_dolphin_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "Dolphin.exe"
            image = root / "game.rvz"
            exe.touch()
            image.touch()
            sd_root = root / "Load" / "Riivolution"
            xml = sd_root / "riivolution" / "CustomVehicleGarage.xml"
            xml.parent.mkdir(parents=True)
            xml.write_text(export.riivolution_xml("RMCE01", ["Race/Common.szs"]), encoding="utf-8")
            archive = sd_root / "CustomVehicleGarage" / "Race" / "Common.szs"
            archive.parent.mkdir(parents=True)
            archive.touch()
            preset = root / "app" / "dolphin-launch.json"

            with patch("vehiclegarage.dolphin.subprocess.Popen") as popen:
                dolphin.launch_mod(exe, image, "RMCE01", sd_root, preset)

            data = json.loads(preset.read_text(encoding="utf-8"))
            self.assertEqual(data["base-file"], str(image.resolve()))
            patch_data = data["riivolution"]["patches"][0]
            self.assertEqual(patch_data["root"], str(sd_root.resolve()))
            self.assertEqual(patch_data["xml"], str(xml.resolve()))
            self.assertEqual(patch_data["options"], [{
                "section-name": "Custom Vehicle Garage",
                "option-name": "Custom Vehicle Garage",
                "choice": 1,
            }])
            popen.assert_called_once_with([str(exe), "--exec", str(preset.resolve())], cwd=str(exe.parent))

    def test_launch_rejects_missing_patch_files_and_wrong_region(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "Dolphin.exe"
            image = root / "game.rvz"
            exe.touch()
            image.touch()
            sd_root = root / "Load" / "Riivolution"
            xml = sd_root / "riivolution" / "CustomVehicleGarage.xml"
            xml.parent.mkdir(parents=True)
            xml.write_text(export.riivolution_xml("RMCE01", ["Race/Common.szs", "Scene/UI/MenuSingle.szs"]), encoding="utf-8")
            archive = sd_root / "CustomVehicleGarage" / "Race" / "Common.szs"
            archive.parent.mkdir(parents=True)
            archive.touch()
            preset = root / "preset.json"
            with patch("vehiclegarage.dolphin.subprocess.Popen") as popen:
                with self.assertRaisesRegex(ValueError, "missing or invalid"):
                    dolphin.launch_mod(exe, image, "RMCE01", sd_root, preset)
                with self.assertRaisesRegex(ValueError, "does not match"):
                    dolphin.launch_mod(exe, image, "RMCP01", sd_root, preset)
                popen.assert_not_called()
                self.assertFalse(preset.exists())

    def test_build_and_play_installs_current_mod_to_dolphin_before_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tool = root / "DolphinTool.exe"
            image = root / "game.rvz"
            exe = root / "Dolphin.exe"
            for path in (tool, image, exe):
                path.touch()
            sd_root = root / "Load" / "Riivolution"
            settings = SimpleNamespace(
                game_id="RMCE01", disc=str(image), dolphintool=str(tool), save=Mock()
            )
            app = SimpleNamespace(
                _require_stock=lambda: True,
                library=SimpleNamespace(all=lambda: []),
                _install_targets=lambda: [],
                folders=SimpleNamespace(riivolution=sd_root),
                settings=settings,
                use_riivolution=Mock(get=Mock(return_value=False)),
                use_sd_sync=Mock(get=Mock(return_value=False)),
                use_custom=Mock(get=Mock(return_value=False)),
                custom_var=Mock(get=Mock(return_value="")),
                root_dir=root,
                cache=root / "cache",
                build_button=Mock(),
                play_button=Mock(),
                cancel_build_button=Mock(),
                install_status=Mock(),
                progress=Mock(),
                events=queue.Queue(),
                _run_in_background=lambda work, done: done(work(), None),
            )
            with patch("vehiclegarage.app.disc.read_game_id", return_value="RMCE01"), \
                    patch("vehiclegarage.app.export.install_mod", return_value=[sd_root]) as install, \
                    patch("vehiclegarage.app.dolphin.launch_mod") as launch:
                GarageApp._build_mod(app, play=True)
            self.assertEqual(install.call_args.args[:4], (root / "cache" / "RMCE01", "RMCE01", [], [sd_root]))
            launch.assert_called_once_with(exe, image, "RMCE01", sd_root, root / "dolphin-launch.json")

    def test_cancelled_build_does_not_launch_dolphin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tool, image, exe = (root / name for name in ("DolphinTool.exe", "game.rvz", "Dolphin.exe"))
            for path in (tool, image, exe):
                path.touch()
            app = SimpleNamespace(
                _require_stock=lambda: True, library=SimpleNamespace(all=lambda: []),
                _install_targets=lambda: [], folders=SimpleNamespace(riivolution=root / "target"),
                settings=SimpleNamespace(game_id="RMCE01", disc=str(image), dolphintool=str(tool), save=Mock()),
                use_riivolution=Mock(get=Mock(return_value=False)), use_sd_sync=Mock(get=Mock(return_value=False)),
                use_custom=Mock(get=Mock(return_value=False)), custom_var=Mock(get=Mock(return_value="")),
                root_dir=root, cache=root / "cache", build_button=Mock(), play_button=Mock(),
                cancel_build_button=Mock(), install_status=Mock(), progress=Mock(), events=queue.Queue(),
            )
            def run(work, done):
                try:
                    done(work(), None)
                except export.BuildCancelled as error:
                    done(None, error)
            app._run_in_background = run
            with patch("vehiclegarage.app.disc.read_game_id", return_value="RMCE01"), \
                    patch("vehiclegarage.app.export.install_mod", side_effect=export.BuildCancelled), \
                    patch("vehiclegarage.app.dolphin.launch_mod") as launch:
                GarageApp._build_mod(app, play=True)
            launch.assert_not_called()
            app.install_status.config.assert_called_with(text="Build cancelled. Existing installations were not changed.")


if __name__ == "__main__":
    unittest.main()
