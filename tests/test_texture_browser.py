import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from vehiclegarage.texture_browser import TextureBrowser


class Listbox:
    def __init__(self, selection=()):
        self.selection = selection
        self.items = []

    def curselection(self):
        return self.selection

    def delete(self, *_args):
        self.items.clear()
        self.selection = ()

    def insert(self, _where, item):
        self.items.append(item)

    def selection_set(self, index):
        self.selection = (index,)


class TextureBrowserTests(unittest.TestCase):
    def test_index_matches_are_combined_and_selection_is_preserved(self):
        title = "Tails Doll (Baby Mario Edit)"
        browser = SimpleNamespace(
            slot=0, search=SimpleNamespace(get=lambda: ""), only_vehicle=SimpleNamespace(get=lambda: True),
            titles=[title, "Standard Kart S texture", "Unrelated"], visible=["Standard Kart S texture"],
            index_matches={title}, content_matches=set(), listbox=Listbox((0,)),
            details={"title": "Standard Kart S texture"}, status=Mock(), search_errors={},
            _set_detail_buttons=Mock(),
        )
        browser._show_search_status = lambda: TextureBrowser._show_search_status(browser)
        TextureBrowser._filter(browser)
        self.assertEqual(browser.visible, [title, "Standard Kart S texture"])
        self.assertEqual(browser.listbox.curselection(), (1,))
        self.assertEqual(browser.details["title"], "Standard Kart S texture")
        browser._set_detail_buttons.assert_not_called()

    def test_index_error_remains_visible_after_content_search_finishes(self):
        jobs = []
        browser = SimpleNamespace(
            load_generation=0, content_matches=set(), index_matches=set(), search_errors={}, visible=[],
            refresh_button=Mock(), status=Mock(), slot=0, cache=Path("unused"),
            app=SimpleNamespace(_run_in_background=lambda work, done: jobs.append((work, done))),
            _alive=lambda: True, _filter=Mock(),
        )
        TextureBrowser._load(browser, False)
        jobs[0][1](["Result"], None)
        with patch("vehiclegarage.texture_browser.messagebox.showwarning") as warning:
            jobs[2][1](None, ValueError("unavailable"))
            warning.assert_called_once()
        jobs[1][1](["Result"], None)
        self.assertEqual(browser.content_matches, {"Result"})
        self.assertIn("Wiki vehicle list", browser.search_errors)
        TextureBrowser._show_search_status(SimpleNamespace(
            search_errors=browser.search_errors, visible=["Result"], status=browser.status,
        ))
        self.assertIn("Wiki vehicle list unavailable", browser.status.config.call_args.kwargs["text"])

    def test_older_refresh_results_do_not_overwrite_newer_search(self):
        jobs = []
        browser = SimpleNamespace(
            load_generation=0, content_matches=set(), index_matches=set(), search_errors={}, visible=[],
            refresh_button=Mock(), status=Mock(), slot=0, cache=Path("unused"),
            app=SimpleNamespace(_run_in_background=lambda work, done: jobs.append((work, done))),
            _alive=lambda: True, _filter=Mock(),
        )
        TextureBrowser._load(browser, False)
        jobs[0][1](["Old"], None)
        TextureBrowser._load(browser, True)
        jobs[3][1](["New"], None)
        jobs[2][1]({"Standard Kart S": ["Old"]}, None)
        jobs[5][1]({"Standard Kart S": ["New"]}, None)
        self.assertEqual(browser.titles, ["New"])
        self.assertEqual(browser.index_matches, {"New"})


if __name__ == "__main__":
    unittest.main()
