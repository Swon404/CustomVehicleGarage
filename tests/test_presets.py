import tempfile
import unittest
import json
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.test_archives import build_u8
from tests.test_bmg import build_bmg
from tests.test_export import fake_szs
from vehiclegarage import bmg, disc, export, presets, u8, yaz0
from vehiclegarage.app import GarageApp
from vehiclegarage.kartparam import KartParam
from vehiclegarage.machinepara import MachinePara
from vehiclegarage.stats import ADVANCED_FIELDS, BARS, format_value


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
        self.assertEqual(len({item.name for item in examples}), 36)
        self.assertGreater(examples[0].stats["speed"], examples[4].stats["speed"])
        self.assertEqual(examples[0].name, "Feather")
        self.assertGreaterEqual(examples[0].stats["speed"], 95)
        self.assertLessEqual(examples[0].stats["weight"], 2)
        self.assertTrue(all(bmg.valid_vehicle_name(item.name) for item in examples))
        examples[0].stats["speed"] = 1
        self.assertNotEqual(presets.creations()[0].stats["speed"], 1)

    def test_draft_persists_and_export_is_consumable_as_bundled_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = presets.creations()[0]
            edited = presets.creations()[0]
            edited.name = "My Bolt"
            edited.stats["speed"] = 99.125
            edited.stats["tilt"] = 0.03125
            presets.save_draft(root, edited)
            self.assertEqual(presets.creations(root)[0], edited)
            self.assertEqual(presets.creations()[0], original)
            exported = root / "export.json"
            presets.write(exported, presets.creations(root))
            self.assertEqual(presets.read(exported), presets.creations(root))
            with patch.object(presets, "DEFAULT_FILE", exported):
                self.assertEqual(presets.creations()[0], edited)

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
            root_dir=Path("unused"), settings=SimpleNamespace(
                picker_folder=Mock(return_value=Path(".")), remember_folder=Mock(),
            ),
        )
        with patch("vehiclegarage.app.OFFICIAL_RELEASE", False), \
                patch("vehiclegarage.app.filedialog.asksaveasfilename", return_value=""), \
                patch("vehiclegarage.app.presets.write") as write:
            GarageApp._export_presets(app)
        write.assert_not_called()
        app.settings.remember_folder.assert_not_called()

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
            vehicle = KartParam.from_bytes(u8.read_file(raw, "kartParam.bin")).vehicles[0]
            self.assertAlmostEqual(vehicle.get("speed"), fitted[0].stats["speed"], places=4)
            ui = yaz0.decompress((output / export.MOD_FOLDER / "Scene" / "UI" / "MenuSingle.szs").read_bytes())
            rating = MachinePara(u8.read_file(ui, "parameter/machine_para.bin"))
            self.assertEqual(rating.vehicle_stat(0, 0), 19)
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
            presets.save_draft(root, edited)
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

    def test_preset_save_uses_draft_not_garage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing = presets.creations()[0]
            stats = dict(existing.stats)
            stats["speed"] = 99.0
            app = SimpleNamespace(
                _current_slot=lambda: 0, name_var=Mock(get=Mock(return_value="New Bolt")),
                _preset_edit_slot=0, edit_texture=None, editing=existing,
                _collect_stats=Mock(return_value=stats), root_dir=root, library=Mock(),
                _refresh_install_summary=Mock(), show_page=Mock(),
            )
            with patch("vehiclegarage.app.OFFICIAL_RELEASE", False):
                GarageApp._save_creation(app)
            self.assertEqual(presets.creations(root)[0].name, "New Bolt")
            self.assertEqual(presets.creations(root)[0].stats["speed"], 99.0)
            self.assertEqual(app._collect_stats.call_args.args[1], {bar.field for bar in BARS})
            app.library.save.assert_not_called()
            app.show_page.assert_called_once_with("install")

    def test_preset_editor_keeps_explicit_values_matching_stock(self):
        stock = {bar.field: 0.024 for bar in BARS}
        stock.update({field: 0.0186 for field, _, _ in ADVANCED_FIELDS})
        stock["mini_turbo_duration"] = 29
        bars = {bar.key: (format_value(stock[bar.field]), stock[bar.field]) for bar in BARS}
        advanced = {field: (format_value(stock[field]), stock[field]) for field, _, _ in ADVANCED_FIELDS}
        app = SimpleNamespace(
            _bar_values=bars, _advanced_values=advanced,
            bar_value_vars={key: Mock(get=Mock(return_value=value[0])) for key, value in bars.items()},
            advanced_vars={key: Mock(get=Mock(return_value=value[0])) for key, value in advanced.items()},
            _stock_value=lambda _slot, field: stock[field],
        )
        fields = {bar.field for bar in BARS} | {"tilt"}
        self.assertEqual(GarageApp._collect_stats(app, 0, fields), {key: stock[key] for key in fields})


if __name__ == "__main__":
    unittest.main()
