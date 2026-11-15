import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from vehiclegarage.app import GarageApp
from vehiclegarage.creations import Creation


class EditorNameTests(unittest.TestCase):
    def test_save_button_enabled_with_slot_even_when_name_empty(self):
        app = SimpleNamespace(
            name_var=Mock(get=Mock(return_value="")),
            name_counter=Mock(),
            save_vehicle_button=Mock(),
            selected_slot=0,
        )
        GarageApp._update_name_counter(app)
        app.save_vehicle_button.state.assert_called_once_with(["!disabled"])
        app.selected_slot = None
        GarageApp._update_name_counter(app)
        app.save_vehicle_button.state.assert_called_with(["disabled"])

    def test_saving_blank_name_explains_requirement_and_focuses_entry(self):
        app = SimpleNamespace(
            _current_slot=lambda: 0,
            name_var=Mock(get=Mock(return_value="   ")),
            name_entry=Mock(),
            library=Mock(),
        )
        with patch("vehiclegarage.app.messagebox.showwarning") as warning:
            GarageApp._save_creation(app)
        warning.assert_called_once_with("Name it", "Give your creation a name.")
        app.name_entry.focus_set.assert_called_once()
        app.library.save.assert_not_called()

    def test_saving_a_long_name_keeps_it_for_build_validation(self):
        app = SimpleNamespace(
            _current_slot=lambda: 0, name_var=Mock(get=Mock(return_value="Longer than ten")),
            _collect_stats=lambda _slot: {}, editing=None, edit_texture=None,
            _preset_edit_slot=None,
            library=Mock(all=Mock(return_value=[])), _refresh_garage=Mock(), show_page=Mock(),
        )
        GarageApp._save_creation(app)
        self.assertEqual(app.library.save.call_args.args[0].name, "Longer than ten")


class VehicleSelectionLayoutTests(unittest.TestCase):
    def test_saved_and_empty_cards_fill_and_align_within_a_row(self):
        try:
            probe = tk.Tk()
        except tk.TclError as err:
            self.skipTest(f"Tk display unavailable: {err}")
        probe.destroy()
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(GarageApp, "_autodetect_tool"), \
                patch.object(GarageApp, "_check_update"):
            app = GarageApp(Path(tmp))
            try:
                app.library.save(Creation("Saved vehicle", slot=0))
                app.show_page("vehicles")
                app._fill_vehicles()
                app.update()
                saved, empty = (app.vehicle_buttons[slot] for slot in (0, 1))
                self.assertIn("SAVED: Saved vehicle (in mod)", saved.cget("text"))
                self.assertEqual(saved.winfo_y(), empty.winfo_y())
                self.assertEqual(saved.winfo_height(), empty.winfo_height())
                self.assertEqual(saved.cget("anchor"), "nw")
                self.assertEqual(empty.cget("anchor"), "nw")
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
