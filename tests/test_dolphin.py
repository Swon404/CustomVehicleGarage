import tempfile
import unittest
from pathlib import Path

from vehiclegarage import dolphin


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


if __name__ == "__main__":
    unittest.main()
