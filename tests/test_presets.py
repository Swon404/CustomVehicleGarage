import tempfile
import tkinter as tk
import unittest
import json
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.test_archives import build_u8
from tests.test_bmg import build_bmg
from tests.test_export import fake_szs, stock_kartparam
from vehiclegarage import bmg, disc, export, presets, u8, yaz0
from vehiclegarage.app import GarageApp
from vehiclegarage.creations import Creation
from vehiclegarage.kartparam import KartParam
from vehiclegarage.machinepara import MachinePara
from vehiclegarage.vehicles import VEHICLES


def full_name_archive() -> bytes:
    messages = [
        (message_id, "abc" if slot == 0 else "Long stock name")
        for slot in range(36)
        for message_id in bmg.vehicle_name_message_ids(slot)
    ]
    return yaz0.compress(build_u8({".": {"message": {"Common.bmg": build_bmg(messages)}}}))


class PresetTests(unittest.TestCase):
    def test_collection_covers_all_slots_and_returns_independent_creations(self):
        examples = presets.creations()
        self.assertEqual([item.slot for item in examples], list(range(36)))
        self.assertEqual(len({item.name.casefold() for item in examples}), 36)
        self.assertEqual(len({json.dumps(item.stats, sort_keys=True) for item in examples}), 36)
        self.assertGreater(examples[0].stats["speed"], examples[4].stats["speed"])
        self.assertEqual(examples[0].name, "Feather")
        self.assertGreaterEqual(examples[0].stats["speed"], 95)
        self.assertLessEqual(examples[0].stats["weight"], 2)
        self.assertEqual(examples[0].stats["speed"], 150.0)
        self.assertEqual(examples[0].stats["weight"], 0.001)
        self.assertEqual(examples[2].name, "CursedKart")
        self.assertEqual(examples[2].stats["mega_mushroom_scale"], 5.0)
        self.assertEqual(examples[2].stats["shock_scale"], 0.01)
        self.assertTrue(all(bmg.valid_vehicle_name(item.name) for item in examples))
        examples[0].stats["speed"] = 1
        self.assertNotEqual(presets.creations()[0].stats["speed"], 1)

    def test_preset_mix_is_shared_between_weight_classes_and_vehicle_types(self):
        examples = presets.creations()
        faster = {
            "Feather", "Rocket", "Blaizing", "Vortex", "Phoenix", "Thunder",
            "Cyclone", "Comet", "Falcon", "Meteor", "Quasar", "Nitro",
        }
        weaker = {
            "Rust", "Clanker", "Poo", "Banana", "Snail", "Slugger", "Wobbler",
            "Mudtrap", "CursedKart", "Brick", "Sheep", "Jelly", "Tanky",
            "Handler", "TurtleHead",
        }
        for weight_class in range(3):
            for kind in ("Kart", "Bike"):
                group = [item for item in examples if VEHICLES[item.slot].weight_class == weight_class
                         and VEHICLES[item.slot].kind == kind]
                self.assertEqual(sum(item.name in faster for item in group), 2, (weight_class, kind))
                self.assertEqual(sum(item.name in weaker for item in group),
                                 3 if kind == "Kart" else 2, (weight_class, kind))
        by_name = {item.name: item for item in examples}
        self.assertEqual(by_name["Vortex"].stats["drift_target_angle"], 90.0)
        self.assertEqual(by_name["Jelly"].stats["accel_a1"], 1.75)
        self.assertEqual(by_name["Poo"].stats["bump_deviation"], 40.0)
        self.assertLess(by_name["Mudtrap"].stats["speed_multiplier_3"], 0.1)
        self.assertEqual(by_name["Spinout"].stats["manual_drift"], 0.5)

    def test_garage_conversion_is_consumable_as_bundled_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items = presets.creations()
            items[0].number = 123
            items[0].name = "Edited"
            items[0].stats["speed"] = 99.125
            items[0].stats["tilt"] = 0.03125
            del items[0].stats["weight"]
            items.append(Creation("Unused alternative", slot=0, enabled=False))
            stock = KartParam.from_bytes(stock_kartparam())
            converted = presets.from_garage(items, stock)
            self.assertEqual(converted[0].stats["speed"], 99.125)
            self.assertEqual(converted[0].stats["tilt"], 0.03125)
            self.assertEqual(converted[0].stats["weight"], stock.vehicles[0].get("weight"))
            self.assertEqual(converted[0].number, 0)
            self.assertNotIn("weight", items[0].stats)
            exported = root / "export.json"
            presets.write(exported, converted)
            self.assertEqual(presets.read(exported), converted)
            with patch.object(presets, "DEFAULT_FILE", exported):
                self.assertEqual(presets.creations()[0], converted[0])

    def test_garage_conversion_rejects_missing_conflicting_or_unsupported_data(self):
        items = presets.creations()
        with self.assertRaisesRegex(ValueError, "Missing:"):
            presets.from_garage(items[:-1], None)
        with self.assertRaisesRegex(ValueError, "More than one"):
            presets.from_garage(items + [items[0]], None)
        items[0].stats.pop("weight")
        with self.assertRaisesRegex(ValueError, "Import game data"):
            presets.from_garage(items, None)
        items[0].stats["weight"] = 2
        items[0].stats["tires"] = 1
        with self.assertRaisesRegex(ValueError, "unsupported preset stats.*tires"):
            presets.from_garage(items, None)
        del items[0].stats["tires"]
        from vehiclegarage.textures import TexturePack
        items[0].texture = TexturePack("Paint", 0, {"sdf_kart-bmr.szs": "a" * 64})
        with self.assertRaisesRegex(ValueError, "cannot include textures"):
            presets.from_garage(items, None)

    def test_invalid_draft_is_reported_and_failed_export_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / presets.DRAFT_FILE).write_text('{"version": 1, "vehicles": []}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "36"):
                presets.creations(root)
            output = root / "existing.json"
            output.write_text("unchanged", encoding="utf-8")
            items = presets.creations()
            items[0].stats["speed"] = float("nan")
            with self.assertRaisesRegex(ValueError, "finite"):
                presets.write(output, items)
            self.assertEqual(output.read_text(encoding="utf-8"), "unchanged")

    def test_invalid_collection_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.json"
            presets.write(path, presets.creations())
            data = json.loads(path.read_text(encoding="utf-8"))
            data["vehicles"][0]["stats"]["mini_turbo_duration"] = True
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "number"):
                presets.read(path)

    def test_export_cancel_does_not_change_folder_or_files(self):
        app = SimpleNamespace(
            root_dir=Path("unused"), library=Mock(all=Mock(return_value=presets.creations())),
            stock=None, settings=SimpleNamespace(
                picker_folder=Mock(return_value=Path(".")), remember_folder=Mock(),
            ),
        )
        with patch("vehiclegarage.app.OFFICIAL_RELEASE", False), \
                patch("vehiclegarage.app.filedialog.asksaveasfilename", return_value=""), \
                patch("vehiclegarage.app.presets.write") as write:
            GarageApp._export_presets(app)
        write.assert_not_called()
        app.settings.remember_folder.assert_not_called()

    def test_export_errors_leave_existing_file_and_garage_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "onny.json"
            output.write_text("unchanged", encoding="utf-8")
            items = presets.creations()[:-1]
            app = SimpleNamespace(
                library=Mock(all=Mock(return_value=items)), stock=None, root_dir=root,
                settings=SimpleNamespace(picker_folder=Mock(return_value=root), remember_folder=Mock()),
            )
            with patch("vehiclegarage.app.OFFICIAL_RELEASE", False), \
                    patch("vehiclegarage.app.filedialog.asksaveasfilename") as save, \
                    patch("vehiclegarage.app.messagebox.showerror") as error:
                GarageApp._export_presets(app)
            self.assertIn("Missing", error.call_args.args[1])
            save.assert_not_called()
            self.assertEqual(output.read_text(encoding="utf-8"), "unchanged")
            app.library.save.assert_not_called()

    def test_fits_names_and_builds_all_36_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / "game"
            for archive, inner in disc.kartparam_archives("RMCJ01").items():
                path = game / archive
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(fake_szs(inner))
            names = full_name_archive()
            for archive in disc.localized_message_archives("RMCJ01"):
                path = game / archive
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(names)
            originals = presets.creations()
            fitted, shortened = presets.fit_names(originals, game, "RMCJ01", lambda: None)
            self.assertEqual(fitted[0].name, "Fea")
            self.assertIn("Feather -> Fea", shortened)
            self.assertEqual(originals[0].name, "Feather")
            output = root / "out"
            export.build_mod(game, "RMCJ01", fitted, output)
            raw = yaz0.decompress((output / export.MOD_FOLDER / "Race" / "Common.szs").read_bytes())
            vehicles = KartParam.from_bytes(u8.read_file(raw, "kartParam.bin")).vehicles
            vehicle = vehicles[0]
            self.assertAlmostEqual(vehicle.get("speed"), fitted[0].stats["speed"], places=4)
            self.assertAlmostEqual(vehicles[2].get("mega_mushroom_scale"), 5.0)
            self.assertAlmostEqual(vehicles[2].get("shock_scale"), 0.01)
            ui = yaz0.decompress((output / export.MOD_FOLDER / "Scene" / "UI" / "MenuSingle.szs").read_bytes())
            rating = MachinePara(u8.read_file(ui, "parameter/machine_para.bin"))
            self.assertEqual(rating.vehicle_stat(0, 0), 49)
            message = yaz0.decompress((output / export.MOD_FOLDER / "Scene" / "UI" / "MenuSingle_J.szs").read_bytes())
            self.assertEqual(bmg.read_message(u8.read_file(message, "message/Common.bmg"), 9100), "Fea")

            originals[0].name = "🚗🚗"
            fitted, shortened = presets.fit_names(originals, game, "RMCJ01", lambda: None)
            self.assertEqual(fitted[0].name, "🚗")
            self.assertTrue(shortened)

    def test_missing_localized_archive_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "Re-import"):
                presets.fit_names(presets.creations(), Path(tmp), "RMCJ01", lambda: None)

    def test_preset_name_preparation_can_be_cancelled(self):
        def cancel():
            raise export.BuildCancelled()

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(export.BuildCancelled):
                presets.fit_names(presets.creations(), Path(tmp), "RMCJ01", cancel)

    def test_selecting_examples_does_not_read_or_modify_garage(self):
        app = SimpleNamespace(
            build_collection=Mock(get=Mock(return_value="onny")), library=Mock(),
            install_summary=Mock(), root_dir=Path("unused"),
        )
        GarageApp._refresh_install_summary(app)
        app.library.all.assert_not_called()
        self.assertIn("36", app.install_summary.config.call_args.kwargs["text"])
        self.assertIn("unchanged", app.install_summary.config.call_args.kwargs["text"])

    def test_build_uses_only_selected_preset_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = SimpleNamespace(game_id="RMCJ01", disc="", dolphintool="", save=Mock())
            app = SimpleNamespace(
                _require_stock=lambda: True, build_collection=Mock(get=Mock(return_value="onny")),
                library=Mock(), _install_targets=lambda: [root / "out"],
                settings=settings, use_riivolution=Mock(get=Mock(return_value=False)),
                use_sd_sync=Mock(get=Mock(return_value=False)), use_custom=Mock(get=Mock(return_value=True)),
                custom_var=Mock(get=Mock(return_value=str(root / "out"))),
                root_dir=root, cache=root / "cache", build_button=Mock(), play_button=Mock(),
                cancel_build_button=Mock(), install_status=Mock(), progress=Mock(), events=Queue(),
                _run_in_background=lambda work, done: done(work(), None),
            )
            fitted = presets.creations()
            with patch("vehiclegarage.app.presets.fit_names", return_value=(fitted, [])), \
                    patch("vehiclegarage.app.export.install_mod", return_value=[root / "out"]) as install:
                GarageApp._build_mod(app)
            self.assertEqual(len(install.call_args.args[2]), 36)
            self.assertEqual(settings.build_collection, "onny")
            app.library.all.assert_not_called()
            app.library.save.assert_not_called()

    def test_build_uses_draft_only_in_development(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edited = presets.creations()[0]
            edited.name = "Draft"
            draft = presets.creations()
            draft[0] = edited
            presets.write(root / presets.DRAFT_FILE, draft)
            settings = SimpleNamespace(game_id="RMCJ01", disc="", dolphintool="", save=Mock())
            app = SimpleNamespace(
                _require_stock=lambda: True, build_collection=Mock(get=Mock(return_value="onny")),
                library=Mock(), _install_targets=lambda: [root / "out"],
                settings=settings, use_riivolution=Mock(get=Mock(return_value=False)),
                use_sd_sync=Mock(get=Mock(return_value=False)), use_custom=Mock(get=Mock(return_value=True)),
                custom_var=Mock(get=Mock(return_value=str(root / "out"))),
                root_dir=root, cache=root / "cache", build_button=Mock(), play_button=Mock(),
                cancel_build_button=Mock(), install_status=Mock(), progress=Mock(), events=Queue(),
                _run_in_background=lambda work, done: done(work(), None),
            )
            with patch("vehiclegarage.app.presets.fit_names", side_effect=lambda items, *_: (items, [])), \
                    patch("vehiclegarage.app.export.install_mod", return_value=[root / "out"]) as install:
                with patch("vehiclegarage.app.OFFICIAL_RELEASE", False):
                    GarageApp._build_mod(app)
                self.assertEqual(install.call_args.args[2][0].name, "Draft")
                with patch("vehiclegarage.app.OFFICIAL_RELEASE", True):
                    GarageApp._build_mod(app)
                self.assertEqual(install.call_args.args[2][0].name, "Feather")


class PresetUiTests(unittest.TestCase):
    def test_development_exports_active_garage_and_release_hides_tool(self):
        try:
            probe = tk.Tk()
        except tk.TclError as err:
            self.skipTest(f"Tk display unavailable: {err}")
        probe.destroy()
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(GarageApp, "_autodetect_tool"), patch.object(GarageApp, "_check_update"), \
                patch("vehiclegarage.app.messagebox.showerror", side_effect=AssertionError):
            root = Path(tmp)
            draft = presets.creations()
            draft[0].name = "Old Draft"
            presets.write(root / presets.DRAFT_FILE, draft)
            for official in (False, True):
                with patch("vehiclegarage.app.OFFICIAL_RELEASE", official):
                    app = GarageApp(root)
                    try:
                        app.show_page("garage")
                        app.update()
                        def descendants(widget):
                            result = []
                            for child in widget.winfo_children():
                                result.append(child)
                                result.extend(descendants(child))
                            return result
                        widgets = descendants(app.pages["garage"])
                        menu_buttons = [w for w in widgets if w.winfo_class() == "TMenubutton"
                                        and w.cget("text") == "EXPORT"]
                        self.assertEqual(len(menu_buttons), 0 if official else 1)
                        app._show_presets()
                        app.update()
                        window = next(w for w in app.winfo_children() if isinstance(w, tk.Toplevel))
                        labels = [w.cget("text") for w in descendants(window) if w.winfo_class() == "TButton"]
                        self.assertIn("EDIT GARAGE COPY", labels)
                        self.assertNotIn("EDIT PRESET", labels)
                        self.assertNotIn("EXPORT JSON", labels)
                        window.destroy()
                        if not official:
                            self.assertEqual(presets.creations(root)[0].name, "Old Draft")
                            garage_id = app.garages.create("Edited Garage", presets.creations(root))
                            app._activate_garage(garage_id)
                            item = app.library.all()[0]
                            item.name = "Garage Edit"
                            app.library.save(item)
                            destination = root / "onny-export.json"
                            menu = app.nametowidget(menu_buttons[0].cget("menu"))
                            with patch.object(app.settings, "picker_folder", return_value=root), \
                                    patch("vehiclegarage.app.filedialog.asksaveasfilename", return_value=str(destination)), \
                                    patch("vehiclegarage.app.messagebox.showinfo"):
                                menu.invoke(1)
                            self.assertEqual(presets.read(destination)[0].name, "Garage Edit")
                            self.assertEqual(presets.read(root / presets.DRAFT_FILE)[0].name, "Old Draft")
                    finally:
                        for timer in app.tk.splitlist(app.tk.call("after", "info")):
                            app.after_cancel(timer)
                        app.destroy()

if __name__ == "__main__":
    unittest.main()
