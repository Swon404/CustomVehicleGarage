import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_archives import build_u8
from tests.test_bmg import build_bmg
from vehiclegarage import bmg, disc, export, u8, yaz0
from vehiclegarage.creations import Creation, Library, slot_conflicts
from vehiclegarage.kartparam import SECTION_SIZE, KartParam
from vehiclegarage.machinepara import FILE_SIZE, MachinePara
from vehiclegarage.stats import BARS


def stock_kartparam() -> bytes:
    body = b"".join(bytes([i + 1]) * SECTION_SIZE for i in range(36))
    return (36).to_bytes(4, "big") + body


def stock_machinepara() -> bytes:
    return b"".join(i.to_bytes(2, "big", signed=True) for i in range(FILE_SIZE // 2))


def fake_szs(inner_path: str) -> bytes:
    parts = inner_path.split("/")
    tree: dict = {"other.bin": b"keep me" * 50}
    node = tree
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = stock_kartparam()
    if inner_path != "kartParam.bin":
        node["machine_para.bin"] = stock_machinepara()
    return yaz0.compress(build_u8({".": tree}))


def fake_name_szs() -> bytes:
    messages = build_bmg(
        [
            (9100, "Standard Kart S"),
            (9118, "Standard Kart S"),
            (9121, "Standard Kart S"),
            (9101, "Standard Kart M"),
        ]
    )
    return yaz0.compress(build_u8({".": {"message": {"Common.bmg": messages}}}))


class CreationTests(unittest.TestCase):
    def test_rejects_unknown_stat_and_bad_slot(self):
        with self.assertRaises(ValueError):
            Creation("x", {"bogus": 1})
        with self.assertRaises(ValueError):
            Creation("x", {}, slot=36)

    def test_library_numbers_from_next_free_number_and_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Library(Path(tmp))
            a = library.save(Creation("A", {"speed": 90.0}, slot=3))
            b = library.save(Creation("B", {}, slot=4))
            self.assertEqual((a.number, b.number), (1, 2))
            library.delete(1)
            self.assertEqual(library.save(Creation("C", {}, slot=5)).number, 3)
            self.assertEqual([c.name for c in library.all()], ["B", "C"])
            self.assertEqual(library.all()[0].slot, 4)

    def test_slot_conflicts_ignore_disabled(self):
        a = Creation("A", slot=2)
        b = Creation("B", slot=2)
        self.assertEqual(list(slot_conflicts([a, b])), [2])
        b.enabled = False
        self.assertEqual(slot_conflicts([a, b]), {})


class ExportTests(unittest.TestCase):
    def test_region_specific_parameter_and_message_archives(self):
        for game, suffixes in (
            ("RMCE01", ("M", "Q", "U")),
            ("RMCP01", ("E", "F", "G", "I", "S")),
            ("RMCJ01", ("J",)),
            ("RMCK01", ("K",)),
        ):
            with self.subTest(game=game):
                archives = disc.kartparam_archives(game)
                self.assertEqual(len(archives), 8)
                self.assertIn("Race/Common.szs", archives)
                expected = "Scene/UI/MenuSingle_R.szs" if game == "RMCK01" else "Scene/UI/MenuSingle.szs"
                self.assertEqual(archives[expected], "parameter/kartParam.bin")
                names = disc.localized_message_archives(game)
                self.assertEqual(len(names), 10 * len(suffixes))
                for suffix in suffixes:
                    self.assertIn(f"Scene/UI/MenuSingle_{suffix}.szs", names)
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            disc.kartparam_archives("RMCX01")

    def test_korean_export_patches_r_archives_and_k_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / "game"
            for archive, inner in disc.kartparam_archives("RMCK01").items():
                path = game / archive
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(fake_szs(inner))
            for archive in disc.localized_message_archives("RMCK01"):
                path = game / archive
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(fake_name_szs())
            out = root / "out"
            export.build_mod(game, "RMCK01", [Creation("Garage", {"speed": 90.0}, slot=0)], out)
            xml = (out / "riivolution" / "CustomVehicleGarage.xml").read_text()
            self.assertIn('<id game="RMCK"/>', xml)
            self.assertIn('disc="/Scene/UI/MenuSingle_R.szs"', xml)
            self.assertIn('disc="/Scene/UI/MenuSingle_K.szs"', xml)
            params = yaz0.decompress((out / export.MOD_FOLDER / "Scene" / "UI" / "MenuSingle_R.szs").read_bytes())
            kart = KartParam.from_bytes(u8.read_file(params, "parameter/kartParam.bin"))
            self.assertEqual(kart.vehicles[0].get("speed"), 90.0)
            names = yaz0.decompress((out / export.MOD_FOLDER / "Scene" / "UI" / "MenuSingle_K.szs").read_bytes())
            self.assertEqual(bmg.read_message(u8.read_file(names, "message/Common.bmg"), 9100), "Garage")

    def test_missing_parameter_archives_fail_before_replacing_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "game"
            (cache / "Race").mkdir(parents=True)
            (cache / "Race" / "Common.szs").write_bytes(fake_szs("kartParam.bin"))
            old = root / "out" / export.MOD_FOLDER / "old.txt"
            old.parent.mkdir(parents=True)
            old.write_text("keep")
            with self.assertRaisesRegex(ValueError, "parameter archives"):
                export.build_mod(cache, "RMCK01", [Creation("Standard Kart M", {"speed": 90}, slot=1)], root / "out")
            self.assertEqual(old.read_text(), "keep")

    def test_build_stats_and_names_for_each_game_region(self):
        for game_id, language in (("RMCE01", "U"), ("RMCP01", "E"), ("RMCJ01", "J"), ("RMCK01", "K")):
            with self.subTest(game_id=game_id), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                cache = root / "game"
                for archive, inner in disc.kartparam_archives(game_id).items():
                    path = cache / archive
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(fake_szs(inner))
                for archive in disc.localized_message_archives(game_id):
                    path = cache / archive
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(fake_name_szs())
                out = root / "out"
                export.build_mod(cache, game_id, [Creation("Garage", {"speed": 90}, slot=0)], out)
                xml = (out / "riivolution" / "CustomVehicleGarage.xml").read_text()
                self.assertIn(f'<id game="{game_id[:4]}"/>', xml)
                names_path = out / export.MOD_FOLDER / "Scene" / "UI" / f"MenuSingle_{language}.szs"
                names = yaz0.decompress(names_path.read_bytes())
                self.assertEqual(bmg.read_message(u8.read_file(names, "message/Common.bmg"), 9100), "Garage")

    def test_numeric_stat_values_allow_over_range_and_reject_invalid_values(self):
        speed = next(bar for bar in BARS if bar.key == "speed")
        turbo = next(bar for bar in BARS if bar.key == "turbo")
        self.assertEqual(speed.parse_value("157.42"), 157.42)
        self.assertEqual(speed.to_display_rating(157.42), 53)
        self.assertEqual(speed.to_display_rating(100), 20)
        self.assertEqual(turbo.parse_value("240"), 240)
        with self.assertRaises(ValueError):
            turbo.parse_value("240.5")
        with self.assertRaises(ValueError):
            speed.parse_value("nan")
        with self.assertRaises(ValueError):
            speed.to_display_rating(100000)

    def test_build_machinepara_extrapolates_over_range_menu_rating(self):
        base = stock_machinepara()
        updated = MachinePara(
            export.build_machinepara(base, [Creation("A", {"speed": 157.42}, slot=7)])
        )
        self.assertEqual(updated.vehicle_stat(7, 0), 53)

    def test_offroad_bar_updates_standard_offroad_gameplay_and_display_stats(self):
        creation = Creation("A", {"speed_multiplier_3": 0.8}, slot=7)
        kart = KartParam.from_bytes(export.build_kartparam(stock_kartparam(), [creation]))
        machine = MachinePara(export.build_machinepara(stock_machinepara(), [creation]))
        self.assertAlmostEqual(kart.vehicles[7].get("speed_multiplier_3"), 0.8)
        self.assertEqual(machine.vehicle_stat(7, 5), 16)

    def test_build_vehicle_name_bmg_handles_translated_stock_label(self):
        source = build_bmg(
            [
                (9100, "Kart Estandar S"),
                (9118, "Kart Estandar S"),
                (9121, "Kart Estandar S"),
            ]
        )
        patched = export.build_vehicle_name_bmg(source, [Creation("Garage Kart", slot=0)])
        for message_id in bmg.vehicle_name_message_ids(0):
            self.assertEqual(bmg.read_message(patched, message_id), "Garage Kart")

    def test_build_kartparam_changes_only_target_slot(self):
        out = export.build_kartparam(stock_kartparam(), [Creation("A", {"speed": 95.5}, slot=7)])
        before, after = KartParam.from_bytes(stock_kartparam()), KartParam.from_bytes(out)
        self.assertAlmostEqual(after.vehicles[7].get("speed"), 95.5, places=3)
        for i in range(36):
            if i != 7:
                self.assertEqual(after.vehicles[i].raw, before.vehicles[i].raw)

    def test_build_machinepara_updates_matching_bars_only(self):
        creation = Creation(
            "A",
            {
                "speed": 100.0,
                "weight": 7.5,
                "accel_a0": 1.0,
                "manual_handling": 0.06,
                "manual_drift": 0.04,
                "mini_turbo_duration": 60,
            },
            slot=7,
        )
        base = stock_machinepara()
        updated = MachinePara(export.build_machinepara(base, [creation]))
        original = MachinePara(base)
        expected = {0: 20, 1: 20, 2: 20, 3: 20, 4: 20, 6: 20}
        for stat, score in expected.items():
            self.assertEqual(updated.vehicle_stat(7, stat), score)
        self.assertEqual(updated.vehicle_stat(7, 5), original.vehicle_stat(7, 5))
        for slot in range(36):
            if slot != 7:
                for stat in range(7):
                    self.assertEqual(updated.vehicle_stat(slot, stat), original.vehicle_stat(slot, stat))

    def test_patch_archive_keeps_other_files(self):
        szs = fake_szs("parameter/kartParam.bin")
        patched = export.patch_archive(
            szs,
            "parameter/kartParam.bin",
            [Creation("A", {"weight": 6.0}, slot=0)],
        )
        data = yaz0.decompress(patched)
        self.assertEqual(u8.read_file(data, "other.bin"), b"keep me" * 50)
        self.assertAlmostEqual(KartParam.from_bytes(u8.read_file(data, "parameter/kartParam.bin")).vehicles[0].get("weight"), 6.0, places=3)
        self.assertEqual(
            MachinePara(u8.read_file(data, "parameter/machine_para.bin")).vehicle_stat(0, 1),
            15,
        )

    def test_build_mod_writes_archives_and_xml(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "game"
            for archive, inner in export.KARTPARAM_ARCHIVES.items():
                (cache / archive).parent.mkdir(parents=True, exist_ok=True)
                (cache / archive).write_bytes(fake_szs(inner))
            out = Path(tmp) / "out"
            export.build_mod(cache, "RMCE01", [Creation("Standard Kart M", {"speed": 90.0}, slot=1), Creation("Off", {"speed": 1.0}, slot=1, enabled=False)], out)
            for archive in export.KARTPARAM_ARCHIVES:
                self.assertTrue((out / "CustomVehicleGarage" / archive).is_file())
            self.assertEqual(len(export.KARTPARAM_ARCHIVES), 8)
            xml = (out / "riivolution" / "CustomVehicleGarage.xml").read_text()
            self.assertIn('<id game="RMCE"/>', xml)
            self.assertIn('disc="/Race/Common.szs" external="/CustomVehicleGarage/Race/Common.szs"', xml)
            self.assertIn('disc="/Scene/UI/Award.szs"', xml)

    def test_build_mod_patches_names_in_all_localized_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "game"
            for archive, inner in export.KARTPARAM_ARCHIVES.items():
                (cache / archive).parent.mkdir(parents=True, exist_ok=True)
                (cache / archive).write_bytes(fake_szs(inner))
            for archive in disc.localized_message_archives("RMCE01"):
                path = cache / archive
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(fake_name_szs())

            out = Path(tmp) / "out"
            export.build_mod(cache, "RMCE01", [Creation("Garage Kart", {"speed": 90.0}, slot=0)], out)

            localized = "Scene/UI/MenuSingle_U.szs"
            self.assertTrue((out / "CustomVehicleGarage" / localized).is_file())
            xml = (out / "riivolution" / "CustomVehicleGarage.xml").read_text()
            self.assertIn(f'disc="/{localized}"', xml)
            archive = yaz0.decompress((out / "CustomVehicleGarage" / localized).read_bytes())
            common = u8.read_file(archive, "message/Common.bmg")
            for message_id in bmg.vehicle_name_message_ids(0):
                self.assertEqual(bmg.read_message(common, message_id), "Garage Kart")
            self.assertEqual(len(disc.localized_message_archives("RMCE01")), 30)

    def test_custom_name_requires_reimported_localized_archives_without_deleting_old_mod(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "game"
            for archive, inner in export.KARTPARAM_ARCHIVES.items():
                (cache / archive).parent.mkdir(parents=True, exist_ok=True)
                (cache / archive).write_bytes(fake_szs(inner))
            out = Path(tmp) / "out"
            old_mod = out / export.MOD_FOLDER / "old.txt"
            old_mod.parent.mkdir(parents=True)
            old_mod.write_text("keep")

            with self.assertRaisesRegex(ValueError, "Re-import the game disc"):
                export.build_mod(cache, "RMCE01", [Creation("Garage Kart", {}, slot=0)], out)
            self.assertEqual(old_mod.read_text(), "keep")

    def test_install_mod_copies_to_every_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "game"
            for archive, inner in export.KARTPARAM_ARCHIVES.items():
                (cache / archive).parent.mkdir(parents=True, exist_ok=True)
                (cache / archive).write_bytes(fake_szs(inner))
            targets = [Path(tmp) / "riivolution-root", Path(tmp) / "sd-sync"]
            export.install_mod(cache, "RMCE01", [Creation("Standard Kart M", {"speed": 90.0}, slot=1)], targets)
            for target in targets:
                self.assertTrue((target / "riivolution" / "CustomVehicleGarage.xml").is_file())
                self.assertTrue((target / "CustomVehicleGarage" / "Race" / "Common.szs").is_file())
            self.assertEqual(
                (targets[0] / "CustomVehicleGarage" / "Race" / "Common.szs").read_bytes(),
                (targets[1] / "CustomVehicleGarage" / "Race" / "Common.szs").read_bytes(),
            )

    def test_cancellation_during_packing_and_copy_keeps_all_old_installations(self):
        for phase in ("Packing", "Preparing"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                cache = root / "game"
                for archive, inner in export.KARTPARAM_ARCHIVES.items():
                    path = cache / archive
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(fake_szs(inner))
                targets = [root / "one", root / "two"]
                for target in targets:
                    old = target / export.MOD_FOLDER / "old.txt"
                    old.parent.mkdir(parents=True)
                    old.write_text("old mod")
                    xml = target / "riivolution" / "CustomVehicleGarage.xml"
                    xml.parent.mkdir()
                    xml.write_text("old xml")
                token = export.BuildCancellation()
                def progress(message, fraction):
                    if message.startswith(phase):
                        token.cancel()
                with self.assertRaises(export.BuildCancelled):
                    export.install_mod(cache, "RMCE01", [Creation("Standard Kart M", {"speed": 90}, slot=1)],
                                       targets, progress, cancel=token)
                for target in targets:
                    self.assertEqual((target / export.MOD_FOLDER / "old.txt").read_text(), "old mod")
                    self.assertEqual((target / "riivolution" / "CustomVehicleGarage.xml").read_text(), "old xml")

    def test_cache_reuses_unchanged_archives_and_invalidates_changed_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / "game"
            for archive, inner in export.KARTPARAM_ARCHIVES.items():
                path = game / archive
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(fake_szs(inner))
            creation = Creation("Standard Kart M", {"speed": 90}, slot=1)
            with patch.object(export, "patch_archive", wraps=export.patch_archive) as patch_archive:
                export.build_mod(game, "RMCE01", [creation], root / "out")
                self.assertEqual(patch_archive.call_count, 8)
                export.build_mod(game, "RMCE01", [creation], root / "out")
                self.assertEqual(patch_archive.call_count, 8)
                creation.stats["speed"] = 91
                export.build_mod(game, "RMCE01", [creation], root / "out")
                self.assertEqual(patch_archive.call_count, 16)
                path = game / "Race" / "Common.szs"
                path.write_bytes(yaz0.compress(build_u8({".": {"kartParam.bin": stock_kartparam(), "new": b"data"}})))
                export.build_mod(game, "RMCE01", [creation], root / "out")
                self.assertEqual(patch_archive.call_count, 17)
                patched = yaz0.decompress((root / "out" / export.MOD_FOLDER / "Race" / "Common.szs").read_bytes())
                self.assertEqual(u8.read_file(patched, "new"), b"data")

    def test_install_rolls_back_if_a_later_target_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            targets = [root / "one", root / "two"]
            for target in targets:
                old = target / export.MOD_FOLDER / "old.txt"
                old.parent.mkdir(parents=True)
                old.write_text("old mod")
                xml = target / "riivolution" / "CustomVehicleGarage.xml"
                xml.parent.mkdir()
                xml.write_text("old xml")
            real_rename = Path.rename
            def failing_rename(path, destination):
                if path.parent.name.startswith(".cvg-") and path.name == export.MOD_FOLDER and destination == targets[1] / export.MOD_FOLDER:
                    raise OSError("simulated failure")
                return real_rename(path, destination)
            with patch.object(Path, "rename", failing_rename):
                with self.assertRaisesRegex(OSError, "simulated failure"):
                    export.install_mod(root / "game", "RMCE01", [], targets)
            for target in targets:
                self.assertEqual((target / export.MOD_FOLDER / "old.txt").read_text(), "old mod")
                self.assertEqual((target / "riivolution" / "CustomVehicleGarage.xml").read_text(), "old xml")

    def test_build_mod_rejects_slot_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                export.build_mod(Path(tmp), "RMCE01", [Creation("A", slot=1), Creation("B", slot=1)], Path(tmp) / "out")


if __name__ == "__main__":
    unittest.main()
