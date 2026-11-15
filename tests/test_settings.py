import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from vehiclegarage.app import GarageApp
from vehiclegarage.settings import Settings


class PickerTests(unittest.TestCase):
    def test_remembers_separate_folders_and_ignores_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            downloads = root / "Downloads"
            files = root / "Files"
            output = root / "Output"
            for folder in (downloads, files, output):
                folder.mkdir()
            app = SimpleNamespace(settings=Settings(), root_dir=root)
            with patch("vehiclegarage.settings.downloads_dir", return_value=downloads), \
                    patch("vehiclegarage.app.filedialog.askopenfilename", side_effect=[str(files / "pack.zip"), ""]) as open_file, \
                    patch("vehiclegarage.app.filedialog.askdirectory", return_value=str(output)):
                GarageApp._choose_path(app, "texture_import", is_file=True)
                self.assertEqual(open_file.call_args.kwargs["initialdir"], str(downloads))
                GarageApp._choose_path(app, "install_folder", is_file=False)
                app.settings = Settings.load(root)
                GarageApp._choose_path(app, "texture_import", is_file=True)
                self.assertEqual(open_file.call_args.kwargs["initialdir"], str(files))
                self.assertEqual(app.settings.recent_folders["texture_import"], str(files))
                self.assertEqual(app.settings.recent_folders["install_folder"], str(output))
                self.assertEqual(Settings.load(root).recent_folders, app.settings.recent_folders)

    def test_missing_folder_and_existing_settings_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "settings.json").write_text('{"disc": "old.rvz"}', encoding="utf-8")
            settings = Settings.load(root)
            settings.recent_folders["game_image"] = str(root / "missing")
            with patch("vehiclegarage.settings.downloads_dir", return_value=root):
                self.assertEqual(settings.picker_folder("game_image"), root)
                self.assertEqual(settings.picker_folder("game_image", str(root / "game.rvz"), True), root)
                self.assertEqual(settings.picker_folder("install_folder", str(root)), root)

    def test_save_failure_is_reported_without_discarding_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = Settings()
            app = SimpleNamespace(settings=settings, root_dir=root)
            with patch("vehiclegarage.settings.downloads_dir", return_value=root), \
                    patch("vehiclegarage.app.filedialog.askopenfilename", return_value=str(root / "pack.zip")), \
                    patch.object(settings, "save", side_effect=OSError("disk full")), \
                    patch("vehiclegarage.app.messagebox.showwarning") as warning:
                self.assertEqual(GarageApp._choose_path(app, "texture_import", is_file=True), str(root / "pack.zip"))
                warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
