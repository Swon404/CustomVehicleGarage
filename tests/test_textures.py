import json
import os
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

    def test_vehicle_search_uses_generic_standard_name_and_page_content(self):
        response = {"query": {"search": [{"title": "Space Kart (Standard Kart Texture)"},
                                         {"title": "Another page"}]}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(textures, "_api", return_value=response) as api:
            result = textures.vehicle_search("Standard Kart S", Path(tmp))
            self.assertIn("Space Kart (Standard Kart Texture)", result)
            self.assertEqual(api.call_args.args[0]["srsearch"], '"Standard Kart"')
            self.assertEqual(textures.vehicle_search("Standard Kart M", Path(tmp)), result)
            self.assertEqual(api.call_count, 1)

    def test_vehicle_index_handles_multiple_vehicles_rowspans_and_canonical_titles(self):
        html = """
        <table><tr><th>Title</th><th>Character</th><th>Vehicle</th><th>Type</th></tr>
        <tr><td rowspan="2"><a href="/wiki/Tails_Doll_%28Baby_Mario_Edit%29">Tails Doll</a></td>
        <td rowspan="2">Baby Mario</td>
        <td>Standard Kart S, Booster Seat, Mini Beast, Cheep Charger, Tiny Titan, Blue Falcon</td><td>Texture</td></tr>
        <tr><td><a href="/wiki/Mach_Bike">Mach Bike</a></td><td>Texture</td></tr>
        <tr><td><a href="/wiki/Other_%26_Kart">Other &amp; Kart</a></td><td>Mario</td>
        <td>Standard Kart M</td><td>Texture</td></tr></table>
        <table><tr><th>Title</th><th>Character</th></tr>
        <tr><td><a href="/wiki/Ignored">Ignored</a></td><td>Blue Falcon</td></tr></table>
        """
        response = {"parse": {"text": {"*": html}}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(textures, "_api", return_value=response):
            index = textures.vehicle_index(Path(tmp))
        title = "Tails Doll (Baby Mario Edit)"
        for vehicle in ("Standard Kart S", "Booster Seat", "Mini Beast", "Cheep Charger",
                        "Tiny Titan", "Blue Falcon", "Mach Bike"):
            self.assertIn(title, index[vehicle])
        self.assertNotIn(title, index["Standard Kart M"])
        self.assertEqual(index["Standard Kart M"], ["Other & Kart"])
        self.assertNotIn("Ignored", index["Blue Falcon"])

    def test_vehicle_index_cache_refresh_and_invalid_data(self):
        html = ('<table><tr><th>Title</th><th>Vehicle</th></tr>'
                '<tr><td><a href="/wiki/Test">Test</a></td><td>Blue Falcon</td></tr></table>')
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            with patch.object(textures, "_api", return_value={"parse": {"text": {"*": html}}}) as api:
                self.assertEqual(textures.vehicle_index(cache), {"Blue Falcon": ["Test"]})
                self.assertEqual(textures.vehicle_index(cache), {"Blue Falcon": ["Test"]})
                self.assertEqual(api.call_count, 1)
                textures.vehicle_index(cache, refresh=True)
                self.assertEqual(api.call_count, 2)
                path = cache / "vehicle-index.json"
                os.utime(path, (0, 0))
                textures.vehicle_index(cache)
                self.assertEqual(api.call_count, 3)
            path.write_text('{"Blue Falcon": [1]}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid"):
                textures.vehicle_index(cache)
            with patch.object(textures, "_api", return_value={"parse": {"text": {"*": "<table></table>"}}}):
                with self.assertRaisesRegex(ValueError, "no recognised"):
                    textures.vehicle_index(cache, refresh=True)

    def test_gallery_image_is_used_as_preview(self):
        parser = textures._PageParser()
        parser.feed('<ul class="gallery mw-gallery-traditional"><li><img src="/w/images/vehicle.png"></li></ul>')
        self.assertEqual(parser.preview, "https://mkwiiki.org/w/images/vehicle.png")

    def test_creator_credit_survives_pack_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "mdf_kart-mr.szs"
            source.write_bytes(vehicle_archive())
            pack = textures.import_pack(source, 1, root / "textures", "My pack", "https://mkwiiki.org/wiki/Test", "Creator")
            library = Library(root / "creations")
            library.save(Creation("Standard Kart M", slot=1, texture=pack))
            saved = library.all()[0].texture
            self.assertEqual(saved.author, "Creator")
            self.assertEqual(saved.source, "https://mkwiiki.org/wiki/Test")
            legacy = pack.to_json()
            del legacy["author"]
            self.assertEqual(textures.TexturePack.from_json(legacy).author, "")

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
