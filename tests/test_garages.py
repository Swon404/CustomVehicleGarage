import argparse
import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from unittest.mock import Mock, patch

from vehiclegarage import cli, garages, presets
from vehiclegarage.app import GarageApp
from vehiclegarage.creations import Creation, Library
from vehiclegarage.settings import Settings
from vehiclegarage.textures import TexturePack


class GarageTests(unittest.TestCase):
    def test_existing_garage_is_preserved_and_backed_up_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = Library(root / "creations")
            original.save(Creation("Original", {"speed": 90}, slot=1))
            store = garages.Garages(root)
            self.assertEqual(store.active_name, "My Garage")
            self.assertEqual(store.library().all()[0].name, "Original")
            backup = root / "garage-migration-backup" / "creation-001.json"
            self.assertEqual(backup.read_bytes(), (root / "creations" / "creation-001.json").read_bytes())
            original.save(Creation("Later", slot=2))
            garages.Garages(root)
            self.assertFalse((backup.parent / "creation-002.json").exists())

    def test_independent_garages_switch_duplicate_rename_and_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = garages.Garages(root)
            store.library().save(Creation("Original", slot=0))
            second = store.create("Chaos", store.library().all())
            store.select(second)
            copy = store.library().all()[0]
            copy.name = "Changed"
            store.library().save(copy)
            store.rename(second, "Workshop")
            reopened = garages.Garages(root)
            self.assertEqual(reopened.active_name, "Workshop")
            self.assertEqual(reopened.library().all()[0].name, "Changed")
            self.assertEqual(reopened.library("default").all()[0].name, "Original")
            with self.assertRaisesRegex(ValueError, "already"):
                reopened.rename(second, "MY GARAGE")
            reopened.delete(second)
            self.assertEqual(reopened.active_name, "My Garage")
            self.assertEqual(reopened.library().all()[0].name, "Original")

    def test_copy_and_move_preserve_source_and_disable_slot_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = garages.Garages(Path(tmp))
            source = store.library().save(Creation("A", slot=0))
            target_id = store.create("Other", [Creation("B", slot=0)])
            copied, conflict = store.file_vehicle(source, target_id)
            self.assertTrue(conflict)
            self.assertFalse(copied.enabled)
            self.assertEqual(len(store.library().all()), 1)
            store.file_vehicle(source, target_id, move=True)
            self.assertEqual(store.library().all(), [])
            self.assertEqual(len(store.library(target_id).all()), 3)

    def test_failed_move_does_not_remove_original_or_keep_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = garages.Garages(Path(tmp))
            source = store.library().save(Creation("A", slot=0))
            target = store.create("Other")
            delete = Library.delete
            def fail_source(library, number):
                if library.folder == store.library().folder:
                    raise OSError("locked")
                return delete(library, number)
            with patch.object(Library, "delete", new=fail_source):
                with self.assertRaisesRegex(OSError, "locked"):
                    store.file_vehicle(source, target, move=True)
            self.assertEqual(len(store.library().all()), 1)
            self.assertEqual(store.library(target).all(), [])

    def test_failed_delete_restores_garage(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = garages.Garages(Path(tmp))
            second = store.create("Other", [Creation("Saved", slot=0)])
            with patch.object(store, "_save", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    store.delete(second)
            self.assertEqual(store.library(second).all()[0].name, "Saved")
            self.assertEqual(len(garages.Garages(Path(tmp)).entries()), 2)

    def test_import_export_and_missing_texture_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            texture = TexturePack("Paint", 0, {"sdf_kart-bmr.szs": "a" * 64}, "https://example.com", "Artist")
            item = Creation("One", {"speed": 96.5}, slot=0, number=4, texture=texture)
            path = root / "shared.json"
            garages.export_file(path, "Chaos", [item], fit_names=True)
            kind, name, items, fit_names = garages.import_file(path)
            self.assertEqual((kind, name, items), ("garage", "Chaos", [item]))
            self.assertTrue(fit_names)
            self.assertEqual(garages.missing_textures(items, root / "textures"), ["One"])
            (root / "textures").mkdir()
            (root / "textures" / ("a" * 64 + ".szs")).write_bytes(b"corrupted")
            self.assertEqual(garages.missing_textures(items, root / "textures"), ["One"])
            self.assertNotIn(".szs bytes", path.read_text(encoding="utf-8"))
            garages.export_file(path, "One", [item], vehicle=True)
            self.assertEqual(garages.import_file(path)[0], "vehicle")
            long_name = "Vehicle" * 20
            garages.export_file(path, long_name, [Creation(long_name, slot=0)], vehicle=True)
            self.assertEqual(garages.import_file(path)[1], long_name)
            kind, _, items, fit_names = garages.import_file(presets.DEFAULT_FILE)
            self.assertEqual(kind, "presets")
            self.assertEqual(len(items), 36)
            self.assertTrue(fit_names)

    def test_invalid_import_is_rejected_without_changing_garage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = garages.Garages(root)
            item = Creation("Good", {"speed": 90}, slot=0)
            path = root / "bad.json"
            garages.export_file(path, "Test", [item])
            data = json.loads(path.read_text(encoding="utf-8"))
            data["vehicles"][0]["stats"]["speed"] = float("nan")
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "finite"):
                garages.import_file(path)
            self.assertEqual(store.entries(), [("default", "My Garage")])
            self.assertEqual(store.library().all(), [])

    def test_cli_build_uses_active_garage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = garages.Garages(root)
            store.library().save(Creation("Original", slot=0))
            second = store.create("Other", [Creation("Selected", slot=1)])
            store.select(second)
            Settings(game_id="RMCE01").save(root)
            args = argparse.Namespace(data=str(root), disc=None, dolphintool=None, out=str(root / "out"))
            with patch("vehiclegarage.cli.export.build_mod", return_value=root / "out") as build:
                self.assertEqual(cli.build(args), 0)
            self.assertEqual([item.name for item in build.call_args.args[2]], ["Selected"])

    def test_cli_fits_names_for_preset_garage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = garages.Garages(root)
            second = store.create("Other", [Creation("Long name", slot=0)], fit_names=True)
            store.select(second)
            Settings(game_id="RMCE01").save(root)
            args = argparse.Namespace(data=str(root), disc=None, dolphintool=None, out=str(root / "out"))
            fitted = [Creation("Lon", slot=0)]
            with patch("vehiclegarage.cli.presets.fit_names", return_value=(fitted, ["Long name -> Lon"])) as fit, \
                    patch("vehiclegarage.cli.export.build_mod", return_value=root / "out") as build:
                self.assertEqual(cli.build(args), 0)
            self.assertEqual(fit.call_args.args[0][0].name, "Long name")
            self.assertEqual(build.call_args.args[2], fitted)

    def test_build_uses_fitted_names_without_changing_saved_creations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            saved = Creation("Long name", slot=0)
            excluded = Creation("Excluded", slot=1, enabled=False)
            settings = SimpleNamespace(game_id="RMCE01", disc="", dolphintool="", save=Mock())
            app = SimpleNamespace(
                _require_stock=lambda: True, build_collection=Mock(get=Mock(return_value="garage")),
                fit_garage_names=Mock(get=Mock(return_value=True)),
                library=SimpleNamespace(all=lambda: [saved, excluded]),
                _install_targets=lambda: [root / "out"], settings=settings,
                use_riivolution=Mock(get=Mock(return_value=False)), use_sd_sync=Mock(get=Mock(return_value=False)),
                use_custom=Mock(get=Mock(return_value=True)), custom_var=Mock(get=Mock(return_value=str(root / "out"))),
                root_dir=root, cache=root / "cache", build_button=Mock(), play_button=Mock(),
                cancel_build_button=Mock(), install_status=Mock(), progress=Mock(), events=Queue(),
                _run_in_background=lambda work, done: done(work(), None),
            )
            fitted = [Creation("Lon", slot=0)]
            with patch("vehiclegarage.app.presets.fit_names", return_value=(fitted, ["Long name -> Lon"])) as fit, \
                    patch("vehiclegarage.app.export.install_mod", return_value=[root / "out"]) as install:
                GarageApp._build_mod(app)
            self.assertEqual(fit.call_args.args[0], [saved])
            self.assertEqual(install.call_args.args[2], fitted)
            self.assertEqual(saved.name, "Long name")


class GarageUiTests(unittest.TestCase):
    def test_switch_copy_export_and_import_through_app(self):
        try:
            probe = tk.Tk()
        except tk.TclError as err:
            self.skipTest(f"Tk display unavailable: {err}")
        probe.destroy()
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(GarageApp, "_autodetect_tool"), patch.object(GarageApp, "_check_update"), \
                patch("vehiclegarage.app.messagebox.showerror", side_effect=AssertionError), \
                patch("vehiclegarage.app.messagebox.showwarning", side_effect=AssertionError):
            root = Path(tmp)
            app = GarageApp(root)
            try:
                app.geometry("900x640")
                app.show_page("garage")
                app.library.save(Creation("First", slot=0))
                other = app.garages.create("Other", [Creation("Occupied", slot=0)])
                app._refresh_garage_picker()
                app._refresh_garage()
                app.update()
                self.assertTrue(app.garage_picker.winfo_ismapped())
                app.tree.selection_set("1")
                app._file_selected(False)
                window = next(w for w in app.winfo_children() if isinstance(w, tk.Toplevel))
                button = next(w for w in window.winfo_children()[0].winfo_children() if w.winfo_class() == "TButton")
                with patch("vehiclegarage.app.messagebox.showinfo") as info:
                    button.invoke()
                self.assertTrue(info.called)
                self.assertFalse(app.garages.library(other).all()[1].enabled)
                app.garage_picker.set("Other")
                app._choose_garage()
                self.assertEqual(app.garages.active_id, other)
                self.assertEqual(len(app.library.all()), 2)
                app.build_collection.set("garage")
                app._refresh_install_summary()
                self.assertIn("Other", app.install_summary.cget("text"))
                path = root / "export.json"
                with patch.object(app.settings, "picker_folder", return_value=root), \
                        patch("vehiclegarage.app.filedialog.asksaveasfilename", return_value=str(path)), \
                        patch("vehiclegarage.app.messagebox.showinfo"):
                    app._export_garage()
                self.assertEqual(garages.import_file(path)[1], "Other")
                with patch.object(app, "_choose_path", return_value=str(path)), \
                        patch("vehiclegarage.app.simpledialog.askstring", return_value="Imported"), \
                        patch("vehiclegarage.app.messagebox.showinfo"):
                    app._import_garage_file()
                self.assertEqual(app.garages.active_name, "Imported")
                self.assertEqual([c.name for c in app.library.all()], ["Occupied", "First"])
                with patch.object(app, "_choose_path", return_value=str(presets.DEFAULT_FILE)), \
                        patch("vehiclegarage.app.simpledialog.askstring", return_value="OnnY"), \
                        patch("vehiclegarage.app.messagebox.showinfo"):
                    app._import_garage_file()
                self.assertEqual(app.garages.active_name, "OnnY")
                self.assertEqual(len(app.library.all()), 36)
                self.assertTrue(app.garages.fit_names())
                app.show_page("install")
                app._refresh_install_summary()
                app.update()
                self.assertIn("... and 30 more.", app.install_summary.cget("text"))
                self.assertTrue(app.build_button.winfo_ismapped())
                self.assertLessEqual(app.build_button.winfo_rooty() + app.build_button.winfo_height(),
                                     app.winfo_rooty() + app.winfo_height())
                app.show_page("garage")
                app._manage_garages()
                app.update()
                window = next(w for w in app.winfo_children() if isinstance(w, tk.Toplevel))
                self.assertEqual(window.title(), "Manage garages")
                self.assertTrue(window.winfo_ismapped())
                frame = window.winfo_children()[0]
                actions = next(w for w in frame.winfo_children() if w.winfo_class() == "TFrame")
                for button in actions.winfo_children():
                    self.assertTrue(button.winfo_ismapped(), button.cget("text"))
                    self.assertLessEqual(button.winfo_rootx() + button.winfo_width(),
                                         window.winfo_rootx() + window.winfo_width())
            finally:
                for timer in app.tk.splitlist(app.tk.call("after", "info")):
                    app.after_cancel(timer)
                app.destroy()


if __name__ == "__main__":
    unittest.main()
