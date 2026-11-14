import pathlib
import unittest

from vehiclegarage.kartparam import KartParam, SECTION_SIZE, Vehicle

SAMPLE = pathlib.Path(__file__).resolve().parents[1] / "ExampleMods" / "FunnyViihicles" / "kartParam.bin"


def make_bytes(count: int) -> bytes:
    body = b"".join(bytes([i % 256]) * SECTION_SIZE for i in range(count))
    return count.to_bytes(4, "big") + body


class KartParamTests(unittest.TestCase):
    def test_round_trip_preserves_bytes(self):
        data = make_bytes(3)
        self.assertEqual(KartParam.from_bytes(data).to_bytes(), data)

    def test_set_and_get_float_and_int_fields(self):
        vehicle = Vehicle(bytes(SECTION_SIZE))
        vehicle.set("speed", 12.5)
        vehicle.set("weight_class", 2)
        self.assertAlmostEqual(vehicle.get("speed"), 12.5)
        self.assertEqual(vehicle.get("weight_class"), 2)

    def test_set_only_changes_that_field_bytes(self):
        raw = bytes(i % 256 for i in range(SECTION_SIZE))
        vehicle = Vehicle(raw)
        vehicle.set("speed", 1.0)  # word index 6 -> bytes 24..27
        changed = {i for i in range(SECTION_SIZE) if vehicle.raw[i] != raw[i]}
        self.assertTrue(changed <= set(range(24, 28)))

    def test_rejects_wrong_length(self):
        with self.assertRaises(ValueError):
            KartParam.from_bytes(make_bytes(2)[:-1])

    def test_real_kart_param_file_has_36_vehicles(self):
        if not SAMPLE.exists():
            self.skipTest("sample kartParam.bin not available")
        data = SAMPLE.read_bytes()
        param = KartParam.from_bytes(data)
        self.assertEqual(len(param.vehicles), 36)
        self.assertEqual(param.to_bytes(), data)


if __name__ == "__main__":
    unittest.main()
