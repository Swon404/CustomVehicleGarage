import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests import destroy_tk_app
from vehiclegarage.app import GarageApp, ToolTip
from vehiclegarage.creations import Creation
from vehiclegarage.kartparam import KartParam, SECTION_SIZE
from vehiclegarage.stats import ADVANCED_FIELDS, advanced_slider_range, format_value


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
                self.assertIs(app.app_icon.tk, app.tk)
                self.assertIs(app.header_icon.tk, app.tk)
                self.assertIs(app.header_art.tk, app.tk)
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
                destroy_tk_app(app)


class GarageColumnLayoutTests(unittest.TestCase):
    def test_headings_align_and_vehicle_columns_take_extra_space(self):
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
                app.show_page("garage")
                app.geometry("900x640")
                app.update()
                columns = ("number", "name", "vehicle", "class", "on")
                for column in columns:
                    self.assertEqual(app.tree.heading(column, "anchor"), app.tree.column(column, "anchor"))
                small = {column: app.tree.column(column, "width") for column in columns}
                app.geometry("1400x900")
                app.update()
                large = {column: app.tree.column(column, "width") for column in columns}
                for column in ("number", "class", "on"):
                    self.assertEqual(small[column], large[column])
                for column in ("name", "vehicle"):
                    self.assertGreater(large[column], small[column])
                for number in range(36):
                    app.tree.insert("", "end", values=(f"#{number + 1}", "Vehicle", "Stock", "Light", "Yes"))
                app.update()
                scrollbar = next(child for child in app.tree.master.winfo_children() if isinstance(child, ttk.Scrollbar))
                self.assertLess(scrollbar.get()[1], 1)
                app.tk.call(scrollbar.cget("command"), "moveto", 1.0)
                app.update()
                self.assertEqual(scrollbar.get()[1], 1)
            finally:
                destroy_tk_app(app)


class EditorAdvancedLayoutTests(unittest.TestCase):
    def test_cleanup_keeps_widget_timer_ownership(self):
        try:
            root = tk.Tk()
        except tk.TclError as err:
            self.skipTest(f"Tk display unavailable: {err}")
        label = ttk.Label(root)
        tooltip = ToolTip(label, lambda: "Tip")
        tooltip._schedule(None)
        root.after(60000, lambda: None)
        destroy_tk_app(root)

    def test_advanced_toggle_visible_and_fields_scroll_into_view(self):
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
                app.show_page("editor")
                def descendants(widget):
                    for child in widget.winfo_children():
                        yield child
                        yield from descendants(child)
                toggle = next(w for w in descendants(app.pages["editor"])
                              if w.winfo_class() == "TCheckbutton"
                              and w.cget("text") == "SHOW ADVANCED GAME VALUES")
                for size in ("1100x760", "900x640"):
                    app.geometry(size)
                    app.editor_canvas.yview_moveto(0)
                    app.update()
                    self.assertTrue(toggle.winfo_ismapped())
                    bottom = toggle.winfo_rooty() + toggle.winfo_height()
                    viewport_bottom = app.editor_canvas.winfo_rooty() + app.editor_canvas.winfo_height()
                    if toggle.master == app.editor_canvas or str(toggle).startswith(str(app.editor_canvas) + "."):
                        self.assertLessEqual(bottom, viewport_bottom)
                    else:
                        self.assertLessEqual(bottom, app.pages["editor"].winfo_rooty() + app.pages["editor"].winfo_height())
                    toggle.invoke()
                    app.update()
                    self.assertTrue(app.advanced_frame.winfo_ismapped())
                    self.assertEqual(set(app.advanced_sliders), {field for field, _, _ in ADVANCED_FIELDS})
                    self.assertGreaterEqual(app.advanced_frame.winfo_rooty(), app.editor_canvas.winfo_rooty())
                    self.assertLess(app.advanced_frame.winfo_rooty(),
                                    app.editor_canvas.winfo_rooty() + app.editor_canvas.winfo_height())
                    frame_right = app.advanced_frame.winfo_rootx() + app.advanced_frame.winfo_width()
                    for child in app.advanced_frame.winfo_children():
                        self.assertLessEqual(child.winfo_rootx() + child.winfo_width(), frame_right)
                        if isinstance(child, ttk.Scale):
                            self.assertGreaterEqual(child.winfo_width(), 80)
                    toggle.invoke()
                    app.update()
                    self.assertFalse(app.advanced_frame.winfo_ismapped())
            finally:
                destroy_tk_app(app)

    def test_sliders_preserve_exact_values_and_sync_entries(self):
        try:
            probe = tk.Tk()
        except tk.TclError as err:
            self.skipTest(f"Tk display unavailable: {err}")
        probe.destroy()
        stock = KartParam.from_bytes((36).to_bytes(4, "big") + bytes(36 * SECTION_SIZE))
        for index, vehicle in enumerate(stock.vehicles):
            for field, _, _ in ADVANCED_FIELDS:
                vehicle.set(field, 0.123456789 + index / 100)
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(GarageApp, "_autodetect_tool"), \
                patch.object(GarageApp, "_check_update"):
            app = GarageApp(Path(tmp))
            try:
                app.stock = stock
                app.selected_slot = 0
                precise = 0.234567891234
                app._load_values(0, {"tilt": precise})
                app.show_page("editor")
                app.update()
                slider = app.advanced_sliders["max_normal_acceleration"]
                self.assertEqual((float(slider.cget("from")), float(slider.cget("to"))), (1.0, 12.0))
                self.assertEqual(app._collect_stats(0), {"tilt": precise})
                tooltip = app._advanced_tooltip("max_normal_acceleration", "Cap on acceleration")
                self.assertIn("Slider range: 1 to 12", tooltip)
                self.assertIn("Stock vehicles:", tooltip)
                app.advanced_open.set(True)
                app._toggle_advanced()
                app.update()
                for field, _, _ in ADVANCED_FIELDS:
                    high = app._advanced_ranges[field][1]
                    app.advanced_sliders[field].set(high)
                    app.update()
                    self.assertAlmostEqual(app._collect_stats(0)[field], high)
                app._load_values(0, {"tilt": precise})
                app.advanced_vars["tilt"].set("0.3")
                app._numeric_advanced_edited("tilt", "Lean")
                self.assertAlmostEqual(app.advanced_slider_vars["tilt"].get(), 0.3)
                self.assertEqual(app._collect_stats(0)["tilt"], 0.3)
                slider.set(1)
                app.update()
                self.assertEqual(float(app.advanced_vars["max_normal_acceleration"].get()), 1)
                self.assertEqual(app._collect_stats(0)["max_normal_acceleration"], 1)
                slider.set(12)
                app.update()
                self.assertEqual(float(app.advanced_vars["max_normal_acceleration"].get()), 12)
                self.assertEqual(app._collect_stats(0)["max_normal_acceleration"], 12)
                app.advanced_vars["max_normal_acceleration"].set("42.123456789")
                app._numeric_advanced_edited("max_normal_acceleration", "Max normal acceleration")
                app.update()
                self.assertEqual(app.advanced_slider_vars["max_normal_acceleration"].get(), 12)
                self.assertEqual(app._collect_stats(0)["max_normal_acceleration"], 42.123456789)
                with patch("vehiclegarage.app.messagebox.showwarning") as warning:
                    app.advanced_vars["tilt"].set("nan")
                    app._numeric_advanced_edited("tilt", "Lean")
                    warning.assert_called_once()
                    with self.assertRaisesRegex(ValueError, "finite"):
                        app._collect_stats(0)
                app._reset_to_stock()
                app.update()
                self.assertEqual(app._collect_stats(0), {})
                self.assertEqual(app.advanced_vars["tilt"].get(), format_value(stock.vehicles[0].get("tilt")))
            finally:
                destroy_tk_app(app)

    def test_stock_ranges_and_identical_values(self):
        self.assertEqual(advanced_slider_range("tilt", [-2.0, 3.0]), (-2.0, 3.0))
        self.assertEqual(advanced_slider_range("tilt", [2.0, 2.0]), (0.0, 4.0))
        self.assertEqual(advanced_slider_range("tilt", [-2.0, -2.0]), (-4.0, 0.0))
        self.assertEqual(advanced_slider_range("tilt", [0.0, 0.0]), (-1.0, 1.0))
        with self.assertRaisesRegex(ValueError, "finite"):
            advanced_slider_range("tilt", [float("nan")])


if __name__ == "__main__":
    unittest.main()
