import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from vehiclegarage.app import GarageApp


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


if __name__ == "__main__":
    unittest.main()
