import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tests.test_archives import build_u8
from tests.test_export import fake_szs
from vehiclegarage import export, preview, textures, yaz0
from vehiclegarage.creations import Creation, Library


def vehicle_archive() -> bytes:
    return yaz0.compress(build_u8({".": {"vehicle.brres": b"bres synthetic model"}}))


class TextureTests(unittest.TestCase):
    def test_import_filters_vehicle_and_character_files_and_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "pack.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("race/mdf_kart-mr.szs", vehicle_archive())
                archive.writestr("race/mdf_kart-mr_4.szs", vehicle_archive())
                archive.writestr("race/la_bike-fk.szs", vehicle_archive())
                archive.writestr("race/mdf_kart-bmr.szs", vehicle_archive())
            pack = textures.import_pack(source, 1, root / "textures", "My pack", "https://example.com")
            self.assertEqual(set(pack.files), {"mdf_kart-mr.szs", "mdf_kart-mr_4.szs"})
            library = Library(root / "creations")
            library.save(Creation("Standard Kart M", slot=1, texture=pack))
            self.assertEqual(library.all()[0].texture, pack)
            self.assertEqual(
                [path for path, _ in textures.texture_outputs(pack, 1, root / "textures")],
                ["Race/Kart/mdf_kart-mr.szs", "Race/Kart/mdf_kart-mr_4.szs"],
            )

    def test_import_rejects_wrong_slot_invalid_archive_and_unsafe_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wrong = root / "la_bike-fk.szs"
            wrong.write_bytes(vehicle_archive())
            with self.assertRaisesRegex(ValueError, "No matching"):
                textures.import_pack(wrong, 22, root / "textures")
            invalid = root / "ma_bike-mr.szs"
            invalid.write_bytes(b"not an archive")
            with self.assertRaisesRegex(ValueError, "valid Yaz0"):
                textures.import_pack(invalid, 22, root / "textures")
            bad_zip = root / "bad.zip"
            with zipfile.ZipFile(bad_zip, "w") as archive:
                archive.writestr("../ma_bike-mr.szs", vehicle_archive())
            with self.assertRaisesRegex(ValueError, "unsafe path"):
                textures.import_pack(bad_zip, 22, root / "textures")
            self.assertFalse((root / "textures").exists())

    def test_import_rejects_duplicate_and_unreasonably_large_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "pack.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("a/ma_bike-mr.szs", vehicle_archive())
                archive.writestr("b/ma_bike-mr.szs", vehicle_archive())
            with self.assertRaisesRegex(ValueError, "more than one"):
                textures.import_pack(source, 22, root / "textures")
            source = root / "ma_bike-mr.szs"
            source.write_bytes(b"Yaz0" + (textures.MAX_UNPACKED + 1).to_bytes(4, "big") + bytes(8))
            with self.assertRaisesRegex(ValueError, "too large"):
                textures.import_pack(source, 22, root / "textures")

    def test_build_writes_texture_and_xml_and_refuses_corrupt_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "mdf_kart-mr.szs"
            source.write_bytes(vehicle_archive())
            storage = root / "textures"
            pack = textures.import_pack(source, 1, storage)
            creation = Creation("Standard Kart M", slot=1, texture=pack)
            game = root / "game"
            common = game / "Race" / "Common.szs"
            common.parent.mkdir(parents=True)
            common.write_bytes(fake_szs("kartParam.bin"))
            out = root / "out"
            export.build_mod(game, "RMCE01", [creation], out, texture_dir=storage)
            target = out / export.MOD_FOLDER / "Race" / "Kart" / source.name
            self.assertEqual(target.read_bytes(), source.read_bytes())
            xml = (out / "riivolution" / "CustomVehicleGarage.xml").read_text()
            self.assertIn('disc="/Race/Kart/mdf_kart-mr.szs"', xml)
            (storage / (next(iter(pack.files.values())) + ".szs")).write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "checksum"):
                export.build_mod(game, "RMCE01", [creation], out, texture_dir=storage)
            self.assertEqual(target.read_bytes(), source.read_bytes())

    def test_disabled_texture_is_not_built_and_legacy_creation_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = Creation.from_json({"name": "Standard Kart M", "slot": 1})
            self.assertIsNone(legacy.texture)
            source = root / "mdf_kart-mr.szs"
            source.write_bytes(vehicle_archive())
            pack = textures.import_pack(source, 1, root / "textures")
            disabled = Creation("Standard Kart M", slot=1, enabled=False, texture=pack)
            game = root / "game"
            (game / "Race").mkdir(parents=True)
            (game / "Race" / "Common.szs").write_bytes(fake_szs("kartParam.bin"))
            export.build_mod(game, "RMCE01", [disabled], root / "out")
            xml = (root / "out" / "riivolution" / "CustomVehicleGarage.xml").read_text()
            self.assertNotIn("mdf_kart-mr.szs", xml)

    def test_wiki_pagination_cache_and_page_details(self):
        pages = [
            {"query": {"categorymembers": [{"title": "First"}]}, "continue": {"cmcontinue": "next", "continue": "-||"}},
            {"query": {"categorymembers": [{"title": "Second"}]}},
        ]
        html = (
            '<table><tr><th>Author:</th><td>A Creator</td></tr>'
            '<tr><th>Download:</th><td><a href="https://example.com/file.zip">Download</a></td></tr></table>'
            '<figure><img src="/w/images/preview.jpg"></figure>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            with patch.object(textures, "_api", side_effect=pages) as api:
                self.assertEqual(textures.catalogue(cache), ["First", "Second"])
                self.assertEqual(api.call_count, 2)
            with patch.object(textures, "_api", side_effect=AssertionError("network used")):
                self.assertEqual(textures.catalogue(cache), ["First", "Second"])
            with patch.object(textures, "_api", return_value={"parse": {"text": {"*": html}}}):
                details = textures.page_details("First", cache)
            self.assertEqual(details["author"], "A Creator")
            self.assertEqual(details["preview"], "https://mkwiiki.org/w/images/preview.jpg")
            self.assertEqual(details["downloads"], ["https://example.com/file.zip"])
            self.assertEqual(json.loads((cache / "catalogue.json").read_text()), ["First", "Second"])

    def test_texture_descriptors_reject_wrong_slot_or_filename(self):
        digest = "a" * 64
        with self.assertRaisesRegex(ValueError, "invalid texture filename"):
            textures.TexturePack.from_json({"name": "x", "slot": 1, "files": {"../mdf_kart-mr.szs": digest}})
        pack = textures.TexturePack.from_json({"name": "x", "slot": 1, "files": {"mdf_kart-mr.szs": digest}})
        with self.assertRaisesRegex(ValueError, "different vehicle slot"):
            textures.texture_outputs(pack, 0, Path("unused"))
        with self.assertRaisesRegex(ValueError, "does not match"):
            Creation("x", slot=0, texture=pack)

    def test_untrusted_or_non_direct_download_is_not_fetched(self):
        with patch.object(textures, "_get", side_effect=AssertionError("network used")):
            for url in ("http://mkwiiki.org/file.zip", "https://example.com/file.zip",
                        "https://mkwiiki.org/wiki/Page"):
                with self.assertRaisesRegex(ValueError, "supported direct"):
                    textures.direct_download(url)

    @unittest.skipUnless(__import__("os").name == "nt", "Windows GDI+ preview")
    def test_windows_preview_decoder_handles_images_and_bad_data(self):
        image = Path(__file__).resolve().parent.parent / "vehiclegarage" / "assets" / "garage.png"
        ppm = preview.decode(image.read_bytes())
        self.assertTrue(ppm.startswith(b"P6\n256 256\n255\n"))
        with self.assertRaisesRegex(ValueError, "format"):
            preview.decode(b"not an image")


if __name__ == "__main__":
    unittest.main()
