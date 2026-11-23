"""The Custom Vehicle Garage desktop app."""

import ctypes
import os
import queue
import threading
import time
import tkinter as tk
import urllib.parse
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from vehiclegarage import bmg, disc, dolphin, export, garages, presets, updater
from vehiclegarage.creations import Creation, slot_conflicts
from vehiclegarage.kartparam import KartParam
from vehiclegarage.settings import Settings, cache_dir, data_dir, texture_dir
from vehiclegarage.stats import (
    ADVANCED_FIELDS, BARS, advanced_slider_range, format_value, parse_advanced_value, same_game_value,
)
from vehiclegarage.texture_browser import TextureBrowser
from vehiclegarage.textures import TexturePack
from vehiclegarage.vehicles import VEHICLES, WEIGHT_CLASSES
from vehiclegarage.version import OFFICIAL_RELEASE, VERSION

COLORS = {
    "background": "#07152d",
    "panel": "#102444",
    "panel_alt": "#1a355a",
    "header": "#124a84",
    "footer": "#f0eff5",
    "text": "#f7f6f8",
    "muted": "#c2d6ee",
    "gold": "#ffda45",
    "purple": "#53a9ff",
    "danger": "#ff7777",
    "selected": "#755700",
}


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.timer = None
        self.window = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def _schedule(self, _event):
        self.timer = self.widget.after(500, self._show)

    def _show(self):
        self.timer = None
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{self.widget.winfo_rootx() + 16}+{self.widget.winfo_rooty() + self.widget.winfo_height()}")
        tk.Label(self.window, text=self.text(), background="#fff4c2", foreground="#17263a",
                 relief="solid", borderwidth=1, padx=8, pady=5, justify="left", wraplength=400).pack()

    def _hide(self, _event=None):
        if self.timer is not None:
            self.widget.after_cancel(self.timer)
            self.timer = None
        if self.window is not None:
            if self.window.winfo_exists():
                self.window.destroy()
            self.window = None


class GarageApp(tk.Tk):
    def __init__(self, root_dir: Path | None = None):
        super().__init__()
        self.title("Custom Vehicle Garage - Mario Kart Wii")
        self.geometry("1100x760")
        self.minsize(900, 640)
        self.configure(background=COLORS["background"])
        self._configure_styles()
        assets = Path(__file__).resolve().parent / "assets"
        self.app_icon = tk.PhotoImage(master=self, file=str(assets / "garage.png"))
        if os.name == "nt":
            self.iconbitmap(default=str(assets / "garage.ico"))
        else:
            self.iconphoto(True, self.app_icon)
        self.header_icon = self.app_icon.subsample(5, 5)
        self.header_art = tk.PhotoImage(master=self, file=str(assets / "racing-banner.png"))
        self.root_dir = root_dir or data_dir()
        self.settings = Settings.load(self.root_dir)
        self.garages = garages.Garages(self.root_dir)
        self.library = self.garages.library()
        self.cache = cache_dir(self.root_dir)
        self.stock: KartParam | None = None
        self.editing: Creation | None = None
        self.selected_slot: int | None = None
        self.edit_texture: TexturePack | None = None
        self._changing_stock_vehicle = False
        self._build_cancel: export.BuildCancellation | None = None
        self.events: queue.Queue = queue.Queue()

        self._build_shell()
        self._build_garage_page()
        self._build_vehicle_page()
        self._build_editor_page()
        self._build_install_page()
        self._build_setup_page()

        self._load_stock()
        self._refresh_garage()
        self._refresh_setup()
        if self.stock is None:
            self.show_page("setup")
        else:
            self.show_page("garage")
        self.after(100, self._poll_events)
        self.after(250, self._check_update)

    # ---------- shared ----------

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background=COLORS["background"])
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("App.TLabel", background=COLORS["background"], foreground=COLORS["text"])
        style.configure("Panel.TLabel", background=COLORS["panel"], foreground=COLORS["text"])
        style.configure("Muted.TLabel", background=COLORS["background"], foreground=COLORS["muted"])
        style.configure(
            "PageTitle.TLabel",
            background=COLORS["background"],
            foreground=COLORS["text"],
            font=("Segoe UI", 18, "bold"),
        )
        style.configure(
            "Section.TLabel",
            background=COLORS["panel"],
            foreground=COLORS["gold"],
            font=("Segoe UI", 11, "bold"),
        )
        style.configure(
            "Nav.TButton",
            background=COLORS["panel_alt"],
            foreground=COLORS["text"],
            bordercolor="#4c79aa",
            lightcolor=COLORS["panel_alt"],
            darkcolor=COLORS["panel_alt"],
            padding=(16, 10),
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Nav.TButton",
            background=[("active", "#285b91"), ("disabled", COLORS["panel"])],
            foreground=[("disabled", COLORS["muted"])],
        )
        style.configure(
            "NavSelected.TButton",
            background=COLORS["gold"],
            foreground="#151515",
            bordercolor="#ffe998",
            lightcolor=COLORS["gold"],
            darkcolor=COLORS["gold"],
            padding=(16, 10),
            font=("Segoe UI", 10, "bold"),
        )
        style.map("NavSelected.TButton", background=[("active", "#ffe36a")])
        style.configure(
            "Primary.TButton",
            background=COLORS["gold"],
            foreground="#171717",
            bordercolor="#ffe998",
            lightcolor=COLORS["gold"],
            darkcolor=COLORS["gold"],
            padding=(16, 10),
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Primary.TButton", background=[("active", "#ffe36a")])
        style.configure(
            "Secondary.TButton",
            background=COLORS["panel_alt"],
            foreground=COLORS["text"],
            bordercolor="#4c79aa",
            lightcolor=COLORS["panel_alt"],
            darkcolor=COLORS["panel_alt"],
            padding=(12, 8),
        )
        style.map("Secondary.TButton", background=[("active", "#285b91")])
        style.configure(
            "Treeview",
            background=COLORS["panel"],
            fieldbackground=COLORS["panel"],
            foreground=COLORS["text"],
            rowheight=34,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.map(
            "Treeview",
            background=[("selected", COLORS["selected"])],
            foreground=[("selected", COLORS["text"])],
        )
        style.configure(
            "Treeview.Heading",
            background=COLORS["panel_alt"],
            foreground=COLORS["gold"],
            relief="flat",
            font=("Segoe UI", 9, "bold"),
        )
        style.map("Treeview.Heading", background=[("active", "#353740")])
        style.configure(
            "Panel.TLabelframe",
            background=COLORS["panel"],
            bordercolor=COLORS["gold"],
            relief="solid",
        )
        style.configure(
            "Panel.TLabelframe.Label",
            background=COLORS["background"],
            foreground=COLORS["gold"],
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "TEntry",
            fieldbackground=COLORS["panel_alt"],
            foreground=COLORS["text"],
            insertcolor=COLORS["text"],
            bordercolor="#4c79aa",
            lightcolor=COLORS["panel_alt"],
            darkcolor=COLORS["panel_alt"],
        )
        style.map(
            "TEntry",
            fieldbackground=[("disabled", COLORS["panel"]), ("readonly", COLORS["panel_alt"])],
        )
        style.configure(
            "TCombobox",
            fieldbackground=COLORS["panel_alt"],
            background=COLORS["panel_alt"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["gold"],
            bordercolor="#4c79aa",
            lightcolor=COLORS["panel_alt"],
            darkcolor=COLORS["panel_alt"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", COLORS["panel_alt"])],
            foreground=[("readonly", COLORS["text"])],
            selectbackground=[("readonly", COLORS["panel_alt"])],
            selectforeground=[("readonly", COLORS["text"])],
        )
        self.option_add("*TCombobox*Listbox.background", COLORS["panel_alt"])
        self.option_add("*TCombobox*Listbox.foreground", COLORS["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", COLORS["selected"])
        self.option_add("*TCombobox*Listbox.selectForeground", COLORS["text"])
        style.configure(
            "TCheckbutton",
            background=COLORS["panel"],
            foreground=COLORS["text"],
            indicatorcolor=COLORS["panel_alt"],
        )
        style.map(
            "TCheckbutton",
            background=[("active", COLORS["panel"])],
            indicatorcolor=[("selected", COLORS["gold"]), ("!selected", COLORS["panel_alt"])],
        )
        style.configure(
            "TRadiobutton",
            background=COLORS["panel"],
            foreground=COLORS["text"],
            indicatorcolor=COLORS["panel_alt"],
        )
        style.map(
            "TRadiobutton",
            background=[("active", COLORS["panel"])],
            indicatorcolor=[("selected", COLORS["gold"]), ("!selected", COLORS["panel_alt"])],
        )
        style.configure(
            "Horizontal.TScale",
            background=COLORS["gold"],
            troughcolor="#28466e",
            bordercolor="#28466e",
            lightcolor=COLORS["gold"],
            darkcolor=COLORS["gold"],
        )
        style.map("Horizontal.TScale", background=[("active", "#ffe989")])
        style.configure(
            "Horizontal.TProgressbar",
            background=COLORS["gold"],
            troughcolor="#28466e",
            bordercolor="#28466e",
            lightcolor=COLORS["gold"],
            darkcolor=COLORS["gold"],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=COLORS["panel_alt"],
            troughcolor=COLORS["background"],
            bordercolor="#4c79aa",
            arrowcolor=COLORS["gold"],
            lightcolor=COLORS["panel_alt"],
            darkcolor=COLORS["panel_alt"],
        )
        style.map("Vertical.TScrollbar", background=[("active", "#285b91")])

    def _build_shell(self) -> None:
        self.header = tk.Canvas(
            self, height=self.header_art.height(), background=COLORS["header"], highlightthickness=0
        )
        self.header.pack(fill="x")
        self.header.create_image(20, 45, image=self.header_icon, anchor="w")
        self.header.create_text(
            84, 31, text="CUSTOM VEHICLE GARAGE", anchor="w",
            fill=COLORS["text"], font=("Segoe UI", 17, "bold"),
        )
        self.header.create_text(
            84, 58, text="Mario Kart Wii | Build your ride and install it to Dolphin.",
            anchor="w", fill=COLORS["muted"], font=("Segoe UI", 9),
        )
        self.game_status = self.header.create_text(
            0, 45,
            text="GAME DATA NOT IMPORTED",
            anchor="e",
            fill=COLORS["muted"],
            font=("Segoe UI", 9, "bold"),
        )
        self.header.bind("<Configure>", self._resize_header)
        tk.Frame(self, height=3, background=COLORS["purple"]).pack(fill="x")

        nav = ttk.Frame(self, style="App.TFrame", padding=(14, 10, 14, 8))
        nav.pack(fill="x")
        self.nav_buttons: dict[str, ttk.Button] = {}
        for key, label in (
            ("garage", "MY GARAGE"),
            ("vehicles", "CHOOSE VEHICLE"),
            ("install", "BUILD & INSTALL"),
        ):
            button = ttk.Button(nav, text=label, style="Nav.TButton", command=lambda k=key: self._navigate(k))
            button.pack(side="left", padx=(0, 7))
            self.nav_buttons[key] = button
        self.nav_buttons["setup"] = ttk.Button(
            nav,
            text="SETUP",
            style="Nav.TButton",
            command=lambda: self._navigate("setup"),
        )
        self.nav_buttons["setup"].pack(side="right")
        self.update_button = ttk.Button(
            nav,
            text="UPDATE TO LATEST",
            style="Nav.TButton",
            command=self._install_update,
        )
        self.available_release: updater.Release | None = None

        self.page_host = ttk.Frame(self, style="App.TFrame", padding=(14, 4, 14, 14))
        self.page_host.pack(fill="both", expand=True)
        self.pages: dict[str, ttk.Frame] = {}

        footer = tk.Frame(self, height=24, background=COLORS["footer"])
        footer.pack(fill="x", side="bottom")
        tk.Frame(footer, height=3, background=COLORS["purple"]).pack(fill="x")
        self.update_status = tk.Label(
            footer, text=f"v{VERSION}" if OFFICIAL_RELEASE else "Development build", background=COLORS["footer"], foreground="#55545d",
            font=("Segoe UI", 8), anchor="w", padx=14,
        )
        self.update_status.pack(side="left")
        tk.Label(
            footer,
            text="Created by Swon404 and OnnY",
            background=COLORS["footer"],
            foreground="#55545d",
            font=("Segoe UI", 8, "bold"),
            anchor="e",
            padx=14,
            pady=2,
        ).pack(fill="x")

    def _resize_header(self, event: tk.Event) -> None:
        self.header.delete("background")
        for x in range(0, event.width, self.header_art.width()):
            self.header.create_image(x, 0, image=self.header_art, anchor="nw", tags="background")
        self.header.tag_lower("background")
        self.header.coords(self.game_status, event.width - 20, 45)

    def _new_page(self, key: str) -> ttk.Frame:
        page = ttk.Frame(self.page_host, style="App.TFrame", padding=8)
        page.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.pages[key] = page
        return page

    def show_page(self, key: str) -> None:
        self.pages[key].tkraise()
        active_key = "vehicles" if key == "editor" else key
        for nav_key, button in self.nav_buttons.items():
            button.configure(style="NavSelected.TButton" if nav_key == active_key else "Nav.TButton")

    def _navigate(self, key: str) -> None:
        if key in ("vehicles", "install") and not self._require_stock():
            return
        if key == "vehicles":
            self._new_creation()
            return
        if key == "install":
            self._refresh_install_summary()
        self.show_page(key)

    def _load_stock(self) -> None:
        self.stock = None
        game = self.settings.game_id
        if game and (self.cache / game / "Race" / "Common.szs").is_file():
            try:
                self.stock = export.read_stock_kartparam(self.cache / game)
            except (OSError, ValueError, KeyError) as err:
                messagebox.showerror("Game data", f"Could not read the imported game data: {err}")

    def _require_stock(self) -> bool:
        if self.stock is None:
            messagebox.showinfo("Set up first", "Import your Mario Kart Wii game data on the Setup page first.")
            self.show_page("setup")
            return False
        return True

    def _poll_events(self) -> None:
        try:
            while True:
                self.events.get_nowait()()
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _run_in_background(self, work, done) -> None:
        def runner():
            try:
                result = work()
                self.events.put(lambda: done(result, None))
            except Exception as err:  # surfaced to the user in the UI
                self.events.put(lambda err=err: done(None, err))

        threading.Thread(target=runner, daemon=True).start()

    def _check_update(self) -> None:
        if not OFFICIAL_RELEASE:
            self.update_status.config(text="Development build | Automatic updates unavailable")
            return

        def checked(release, error):
            if error:
                self.update_status.config(text=f"v{VERSION}  |  Update check failed: {error}")
            elif release is None:
                self.update_status.config(text=f"v{VERSION}  |  Up to date")
            else:
                self.available_release = release
                self.update_button.config(text="UPDATE TO LATEST")
                self.update_button.pack(side="right", padx=(0, 7), before=self.nav_buttons["setup"])
                self.update_status.config(text=f"v{VERSION}  |  Update available")

        self._run_in_background(updater.latest_release, checked)

    def _install_update(self) -> None:
        release = self.available_release
        if release is None or not messagebox.askyesno(
            "Update available",
            f"Version {release.version} is available (you have {VERSION}).\n\n"
            "Install it and restart now? Unsaved edits will be lost.",
        ):
            return
        self.update_button.state(["disabled"])

        def installed(_result, error):
            if error:
                self.update_button.state(["!disabled"])
                messagebox.showerror("Update failed", str(error))
            else:
                self.destroy()

        self._run_in_background(lambda: updater.install_release(release), installed)

    # ---------- garage page ----------

    def _build_garage_page(self) -> None:
        page = self._new_page("garage")
        hero = ttk.Frame(page, style="App.TFrame")
        hero.pack(fill="x", pady=(2, 12))
        titles = ttk.Frame(hero, style="App.TFrame")
        titles.pack(side="left", fill="x", expand=True)
        ttk.Label(titles, text="MY GARAGE", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(
            titles,
            text="Your saved rides and the stock vehicles they replace.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(3, 0))
        ttk.Button(
            hero,
            text="  +  CREATE VEHICLE  ",
            style="Primary.TButton",
            command=self._new_creation,
        ).pack(side="right", padx=(10, 0), pady=4)

        panel = ttk.Frame(page, style="Panel.TFrame", padding=12)
        panel.pack(fill="both", expand=True)
        garage_bar = ttk.Frame(panel, style="Panel.TFrame")
        garage_bar.pack(fill="x", pady=(0, 8))
        ttk.Label(garage_bar, text="GARAGE", style="Section.TLabel").pack(side="left", padx=(0, 8))
        self.garage_picker = ttk.Combobox(garage_bar, state="readonly", width=25)
        self.garage_picker.pack(side="left", padx=(0, 8))
        self.garage_picker.bind("<<ComboboxSelected>>", self._choose_garage)
        ttk.Button(garage_bar, text="MANAGE GARAGES", style="Secondary.TButton",
                   command=self._manage_garages).pack(side="left", padx=(0, 6))
        ttk.Button(garage_bar, text="IMPORT", style="Secondary.TButton",
                   command=self._import_garage_file).pack(side="left", padx=(0, 6))
        if OFFICIAL_RELEASE:
            ttk.Button(garage_bar, text="EXPORT GARAGE", style="Secondary.TButton",
                       command=self._export_garage).pack(side="left")
        else:
            export_button = ttk.Menubutton(garage_bar, text="EXPORT", style="Secondary.TButton")
            export_menu = tk.Menu(export_button, tearoff=False)
            export_menu.add_command(label="Export garage...", command=self._export_garage)
            export_menu.add_command(label="Export OnnY presets from this garage...", command=self._export_presets)
            export_button.configure(menu=export_menu)
            export_button.pack(side="left")
        self._refresh_garage_picker()
        toolbar = ttk.Frame(panel, style="Panel.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Label(toolbar, text="FILTER", style="Section.TLabel").pack(side="left", padx=(0, 12))
        self.filter_class = ttk.Combobox(toolbar, values=["All", *WEIGHT_CLASSES], state="readonly", width=12)
        self.filter_class.set("All")
        self.filter_class.pack(side="left", padx=(0, 12))
        self.filter_class.bind("<<ComboboxSelected>>", lambda _e: self._refresh_garage())
        ttk.Label(toolbar, text="SEARCH", style="Section.TLabel").pack(side="left", padx=(0, 8))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh_garage())
        ttk.Entry(toolbar, textvariable=self.search_var, width=26).pack(side="left")
        self.garage_count = ttk.Label(toolbar, text="", style="Panel.TLabel")
        self.garage_count.pack(side="right")

        columns = ("number", "name", "vehicle", "class", "on")
        table = ttk.Frame(panel, style="Panel.TFrame")
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=columns, show="headings", selectmode="browse")
        for col, text, width, minimum, anchor, stretch in (
            ("number", "NO.", 65, 50, "center", False),
            ("name", "CREATION", 250, 150, "w", True),
            ("vehicle", "REPLACES STOCK VEHICLE", 260, 200, "w", True),
            ("class", "CLASS", 90, 75, "center", False),
            ("on", "IN MOD", 80, 65, "center", False),
        ):
            self.tree.heading(col, text=text, anchor=anchor)
            self.tree.column(col, width=width, minwidth=minimum, anchor=anchor, stretch=stretch)
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("conflict", foreground=COLORS["danger"])
        self.tree.tag_configure("off", foreground="#85838b")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._update_garage_actions())

        actions = ttk.Frame(panel, style="Panel.TFrame")
        actions.pack(fill="x", pady=(10, 0))
        self.edit_selected_button = ttk.Button(actions, text="EDIT SELECTED", style="Secondary.TButton", command=self._edit_selected)
        self.edit_selected_button.pack(side="left")
        self.toggle_selected_button = ttk.Button(actions, text="INCLUDE / EXCLUDE", style="Secondary.TButton", command=self._toggle_selected)
        self.toggle_selected_button.pack(side="left", padx=6)
        self.delete_selected_button = ttk.Button(actions, text="DELETE", style="Secondary.TButton", command=self._delete_selected)
        self.delete_selected_button.pack(side="left")
        self.file_selected_button = ttk.Menubutton(actions, text="FILE VEHICLE", style="Secondary.TButton")
        file_menu = tk.Menu(self.file_selected_button, tearoff=False)
        file_menu.add_command(label="Copy to another garage...", command=lambda: self._file_selected(False))
        file_menu.add_command(label="Move to another garage...", command=lambda: self._file_selected(True))
        file_menu.add_separator()
        file_menu.add_command(label="Export vehicle...", command=self._export_vehicle)
        self.file_selected_button.configure(menu=file_menu)
        self.file_selected_button.pack(side="left", padx=6)
        ttk.Button(
            actions,
            text="BUILD & INSTALL  >",
            style="Primary.TButton",
            command=lambda: self._navigate("install"),
        ).pack(side="right")
        self.garage_note = tk.Label(
            page,
            text="",
            background=COLORS["background"],
            foreground=COLORS["danger"],
            anchor="w",
            font=("Segoe UI", 9, "bold"),
        )
        self.garage_note.pack(fill="x", pady=(8, 0))

    def _selected_creation(self) -> Creation | None:
        selection = self.tree.selection()
        if not selection:
            return None
        number = int(selection[0])
        return next((c for c in self.library.all() if c.number == number), None)

    def _refresh_garage(self) -> None:
        creations = self.library.all()
        conflicts = {c.number for items in slot_conflicts(creations).values() for c in items}
        wanted_class = self.filter_class.get()
        query = self.search_var.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        visible_count = 0
        for c in creations:
            vehicle = VEHICLES[c.slot]
            if wanted_class != "All" and vehicle.weight_label != wanted_class:
                continue
            if query and query not in c.name.lower() and query not in vehicle.name.lower():
                continue
            visible_count += 1
            tags = []
            if c.number in conflicts:
                tags.append("conflict")
            if not c.enabled:
                tags.append("off")
            self.tree.insert(
                "", "end", iid=str(c.number), tags=tags,
                values=(f"#{c.number}", c.name, vehicle.name, vehicle.weight_label, "Yes" if c.enabled else "No"),
            )
        included_count = sum(1 for creation in creations if creation.enabled)
        self.garage_count.config(
            text=f"{visible_count} SHOWN  |  {included_count} INCLUDED",
        )
        if conflicts:
            self.garage_note.config(
                text="Two included creations replace the same vehicle. Exclude one before installing.",
                foreground=COLORS["danger"],
            )
        elif not creations:
            self.garage_note.config(
                text="No vehicles yet. Choose CREATE VEHICLE to get started.",
                foreground=COLORS["muted"],
            )
        else:
            self.garage_note.config(text="")
        self._update_garage_actions()

    def _update_garage_actions(self) -> None:
        state = ["!disabled"] if self.tree.selection() else ["disabled"]
        for button in (self.edit_selected_button, self.toggle_selected_button, self.delete_selected_button, self.file_selected_button):
            button.state(state)

    def _refresh_garage_picker(self) -> None:
        self.garage_picker.configure(values=[name for _, name in self.garages.entries()])
        self.garage_picker.set(self.garages.active_name)
        if hasattr(self, "garage_collection_button"):
            self.garage_collection_button.config(text=self._garage_collection_label())

    def _garage_collection_label(self) -> str:
        name = self.garages.active_name
        return "Garage: " + (name if len(name) <= 24 else name[:21] + "...")

    def _activate_garage(self, garage_id: str) -> None:
        self.garages.select(garage_id)
        self.library = self.garages.library()
        self._refresh_garage_picker()
        self._refresh_garage()
        if hasattr(self, "install_summary"):
            self.build_collection.set("garage")
            self.fit_garage_names.set(self.garages.fit_names())
            self._refresh_install_summary()

    def _choose_garage(self, _event=None) -> None:
        chosen = self.garage_picker.get()
        garage_id = next((key for key, name in self.garages.entries() if name == chosen), None)
        if garage_id is None:
            self._refresh_garage_picker()
            messagebox.showerror("Choose garage", "The selected garage no longer exists.", parent=self)
            return
        try:
            self._activate_garage(garage_id)
        except (OSError, ValueError) as err:
            self._refresh_garage_picker()
            messagebox.showerror("Choose garage", str(err), parent=self)

    def _manage_garages(self) -> None:
        window = tk.Toplevel(self)
        window.title("Manage garages")
        window.transient(self)
        window.geometry("600x420")
        window.configure(background=COLORS["background"])
        frame = ttk.Frame(window, style="App.TFrame", padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="YOUR GARAGES", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Each garage is independent. Select one to manage it.",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 8))
        actions = ttk.Frame(frame, style="App.TFrame")
        actions.pack(side="bottom", fill="x", pady=(8, 0))
        listing = tk.Listbox(frame, exportselection=False, background=COLORS["panel"],
                             foreground=COLORS["text"], selectbackground=COLORS["selected"])
        listing.pack(fill="both", expand=True)
        entries: list[tuple[str, str]] = []

        def refresh(selected: str | None = None) -> None:
            entries[:] = self.garages.entries()
            listing.delete(0, "end")
            for index, (garage_id, name) in enumerate(entries):
                suffix = "  (current)" if garage_id == self.garages.active_id else ""
                listing.insert("end", name + suffix)
                if garage_id == (selected or self.garages.active_id):
                    listing.selection_set(index)
                    listing.see(index)
            self._refresh_garage_picker()

        def selected() -> str | None:
            selection = listing.curselection()
            return entries[selection[0]][0] if selection else None

        def ask_name(title: str, initial: str = "") -> str | None:
            return simpledialog.askstring(title, "Garage name:", initialvalue=initial, parent=window)

        def run(action) -> None:
            try:
                action()
            except (OSError, ValueError) as err:
                messagebox.showerror("Manage garages", str(err), parent=window)

        def create() -> None:
            name = ask_name("New garage")
            if name is not None:
                def save():
                    garage_id = self.garages.create(name)
                    self._activate_garage(garage_id)
                    refresh(garage_id)
                run(save)

        def rename() -> None:
            garage_id = selected()
            if garage_id is None:
                return
            name = ask_name("Rename garage", self.garages.name(garage_id))
            if name is not None:
                def save():
                    self.garages.rename(garage_id, name)
                    self._refresh_garage_picker()
                    if hasattr(self, "install_summary"):
                        self._refresh_install_summary()
                    refresh(garage_id)
                run(save)

        def duplicate(onny: bool = False) -> None:
            garage_id = selected()
            if onny:
                initial = "OnnY's Customs"
            elif garage_id is not None:
                initial = self.garages.name(garage_id) + " copy"
            else:
                return
            name = ask_name("Copy garage", initial)
            if name is not None:
                def save():
                    if onny:
                        items = presets.creations(None if OFFICIAL_RELEASE else self.root_dir)
                        fit_names = True
                    elif garage_id is not None:
                        items = self.garages.library(garage_id).all()
                        fit_names = self.garages.fit_names(garage_id)
                    else:
                        raise ValueError("Choose a garage to duplicate.")
                    new_id = self.garages.create(name, items, fit_names=fit_names)
                    self._activate_garage(new_id)
                    refresh(new_id)
                run(save)

        def delete() -> None:
            garage_id = selected()
            if garage_id is None:
                return
            name = self.garages.name(garage_id)
            if not messagebox.askyesno("Delete garage", f"Delete '{name}' and its saved vehicles?\n"
                                      "Other garages and installed mods are not changed.", parent=window):
                return
            def remove():
                try:
                    self.garages.delete(garage_id)
                finally:
                    self.library = self.garages.library()
                    self._refresh_garage()
                    self._refresh_garage_picker()
                    if hasattr(self, "install_summary"):
                        self.fit_garage_names.set(self.garages.fit_names())
                        self._refresh_install_summary()
                    refresh()
            run(remove)

        def use() -> None:
            garage_id = selected()
            if garage_id is not None:
                def activate():
                    self._activate_garage(garage_id)
                    window.destroy()
                run(activate)

        for text, command in (("NEW", create), ("RENAME", rename), ("DUPLICATE", duplicate),
                              ("COPY ONNY'S", lambda: duplicate(True)), ("DELETE", delete), ("USE", use)):
            ttk.Button(actions, text=text, style="Secondary.TButton", command=command).pack(side="left", padx=(0, 4))
        listing.bind("<Double-1>", lambda _event: use())
        refresh()

    def _file_selected(self, move: bool) -> None:
        creation = self._selected_creation()
        if creation is None:
            return
        entries = [(key, name) for key, name in self.garages.entries() if key != self.garages.active_id]
        if not entries:
            messagebox.showinfo("File vehicle", "Create another garage first.", parent=self)
            return
        window = tk.Toplevel(self)
        window.title("Move vehicle" if move else "Copy vehicle")
        window.transient(self)
        window.configure(background=COLORS["background"])
        frame = ttk.Frame(window, style="App.TFrame", padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"Choose a garage for {creation.name}:", style="App.TLabel").pack(anchor="w")
        target = ttk.Combobox(frame, values=[name for _, name in entries], state="readonly", width=32)
        target.current(0)
        target.pack(fill="x", pady=10)

        def apply() -> None:
            index = target.current()
            if not 0 <= index < len(entries):
                return
            try:
                _, conflict = self.garages.file_vehicle(creation, entries[index][0], move=move)
            except (OSError, ValueError) as err:
                messagebox.showerror("File vehicle", str(err), parent=window)
                return
            window.destroy()
            self._refresh_garage()
            if conflict:
                messagebox.showinfo("Vehicle filed", "The destination already uses that slot. "
                                    "The filed vehicle was excluded from its mod.", parent=self)

        ttk.Button(frame, text="MOVE" if move else "COPY", style="Primary.TButton", command=apply).pack(anchor="e")

    def _save_garage_file(self, name: str, items: list[Creation], *, vehicle: bool = False) -> None:
        try:
            initial = self.settings.picker_folder("garage_export")
        except OSError as err:
            messagebox.showerror("Export", str(err), parent=self)
            return
        chosen = filedialog.asksaveasfilename(
            parent=self, title="Export vehicle" if vehicle else "Export garage",
            initialdir=str(initial), initialfile="vehicle.json" if vehicle else "garage.json",
            defaultextension=".json", filetypes=[("Garage files", "*.json")],
        )
        if not chosen:
            return
        try:
            garages.export_file(Path(chosen), name, items, vehicle=vehicle,
                                fit_names=self.garages.fit_names() if not vehicle else False)
        except (OSError, ValueError) as err:
            messagebox.showerror("Export failed", str(err), parent=self)
            return
        try:
            self.settings.remember_folder("garage_export", chosen, True, self.root_dir)
        except OSError as err:
            messagebox.showwarning("Remember folder", f"Export succeeded, but its folder could not be saved: {err}", parent=self)
        messagebox.showinfo("Export complete", "Exported stats and texture references, not texture or game files.", parent=self)

    def _export_garage(self) -> None:
        self._save_garage_file(self.garages.active_name, self.library.all())

    def _export_vehicle(self) -> None:
        creation = self._selected_creation()
        if creation is not None:
            self._save_garage_file(creation.name, [creation], vehicle=True)

    def _import_garage_file(self) -> None:
        chosen = self._choose_path("garage_import", is_file=True, title="Import garage or vehicle",
                                   filetypes=[("Garage and preset files", "*.json"), ("All files", "*.*")])
        if not chosen:
            return
        try:
            kind, name, items, fit_names = garages.import_file(Path(chosen))
            missing = garages.missing_textures(items, texture_dir(self.root_dir))
        except (OSError, ValueError) as err:
            messagebox.showerror("Import failed", str(err), parent=self)
            return
        if kind in ("garage", "presets"):
            name = simpledialog.askstring("Import garage", "Name for the new garage:", initialvalue=name, parent=self)
            if name is None:
                return
            try:
                garage_id = self.garages.create(name, items, fit_names=fit_names)
                self._activate_garage(garage_id)
            except (OSError, ValueError) as err:
                messagebox.showerror("Import failed", str(err), parent=self)
                return
            detail = f"Imported {len(items)} vehicle(s) into {name.strip()}."
        else:
            try:
                _, conflict = self.garages.add_vehicle(items[0])
            except (OSError, ValueError) as err:
                messagebox.showerror("Import failed", str(err), parent=self)
                return
            self._refresh_garage()
            detail = f"Imported {items[0].name} into {self.garages.active_name}."
            if conflict:
                detail += "\nThe slot is already used, so the imported vehicle is excluded."
        if missing:
            detail += "\n\nTexture files are not included or failed their checksum. Re-import the textures for: " + ", ".join(missing)
        messagebox.showinfo("Import complete", detail, parent=self)

    def _toggle_selected(self) -> None:
        creation = self._selected_creation()
        if creation:
            creation.enabled = not creation.enabled
            self.library.save(creation)
            self._refresh_garage()

    def _delete_selected(self) -> None:
        creation = self._selected_creation()
        if creation and messagebox.askyesno("Delete", f"Delete #{creation.number} {creation.name}?"):
            self.library.delete(creation.number)
            self._refresh_garage()

    def _edit_selected(self) -> None:
        creation = self._selected_creation()
        if creation and self._require_stock():
            self._changing_stock_vehicle = False
            self._start_editing(creation)

    def _new_creation(self) -> None:
        if self._require_stock():
            self._changing_stock_vehicle = False
            self.editing = None
            self.selected_slot = None
            self.vehicle_class_filter.set("All")
            self.vehicle_kind_filter.set("All")
            self.vehicle_search_var.set("")
            self._fill_vehicles()
            self.show_page("vehicles")

    # ---------- vehicle selection ----------

    def _build_vehicle_page(self) -> None:
        page = self._new_page("vehicles")
        ttk.Label(page, text="CHOOSE A STOCK VEHICLE", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(
            page,
            text="Your creation takes this vehicle's place in the game.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(3, 12))

        panel = ttk.Frame(page, style="Panel.TFrame", padding=12)
        panel.pack(fill="both", expand=True)
        filters = ttk.Frame(panel, style="Panel.TFrame")
        filters.pack(fill="x", pady=(0, 8))
        ttk.Label(filters, text="CLASS", style="Section.TLabel").pack(side="left", padx=(0, 8))
        self.vehicle_class_filter = ttk.Combobox(
            filters,
            values=["All", *WEIGHT_CLASSES],
            state="readonly",
            width=12,
        )
        self.vehicle_class_filter.set("All")
        self.vehicle_class_filter.pack(side="left", padx=(0, 16))
        self.vehicle_class_filter.bind("<<ComboboxSelected>>", lambda _e: self._fill_vehicles())
        ttk.Label(filters, text="TYPE", style="Section.TLabel").pack(side="left", padx=(0, 8))
        self.vehicle_kind_filter = tk.StringVar(value="All")
        for kind in ("All", "Kart", "Bike"):
            ttk.Radiobutton(
                filters,
                text=f"{kind.upper()}S" if kind != "All" else "ALL",
                value=kind,
                variable=self.vehicle_kind_filter,
                command=self._fill_vehicles,
            ).pack(side="left", padx=3)
        ttk.Label(filters, text="SEARCH", style="Section.TLabel").pack(side="left", padx=(16, 8))
        self.vehicle_search_var = tk.StringVar()
        self.vehicle_search_var.trace_add("write", lambda *_: self._fill_vehicles())
        ttk.Entry(filters, textvariable=self.vehicle_search_var, width=24).pack(side="left")

        grid_area = ttk.Frame(panel, style="Panel.TFrame")
        grid_area.pack(fill="both", expand=True)
        self.vehicle_canvas = tk.Canvas(
            grid_area,
            background=COLORS["panel"],
            highlightthickness=0,
            borderwidth=0,
        )
        self.vehicle_canvas.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(grid_area, orient="vertical", command=self.vehicle_canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.vehicle_canvas.configure(yscrollcommand=scrollbar.set)
        self.vehicle_grid = ttk.Frame(self.vehicle_canvas, style="Panel.TFrame")
        self.vehicle_grid_window = self.vehicle_canvas.create_window(
            (0, 0),
            window=self.vehicle_grid,
            anchor="nw",
        )
        self.vehicle_grid.bind(
            "<Configure>",
            lambda _e: self.vehicle_canvas.configure(scrollregion=self.vehicle_canvas.bbox("all")),
        )
        self.vehicle_canvas.bind(
            "<Configure>",
            lambda event: self.vehicle_canvas.itemconfigure(self.vehicle_grid_window, width=event.width),
        )
        self.visible_slots: list[int] = []
        self.vehicle_buttons: dict[int, tk.Button] = {}

        selection = ttk.Frame(panel, style="Panel.TFrame", padding=(10, 8, 10, 0))
        selection.pack(fill="x", pady=(8, 0))
        self.vehicle_selection_info = tk.Label(
            selection,
            text="Choose one of the stock vehicles above.",
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            anchor="w",
            justify="left",
            font=("Segoe UI", 10),
        )
        self.vehicle_selection_info.pack(side="left", fill="x", expand=True)
        self.vehicle_continue_button = ttk.Button(
            selection,
            text="TUNE THIS VEHICLE  >",
            style="Primary.TButton",
            command=self._continue_vehicle_selection,
        )
        self.vehicle_continue_button.pack(side="right")

        self._fill_vehicles()

    def _fill_vehicles(self, select_slot: int | None = None) -> None:
        if select_slot is not None:
            self.selected_slot = select_slot
        if not hasattr(self, "vehicle_grid"):
            return
        for child in self.vehicle_grid.winfo_children():
            child.destroy()
        self.vehicle_buttons.clear()

        wanted_class = self.vehicle_class_filter.get()
        wanted_kind = self.vehicle_kind_filter.get()
        query = self.vehicle_search_var.get().strip().lower()
        self.visible_slots = []
        for column in range(3):
            self.vehicle_grid.columnconfigure(column, weight=1, uniform="vehicle")
        visible = [
            vehicle for vehicle in VEHICLES
            if (wanted_class == "All" or vehicle.weight_label == wanted_class)
            and (wanted_kind == "All" or vehicle.kind == wanted_kind)
            and (not query or query in vehicle.name.lower())
        ]
        used: dict[int, list[Creation]] = {}
        for creation in self.library.all():
            used.setdefault(creation.slot, []).append(creation)
        for index, vehicle in enumerate(visible):
            row, column = divmod(index, 3)
            selected = vehicle.slot == self.selected_slot
            occupants = []
            for creation in used.get(vehicle.slot, []):
                if self.editing is not None and creation.number == self.editing.number:
                    occupants.append(f"{creation.name} (editing)")
                elif not creation.enabled:
                    occupants.append(f"{creation.name} (excluded)")
                else:
                    occupants.append(f"{creation.name} (in mod)")
            button = tk.Button(
                self.vehicle_grid,
                text=(f"{vehicle.name}\n{vehicle.kind.upper()}  /  {vehicle.weight_label.upper()}"
                      + ("\nSAVED: " + ", ".join(occupants) if occupants else "")),
                command=lambda slot=vehicle.slot: self._select_vehicle(slot),
                background=COLORS["selected"] if selected else COLORS["panel_alt"],
                foreground=COLORS["text"],
                activebackground=COLORS["selected"],
                activeforeground=COLORS["text"],
                highlightthickness=2,
                highlightbackground=COLORS["gold"] if selected else COLORS["panel_alt"],
                highlightcolor=COLORS["gold"],
                relief="flat",
                borderwidth=0,
                padx=8,
                pady=9,
                justify="left",
                anchor="nw",
                font=("Segoe UI", 10, "bold"),
                cursor="hand2",
            )
            button.grid(row=row, column=column, sticky="nsew", padx=5, pady=5)
            self.visible_slots.append(vehicle.slot)
            self.vehicle_buttons[vehicle.slot] = button

        self.vehicle_selection_info.configure(text=self._vehicle_selection_text())
        if self.selected_slot is None:
            self.vehicle_continue_button.state(["disabled"])
        else:
            self.vehicle_continue_button.state(["!disabled"])

    def _vehicle_selection_text(self) -> str:
        if self.selected_slot is None:
            return "Choose one of the stock vehicles above."
        vehicle = VEHICLES[self.selected_slot]
        return (
            f"SELECTED: {vehicle.name}  |  {vehicle.kind}  |  {vehicle.weight_label}\n"
            "Your creation will replace this stock vehicle."
        )

    def _select_vehicle(self, slot: int) -> None:
        old = self.selected_slot
        self.selected_slot = slot
        for current in (old, slot):
            button = self.vehicle_buttons.get(current)
            if button:
                selected = current == slot
                button.config(background=COLORS["selected"] if selected else COLORS["panel_alt"],
                              highlightbackground=COLORS["gold"] if selected else COLORS["panel_alt"])
        self.vehicle_selection_info.configure(text=self._vehicle_selection_text())
        self.vehicle_continue_button.state(["!disabled"])

    def _continue_vehicle_selection(self) -> None:
        if self.selected_slot is not None:
            self._start_editing(self.editing, slot=self.selected_slot)

    # ---------- editor page ----------

    def _build_editor_page(self) -> None:
        page = self._new_page("editor")
        actions = ttk.Frame(page, style="App.TFrame")
        actions.pack(side="bottom", fill="x", pady=(10, 0))
        self.editor_back_button = ttk.Button(actions, text="< BACK TO GARAGE", style="Secondary.TButton", command=self._cancel_editing)
        self.editor_back_button.pack(side="left")
        ttk.Button(actions, text="RESET STATS", style="Secondary.TButton", command=self._reset_to_stock).pack(side="left", padx=8)
        self.save_vehicle_button = ttk.Button(actions, text="SAVE VEHICLE", style="Primary.TButton", command=self._save_creation)
        self.save_vehicle_button.pack(side="right")
        self.save_vehicle_button.state(["disabled"])

        self.advanced_open = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            page,
            text="SHOW ADVANCED GAME VALUES",
            variable=self.advanced_open,
            command=self._toggle_advanced,
        ).pack(side="bottom", anchor="w", pady=(8, 0))

        scroll_area = ttk.Frame(page, style="App.TFrame")
        scroll_area.pack(fill="both", expand=True)
        self.editor_canvas = tk.Canvas(scroll_area, background=COLORS["background"], highlightthickness=0)
        self.editor_canvas.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(scroll_area, orient="vertical", command=self.editor_canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.editor_canvas.configure(yscrollcommand=scrollbar.set)
        content = ttk.Frame(self.editor_canvas, style="App.TFrame")
        content_window = self.editor_canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind(
            "<Configure>",
            lambda _event: self.editor_canvas.configure(scrollregion=self.editor_canvas.bbox("all")),
        )
        self.editor_canvas.bind(
            "<Configure>",
            lambda event: self.editor_canvas.itemconfigure(content_window, width=event.width),
        )
        heading = ttk.Frame(content, style="App.TFrame")
        heading.pack(fill="x", pady=(2, 12))
        ttk.Label(heading, text="TUNE YOUR VEHICLE", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(
            heading,
            text="Set its in-game name and adjust the stats. Your original game files stay unchanged.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(3, 0))

        identity = ttk.Frame(content, style="Panel.TFrame", padding=12)
        identity.pack(fill="x")
        identity_left = ttk.Frame(identity, style="Panel.TFrame")
        identity_left.pack(side="left", fill="x", expand=True)
        ttk.Label(identity_left, text="IN-GAME NAME (REQUIRED)", style="Section.TLabel").pack(anchor="w")
        name_row = ttk.Frame(identity_left, style="Panel.TFrame")
        name_row.pack(anchor="w", pady=(4, 0))
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(
            name_row,
            textvariable=self.name_var,
            width=28,
        )
        self.name_entry.pack(side="left")
        self.name_counter = ttk.Label(name_row, text="0 UTF-16 units", style="Panel.TLabel")
        self.name_counter.pack(side="left", padx=8)
        ttk.Label(
            identity_left, text="Available name space is checked when building; long names may be clipped in-game.",
            style="Panel.TLabel", wraplength=410,
        ).pack(anchor="w", pady=(4, 0))
        self.name_var.trace_add("write", lambda *_: self._update_name_counter())
        texture_row = ttk.Frame(identity_left, style="Panel.TFrame")
        texture_row.pack(anchor="w", pady=(8, 0))
        self.browse_texture_button = ttk.Button(texture_row, text="BROWSE TEXTURES", style="Secondary.TButton", command=self._browse_textures)
        self.browse_texture_button.pack(side="left")
        self.clear_texture_button = ttk.Button(texture_row, text="CLEAR", style="Secondary.TButton", command=self._clear_texture)
        self.clear_texture_button.pack(side="left", padx=6)
        self.texture_source_button = ttk.Button(texture_row, text="SOURCE", style="Secondary.TButton", command=self._open_texture_source)
        self.texture_source_button.pack(side="left")
        self.texture_label = ttk.Label(identity_left, text="Texture: stock appearance", style="Panel.TLabel", wraplength=410)
        self.texture_label.pack(anchor="w", pady=(4, 0))

        identity_right = ttk.Frame(identity, style="Panel.TFrame")
        identity_right.pack(side="right", padx=(16, 0))
        self.editor_vehicle_label = ttk.Label(
            identity_right,
            text="NO STOCK VEHICLE SELECTED",
            style="Section.TLabel",
            justify="right",
        )
        self.editor_vehicle_label.pack(anchor="e")
        self.number_label = ttk.Label(identity_right, text="", style="Panel.TLabel")
        self.number_label.pack(anchor="e", pady=(3, 0))
        self.change_stock_button = ttk.Button(
            identity_right,
            text="CHANGE STOCK VEHICLE",
            style="Secondary.TButton",
            command=self._change_stock_vehicle,
        )
        self.change_stock_button.pack(anchor="e", pady=(8, 0))

        bars = ttk.LabelFrame(
            content,
            text="  PERFORMANCE STATS  ",
            padding=10,
            style="Panel.TLabelframe",
        )
        bars.pack(fill="x", pady=10)
        self.bar_vars: dict[str, tk.DoubleVar] = {}
        self.bar_value_vars: dict[str, tk.StringVar] = {}
        self.bar_stock_labels: dict[str, ttk.Label] = {}
        self._bar_values: dict[str, tuple[str, float | int]] = {}
        self._advanced_values: dict[str, tuple[str, float | int]] = {}
        self._syncing_bar = False
        for row, bar in enumerate(BARS):
            label = ttk.Label(bars, text=bar.label.upper(), width=15, style="Panel.TLabel")
            label.grid(row=row, column=0, sticky="w", pady=3)
            var = tk.DoubleVar(value=50.0)
            self.bar_vars[bar.key] = var
            scale = ttk.Scale(
                bars,
                from_=0,
                to=100,
                variable=var,
                length=310,
                command=lambda _v, b=bar: self._bar_moved(b),
            )
            scale.grid(row=row, column=1, padx=10, pady=3, sticky="ew")
            value_var = tk.StringVar()
            self.bar_value_vars[bar.key] = value_var
            entry = ttk.Entry(bars, textvariable=value_var, width=13)
            entry.grid(row=row, column=2, padx=4, pady=3)
            entry.bind("<Return>", lambda _e, b=bar: self._numeric_bar_edited(b))
            entry.bind("<FocusOut>", lambda _e, b=bar: self._numeric_bar_edited(b))
            for widget in (label, scale, entry):
                ToolTip(widget, lambda b=bar: self._stat_tooltip(b.field, b.hint, b.low, b.high))
            stock_label = ttk.Label(bars, text="", width=16, style="Panel.TLabel")
            stock_label.grid(row=row, column=3, sticky="w", padx=8)
            self.bar_stock_labels[bar.key] = stock_label
            ttk.Label(
                bars,
                text=bar.hint,
                foreground=COLORS["muted"],
                background=COLORS["panel"],
            ).grid(row=row, column=4, sticky="w", padx=8)
        bars.columnconfigure(1, weight=1)
        self.advanced_frame = ttk.LabelFrame(
            content,
            text="  ADVANCED STATS  ",
            padding=8,
            style="Panel.TLabelframe",
        )
        self.advanced_vars: dict[str, tk.StringVar] = {}
        self.advanced_slider_vars: dict[str, tk.DoubleVar] = {}
        self.advanced_sliders: dict[str, ttk.Scale] = {}
        self._advanced_ranges: dict[str, tuple[float, float]] = {}
        self._syncing_advanced = False
        for i, (field, label, hint) in enumerate(ADVANCED_FIELDS):
            var = tk.StringVar()
            self.advanced_vars[field] = var
            row, column = divmod(i, 2)
            label_widget = ttk.Label(self.advanced_frame, text=label, width=23, style="Panel.TLabel")
            label_widget.grid(row=row, column=column * 3, sticky="w", pady=2)
            slider_var = tk.DoubleVar(value=0.0)
            self.advanced_slider_vars[field] = slider_var
            slider = ttk.Scale(
                self.advanced_frame, from_=0, to=1, variable=slider_var, length=110,
                command=lambda _value, f=field: self._advanced_moved(f),
            )
            slider.grid(row=row, column=column * 3 + 1, sticky="ew", padx=(0, 6), pady=2)
            self.advanced_sliders[field] = slider
            entry = ttk.Entry(self.advanced_frame, textvariable=var, width=12)
            entry.grid(row=row, column=column * 3 + 2, padx=(0, 12), pady=2)
            entry.bind("<Return>", lambda _event, f=field, name=label: self._numeric_advanced_edited(f, name))
            entry.bind("<FocusOut>", lambda _event, f=field, name=label: self._numeric_advanced_edited(f, name))
            for widget in (label_widget, slider, entry):
                ToolTip(widget, lambda f=field, h=hint: self._advanced_tooltip(f, h))
        self.advanced_frame.columnconfigure(1, weight=1)
        self.advanced_frame.columnconfigure(4, weight=1)

    def _advanced_tooltip(self, field: str, hint: str) -> str:
        limits = self._advanced_ranges.get(field)
        if limits is None:
            return self._stat_tooltip(field, hint)
        return self._stat_tooltip(field, hint, *limits)

    def _stat_tooltip(self, field: str, hint: str, low=None, high=None) -> str:
        text = hint
        if low is not None:
            text += f"\nSlider range: {format_value(low)} to {format_value(high)} (values outside are allowed)."
        if self.stock is not None:
            values = [vehicle.get(field) for vehicle in self.stock.vehicles]
            text += f"\nStock vehicles: {format_value(min(values))} to {format_value(max(values))}."
        return text

    def _toggle_advanced(self) -> None:
        if self.advanced_open.get():
            self.advanced_frame.pack(fill="x", pady=6)
            self.after_idle(self._scroll_to_advanced)
        else:
            self.advanced_frame.pack_forget()

    def _scroll_to_advanced(self) -> None:
        if self.advanced_open.get():
            self.editor_canvas.update_idletasks()
            bounds = self.editor_canvas.bbox("all")
            if bounds and bounds[3] > 0:
                self.editor_canvas.yview_moveto(self.advanced_frame.winfo_y() / bounds[3])

    def _update_name_counter(self) -> None:
        units = len(self.name_var.get().encode("utf-16-be", errors="surrogatepass")) // 2
        self.name_counter.config(text=f"{units} UTF-16 units")
        self.save_vehicle_button.state(
            ["!disabled"] if self.selected_slot is not None else ["disabled"]
        )

    def _change_stock_vehicle(self) -> None:
        self._changing_stock_vehicle = True
        self._fill_vehicles(select_slot=self.selected_slot)
        self.show_page("vehicles")

    def _cancel_editing(self) -> None:
        self.editing = None
        self._changing_stock_vehicle = False
        self._refresh_garage()
        self.show_page("garage")

    def _browse_textures(self) -> None:
        slot = self._current_slot()
        if slot is not None:
            TextureBrowser(self, slot, self._apply_texture)

    def _apply_texture(self, pack: TexturePack) -> None:
        if pack.slot != self._current_slot():
            messagebox.showwarning("Vehicle changed", "Choose a texture for the current vehicle.")
            return
        self.edit_texture = pack
        self._refresh_texture_label()

    def _clear_texture(self) -> None:
        self.edit_texture = None
        self._refresh_texture_label()

    def _open_texture_source(self) -> None:
        if self.edit_texture and self.edit_texture.source:
            if not webbrowser.open(self.edit_texture.source):
                messagebox.showerror("Open browser", "Could not open the texture source.")

    def _refresh_texture_label(self) -> None:
        if self.edit_texture:
            self.clear_texture_button.state(["!disabled"])
            parsed = urllib.parse.urlsplit(self.edit_texture.source)
            self.texture_source_button.state(["!disabled"] if parsed.scheme in ("https", "http") and parsed.netloc else ["disabled"])
            credit = f" by {self.edit_texture.author}" if self.edit_texture.author else ""
            self.texture_label.config(
                text=f"Texture: {self.edit_texture.name}{credit} ({len(self.edit_texture.files)} race files). "
                     "The in-game selection preview remains stock."
            )
        else:
            self.clear_texture_button.state(["disabled"])
            self.texture_source_button.state(["disabled"])
            self.texture_label.config(text="Texture: stock appearance")

    def _current_slot(self) -> int | None:
        return self.selected_slot

    def _vehicle_picked(self) -> None:
        slot = self._current_slot()
        if slot is not None:
            self._select_vehicle(slot)

    def _stock_value(self, slot: int, field: str):
        return self.stock.vehicles[slot].get(field)

    def _load_values(self, slot: int, overrides: dict) -> None:
        vehicle = VEHICLES[slot]
        self.editor_vehicle_label.config(
            text=f"REPLACES {vehicle.name.upper()}  |  {vehicle.kind.upper()} / {vehicle.weight_label.upper()}"
        )
        for bar in BARS:
            value = overrides.get(bar.field, self._stock_value(slot, bar.field))
            self._set_bar_value(bar, value, slot)
        for field, _label, _hint in ADVANCED_FIELDS:
            value = overrides.get(field, self._stock_value(slot, field))
            values = [vehicle.get(field) for vehicle in self.stock.vehicles]
            low, high = advanced_slider_range(field, values)
            self._advanced_ranges[field] = (low, high)
            self._syncing_advanced = True
            try:
                self.advanced_sliders[field].configure(from_=low, to=high)
            finally:
                self._syncing_advanced = False
            self._set_advanced_value(field, value)

    def _set_advanced_value(self, field: str, value: float) -> None:
        low, high = self._advanced_ranges[field]
        self._syncing_advanced = True
        try:
            self.advanced_slider_vars[field].set(max(low, min(high, value)))
            shown = format_value(value)
            self._advanced_values[field] = (shown, value)
            self.advanced_vars[field].set(shown)
        finally:
            self._syncing_advanced = False

    def _advanced_moved(self, field: str) -> None:
        if self._syncing_advanced or self._current_slot() is None:
            return
        value = self.advanced_slider_vars[field].get()
        shown = format_value(value)
        self._advanced_values[field] = (shown, value)
        self.advanced_vars[field].set(shown)

    def _numeric_advanced_edited(self, field: str, label: str) -> None:
        if self._current_slot() is None:
            return
        try:
            text = self.advanced_vars[field].get().strip()
            shown, original = self._advanced_values[field]
            value = parse_advanced_value(str(original) if text == shown else text, label)
        except ValueError as err:
            messagebox.showwarning("Check the stat value", str(err))
            return
        self._set_advanced_value(field, value)

    def _set_bar_value(self, bar, value, slot: int) -> None:
        self._syncing_bar = True
        self.bar_vars[bar.key].set(bar.to_percent(float(value)))
        shown = format_value(value)
        self._bar_values[bar.key] = (shown, value)
        self.bar_value_vars[bar.key].set(shown)
        self._syncing_bar = False
        stock = self._stock_value(slot, bar.field)
        self.bar_stock_labels[bar.key].config(text=f"Stock: {stock:g}")

    def _bar_moved(self, bar) -> None:
        if self._syncing_bar:
            return
        slot = self._current_slot()
        if slot is None:
            return
        value = bar.from_percent(self.bar_vars[bar.key].get())
        shown = format_value(value)
        self._bar_values[bar.key] = (shown, value)
        self.bar_value_vars[bar.key].set(shown)
        stock = self._stock_value(slot, bar.field)
        self.bar_stock_labels[bar.key].config(text=f"Stock: {stock:g}")

    def _numeric_bar_edited(self, bar) -> None:
        try:
            text = self.bar_value_vars[bar.key].get().strip()
            shown, original = self._bar_values[bar.key]
            value = original if text == shown else bar.parse_value(text)
        except ValueError as err:
            messagebox.showwarning("Check the stat value", str(err))
            return
        slot = self._current_slot()
        if slot is not None:
            self._set_bar_value(bar, value, slot)

    def _start_editing(self, creation: Creation | None, slot: int | None = None) -> None:
        self.editing = creation
        if slot is None:
            slot = creation.slot if creation else (self.selected_slot if self.selected_slot is not None else 0)
        if self._changing_stock_vehicle:
            if self.edit_texture and self.edit_texture.slot != slot:
                self.edit_texture = None
                messagebox.showinfo("Texture cleared", "The texture was for the previous vehicle. Choose a compatible texture for this one.")
        else:
            self.edit_texture = creation.texture if creation and creation.slot == slot else None
        self._changing_stock_vehicle = False
        self.selected_slot = slot
        self._fill_vehicles(select_slot=slot)
        self.name_var.set(creation.name if creation else "")
        self._update_name_counter()
        self.number_label.config(text=(
            f"#{creation.number}" if creation and creation.number > 0 else f"#{self.library.next_number()} (new)"
        ))
        overrides = creation.stats if creation and creation.slot == slot else {}
        self._load_values(slot, overrides)
        self._refresh_texture_label()
        self.show_page("editor")

    def _reset_to_stock(self) -> None:
        slot = self._current_slot()
        if slot is not None:
            self._load_values(slot, {})

    def _collect_stats(self, slot: int) -> dict:
        stats: dict = {}
        for bar in BARS:
            text = self.bar_value_vars[bar.key].get().strip()
            shown, original = self._bar_values[bar.key]
            value = original if text == shown else bar.parse_value(text)
            stock = self._stock_value(slot, bar.field)
            if (value != stock if bar.is_int else not same_game_value(value, stock)):
                stats[bar.field] = value
        for field, label, _hint in ADVANCED_FIELDS:
            text = self.advanced_vars[field].get().strip()
            shown, original = self._advanced_values[field]
            value = parse_advanced_value(str(original) if text == shown else text, label)
            stock = self._stock_value(slot, field)
            if not same_game_value(value, stock):
                stats[field] = value
        return stats

    def _save_creation(self) -> None:
        slot = self._current_slot()
        name = self.name_var.get().strip()
        if slot is None:
            messagebox.showwarning("Pick a vehicle", "Choose the vehicle this creation replaces.")
            return
        if not name:
            messagebox.showwarning("Name it", "Give your creation a name.")
            self.name_entry.focus_set()
            return
        if not bmg.valid_vehicle_name(name):
            messagebox.showwarning(
                "Invalid name", "Use printable characters that can be encoded in UTF-16.",
            )
            return
        try:
            stats = self._collect_stats(slot)
        except ValueError as err:
            messagebox.showwarning("Check the stats", str(err))
            return
        number = self.editing.number if self.editing else 0
        creation = Creation(name=name, stats=stats, slot=slot, number=number, enabled=self.editing.enabled if self.editing else True, texture=self.edit_texture)
        others = [c for c in self.library.all() if c.slot == slot and c.number != number and c.enabled]
        if others and creation.enabled:
            names = ", ".join(f"#{c.number} {c.name}" for c in others)
            if messagebox.askyesno("Vehicle already used", f"{names} already replaces {VEHICLES[slot].name}.\nExclude it from the mod?"):
                for other in others:
                    other.enabled = False
                    self.library.save(other)
            else:
                creation.enabled = False
        self.library.save(creation)
        self.editing = creation
        self._refresh_garage()
        self.show_page("garage")

    # ---------- install page ----------

    def _build_install_page(self) -> None:
        outer = self._new_page("install")
        canvas = tk.Canvas(outer, background=COLORS["background"], highlightthickness=0, borderwidth=0)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=scrollbar.set)
        page = ttk.Frame(canvas, style="App.TFrame")
        content_window = canvas.create_window((0, 0), window=page, anchor="nw")
        page.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(content_window, width=event.width))
        canvas.bind("<MouseWheel>", lambda event: canvas.yview_scroll(-int(event.delta / 120), "units"))
        ttk.Label(page, text="BUILD & INSTALL", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(
            page,
            text="Review your vehicles and choose where the mod should go.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(3, 12))

        collection = ttk.LabelFrame(page, text="  VEHICLE COLLECTION  ", padding=8, style="Panel.TLabelframe")
        collection.pack(fill="x", pady=(0, 8))
        default_collection = self.settings.build_collection or ("garage" if self.library.all() else "onny")
        self.build_collection = tk.StringVar(value=default_collection)
        self.garage_collection_button = ttk.Radiobutton(
            collection, text=self._garage_collection_label(), variable=self.build_collection, value="garage",
            command=self._refresh_install_summary,
        )
        self.garage_collection_button.pack(side="left", padx=(0, 18))
        ttk.Radiobutton(
            collection, text="OnnY's Custom Vehicles (36)", variable=self.build_collection, value="onny",
            command=self._refresh_install_summary,
        ).pack(side="left")
        ttk.Button(
            collection, text="VIEW EXAMPLES", style="Secondary.TButton", command=self._show_presets,
        ).pack(side="right")
        name_options = ttk.Frame(page, style="App.TFrame")
        name_options.pack(fill="x", pady=(0, 8))
        self.fit_garage_names = tk.BooleanVar(value=self.garages.fit_names())
        ttk.Checkbutton(
            name_options, text="Shorten garage vehicle names if needed to fit the game",
            variable=self.fit_garage_names, command=self._save_fit_names,
        ).pack(anchor="w")

        self.folders = dolphin.find_folders(
            Path(self.settings.dolphintool).with_name("Dolphin.exe") if self.settings.dolphintool else None
        )
        box = ttk.LabelFrame(
            page,
            text="  INSTALL DESTINATIONS  ",
            padding=12,
            style="Panel.TLabelframe",
        )
        box.pack(fill="x")
        self.use_riivolution = tk.BooleanVar(value=self.settings.install_riivolution)
        self.use_sd_sync = tk.BooleanVar(value=self.settings.install_sd_sync)
        self.use_custom = tk.BooleanVar(value=self.settings.install_custom)
        self.custom_var = tk.StringVar(value=self.settings.output)
        ttk.Checkbutton(
            box,
            text="Dolphin Riivolution folder",
            variable=self.use_riivolution,
        ).grid(row=0, column=0, sticky="w")
        self.riivolution_path_label = ttk.Label(box, text=str(self.folders.riivolution), style="Panel.TLabel")
        self.riivolution_path_label.grid(row=0, column=1, sticky="w", padx=10)
        ttk.Checkbutton(
            box,
            text="Dolphin SD card sync folder",
            variable=self.use_sd_sync,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.sd_sync_path_label = ttk.Label(box, text=str(self.folders.sd_sync), style="Panel.TLabel")
        self.sd_sync_path_label.grid(row=1, column=1, sticky="w", padx=10, pady=(8, 0))
        ttk.Checkbutton(
            box,
            text="Other folder / real Wii SD card",
            variable=self.use_custom,
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(box, textvariable=self.custom_var, width=54).grid(
            row=2, column=1, padx=10, pady=(8, 0), sticky="ew"
        )
        ttk.Button(
            box,
            text="BROWSE",
            style="Secondary.TButton",
            command=lambda: self._browse_dir(self.custom_var),
        ).grid(row=2, column=2, pady=(8, 0))
        box.columnconfigure(1, weight=1)

        summary_panel = ttk.Frame(page, style="Panel.TFrame", padding=12)
        summary_panel.pack(fill="x", pady=10)
        ttk.Label(summary_panel, text="READY TO INSTALL", style="Section.TLabel").pack(anchor="w")
        self.install_summary = ttk.Label(
            summary_panel,
            text="",
            justify="left",
            style="Panel.TLabel",
        )
        self.install_summary.pack(anchor="w", pady=(6, 0))

        actions = ttk.Frame(page, style="App.TFrame")
        actions.pack(fill="x", before=collection, pady=(0, 8))
        self.build_button = ttk.Button(
            actions,
            text="BUILD & INSTALL MOD",
            style="Primary.TButton",
            command=self._build_mod,
        )
        self.build_button.pack(side="left")
        self.play_button = ttk.Button(
            actions,
            text="BUILD & PLAY IN DOLPHIN",
            style="Secondary.TButton",
            command=lambda: self._build_mod(play=True),
        )
        self.play_button.pack(side="left", padx=(8, 0))
        self.cancel_build_button = ttk.Button(
            actions, text="CANCEL BUILD", style="Secondary.TButton", command=self._cancel_build
        )
        self.cancel_build_button.pack(side="left", padx=(8, 0))
        self.cancel_build_button.state(["disabled"])
        self.progress = ttk.Progressbar(actions, maximum=100, length=420)
        self.progress.pack(side="left", fill="x", expand=True, padx=14)
        self.install_status = ttk.Label(
            page,
            text="",
            style="Muted.TLabel",
            wraplength=900,
            justify="left",
        )
        self.install_status.pack(anchor="w", before=collection, pady=(0, 8))
        ttk.Label(
            page,
            justify="left",
            wraplength=900,
            style="Muted.TLabel",
            text=(
                "Build & Play installs to Dolphin's Riivolution folder and starts the game with the mod enabled. "
                "Alternatively, right-click the game in Dolphin and choose 'Start with Riivolution Patches'."
            ),
        ).pack(anchor="w", pady=(16, 0))

    def _choose_path(self, key: str, *, is_file: bool, existing: str = "", parent=None, **options) -> str:
        try:
            initial = self.settings.picker_folder(key, existing, is_file)
        except OSError as err:
            messagebox.showerror("Choose folder", str(err), parent=parent or self)
            return ""
        dialog = filedialog.askopenfilename if is_file else filedialog.askdirectory
        chosen = dialog(parent=parent or self, initialdir=str(initial), **options)
        if chosen:
            try:
                self.settings.remember_folder(key, chosen, is_file, self.root_dir)
            except OSError as err:
                messagebox.showwarning("Remember folder", f"Could not save the selected folder: {err}", parent=parent or self)
        return chosen

    def _browse_dir(self, var: tk.StringVar) -> None:
        chosen = self._choose_path("install_folder", is_file=False, existing=var.get())
        if chosen:
            var.set(chosen)

    def _save_fit_names(self) -> None:
        try:
            self.garages.set_fit_names(self.fit_garage_names.get())
        except OSError as err:
            self.fit_garage_names.set(self.garages.fit_names())
            messagebox.showerror("Garage settings", str(err), parent=self)

    def _refresh_install_summary(self) -> None:
        if self.build_collection.get() == "onny":
            draft = "\nDevelopment draft will be used." if not OFFICIAL_RELEASE and (self.root_dir / presets.DRAFT_FILE).is_file() else ""
            self.install_summary.config(
                text="OnnY's Custom Vehicles will replace all 36 stock vehicle slots.\n"
                "Your saved creations are unchanged and are not included in this build.\n"
                "Preset names may be shortened to fit your game's language files." + draft
            )
            return
        active = [c for c in self.library.all() if c.enabled]
        if active:
            lines = [f"{self.garages.active_name}: {len(active)} creation(s) will be installed:"]
            lines += [f"   #{c.number} {c.name}  ->  replaces {VEHICLES[c.slot].name}" for c in active[:6]]
            if len(active) > 6:
                lines.append(f"   ... and {len(active) - 6} more.")
        else:
            lines = [f"{self.garages.active_name}: no creations are included yet."]
        if self.garages.fit_names():
            lines.append("Vehicle names may be shortened to fit your game.")
        self.install_summary.config(text="\n".join(lines))

    def _show_presets(self) -> None:
        try:
            items = presets.creations(None if OFFICIAL_RELEASE else self.root_dir)
        except (OSError, ValueError) as err:
            messagebox.showerror("Preset collection", str(err))
            return
        window = tk.Toplevel(self)
        window.title("OnnY's Custom Vehicles")
        window.transient(self)
        window.geometry("560x500")
        frame = ttk.Frame(window, style="App.TFrame", padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="ONNY'S CUSTOM VEHICLES", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame, text=(
                "Development collection: edit a garage copy. Names may be shortened to fit your game."
                if not OFFICIAL_RELEASE else
                "Use this collection instead of My Garage, or edit a copy. Names may be shortened to fit your game."
            ),
            style="Muted.TLabel", wraplength=500,
        ).pack(anchor="w", pady=(4, 8))
        buttons = ttk.Frame(frame, style="App.TFrame")
        buttons.pack(side="bottom", fill="x", pady=(8, 0))
        list_frame = ttk.Frame(frame, style="App.TFrame")
        list_frame.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(list_frame, orient="vertical")
        scroll.pack(side="right", fill="y")
        listing = tk.Listbox(
            list_frame, background=COLORS["panel"], foreground=COLORS["text"],
            selectbackground=COLORS["selected"], yscrollcommand=scroll.set,
        )
        listing.pack(fill="both", expand=True)
        scroll.config(command=listing.yview)
        for creation in items:
            listing.insert("end", f"{creation.name}  |  replaces {VEHICLES[creation.slot].name}")

        def edit_selected() -> None:
            selected = listing.curselection()
            if not selected or not self._require_stock():
                return
            creation = items[selected[0]]
            window.destroy()
            self._start_editing(creation)

        edit_copy = ttk.Button(buttons, text="EDIT GARAGE COPY", style="Secondary.TButton", command=edit_selected)
        edit_copy.pack(side="left")
        edit_copy.state(["disabled"])

        def selected(_event) -> None:
            edit_copy.state(["!disabled"] if listing.curselection() else ["disabled"])

        listing.bind("<<ListboxSelect>>", selected)

    def _export_presets(self) -> None:
        if OFFICIAL_RELEASE:
            return
        try:
            garage_items = self.library.all()
            used_stock = any(
                item.enabled and any(bar.field not in item.stats for bar in BARS)
                for item in garage_items
            )
            items = presets.from_garage(garage_items, self.stock)
            initial = self.settings.picker_folder("preset_export")
        except (OSError, ValueError) as err:
            messagebox.showerror("Export presets", str(err))
            return
        chosen = filedialog.asksaveasfilename(
            parent=self, title="Export OnnY's Custom Vehicles", initialdir=str(initial),
            initialfile="onny-presets.json", defaultextension=".json",
            filetypes=[("Preset collection", "*.json")],
        )
        if not chosen:
            return
        try:
            presets.write(Path(chosen), items)
        except (OSError, ValueError) as err:
            messagebox.showerror("Export presets", str(err))
            return
        try:
            self.settings.remember_folder("preset_export", chosen, True, self.root_dir)
        except OSError as err:
            messagebox.showwarning("Remember folder", f"Preset export succeeded, but its folder could not be saved: {err}")
        messagebox.showinfo(
            "Preset export",
            f"Exported all 36 presets to:\n{chosen}\n\n"
            + ("Unchanged performance values were taken from your imported game data.\n\n" if used_stock else "")
            + "To update a future release, replace the bundled onny-presets.json with this file and run the tests.",
        )

    def _install_targets(self) -> list[Path]:
        targets = []
        if self.use_riivolution.get():
            targets.append(self.folders.riivolution)
        if self.use_sd_sync.get():
            targets.append(self.folders.sd_sync)
        if self.use_custom.get() and self.custom_var.get().strip():
            targets.append(Path(self.custom_var.get().strip()))
        return targets

    def _cancel_build(self) -> None:
        if self._build_cancel and self._build_cancel.cancel():
            self.cancel_build_button.state(["disabled"])
            self.install_status.config(text="Cancelling build...")
        else:
            self.install_status.config(text="Finishing installation; it can no longer be cancelled.")

    def _dolphin_close_prompt(self) -> bool:
        window = tk.Toplevel(self)
        window.title("Close Dolphin")
        window.transient(self)
        window.resizable(False, False)
        window.configure(background=COLORS["background"])
        frame = ttk.Frame(window, style="App.TFrame", padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text="Dolphin is running. Please close all Dolphin windows before continuing.",
            style="App.TLabel", wraplength=380,
        ).pack(anchor="w")
        ttk.Label(
            frame, text="Exit cancels Build & Play; it will not close this app.",
            style="Muted.TLabel", wraplength=380,
        ).pack(anchor="w", pady=(6, 12))
        buttons = ttk.Frame(frame, style="App.TFrame")
        buttons.pack(fill="x")
        result = False

        def finish(continue_build: bool) -> None:
            nonlocal result
            result = continue_build
            window.destroy()

        ttk.Button(buttons, text="CONTINUE", style="Primary.TButton", command=lambda: finish(True)).pack(side="left")
        ttk.Button(buttons, text="EXIT", style="Secondary.TButton", command=lambda: finish(False)).pack(side="right")
        window.protocol("WM_DELETE_WINDOW", lambda: finish(False))
        window.grab_set()
        self.wait_window(window)
        return result

    def _ensure_dolphin_closed(self) -> bool:
        try:
            while dolphin.is_running():
                if not self._dolphin_close_prompt():
                    return False
        except OSError as err:
            messagebox.showerror("Dolphin check failed", f"Could not check whether Dolphin is running: {err}")
            return False
        return True

    def _build_mod(self, play: bool = False) -> None:
        if not self._require_stock():
            return
        collection = self.build_collection.get()
        if collection == "onny":
            try:
                creations = presets.creations(None if OFFICIAL_RELEASE else self.root_dir)
            except (OSError, ValueError) as err:
                messagebox.showerror("Preset collection", str(err))
                return
        elif collection == "garage":
            creations = self.library.all()
        else:
            messagebox.showerror("Vehicle collection", "Choose a valid vehicle collection.")
            return
        if slot_conflicts(creations):
            messagebox.showwarning("Conflict", "Two included creations replace the same vehicle. Fix that in My Garage first.")
            return
        fit_names = collection == "onny" or (collection == "garage" and self.fit_garage_names.get())
        targets = self._install_targets()
        if play and self.folders.riivolution not in targets:
            targets.insert(0, self.folders.riivolution)
        if not targets:
            messagebox.showwarning("Choose a folder", "Tick at least one place to install the mod.")
            return
        if play and not self._ensure_dolphin_closed():
            return
        self.settings.install_riivolution = self.use_riivolution.get()
        self.settings.install_sd_sync = self.use_sd_sync.get()
        self.settings.install_custom = self.use_custom.get()
        self.settings.output = self.custom_var.get()
        self.settings.build_collection = collection
        self.settings.save(self.root_dir)

        game = self.settings.game_id
        image = Path(self.settings.disc) if self.settings.disc else None
        tool = Path(self.settings.dolphintool) if self.settings.dolphintool else None
        exe = tool.with_name("Dolphin.exe") if tool else None
        if play and (image is None or not image.is_file() or tool is None or not tool.is_file()
                     or exe is None or not exe.is_file()):
            messagebox.showwarning(
                "Dolphin setup",
                "Choose a valid game image and DolphinTool.exe on the Setup page. "
                "Dolphin.exe must be in the same folder as DolphinTool.exe.",
            )
            return
        self.build_button.state(["disabled"])
        self.play_button.state(["disabled"])
        self.cancel_build_button.state(["!disabled"])
        cancel = export.BuildCancellation()
        self._build_cancel = cancel
        self.install_status.config(text="Building...")

        def progress(message: str, fraction: float) -> None:
            def update():
                self.progress.config(value=fraction * 100)
                self.install_status.config(text=message)
                if message.startswith("Finishing installation"):
                    self.cancel_build_button.state(["disabled"])
            self.events.put(update)

        def work():
            cancel.check()
            shortened = []
            build_creations = creations
            if fit_names:
                progress("Checking vehicle names...", 0)
                active = [creation for creation in creations if creation.enabled]
                build_creations, shortened = presets.fit_names(active, self.cache / game, game, cancel.check)
            if play:
                imported_game = disc.read_game_id(tool, image)
                if imported_game != game:
                    raise ValueError(
                        f"The selected game image is {imported_game}, but the imported data is {game}. "
                        "Re-import the game on the Setup page."
                    )
            result = export.install_mod(self.cache / game, game, build_creations, targets, progress, texture_dir(self.root_dir), cancel)
            if play:
                dolphin.launch_mod(exe, image, game, self.folders.riivolution, self.root_dir / "dolphin-launch.json")
            return result, shortened

        def done(result, error):
            self._build_cancel = None
            self.build_button.state(["!disabled"])
            self.play_button.state(["!disabled"])
            self.cancel_build_button.state(["disabled"])
            if isinstance(error, export.BuildCancelled):
                self.progress.config(value=0)
                self.install_status.config(text="Build cancelled. Existing installations were not changed.")
            elif error:
                self.install_status.config(text=f"Failed: {error}")
                messagebox.showerror("Build or launch failed" if play else "Build failed", str(error))
            else:
                self.progress.config(value=100)
                prefix = "Launched Dolphin. Installed into:\n" if play else "Done. Installed into:\n"
                targets_done, shortened = result
                names = "\nShortened vehicle names: " + ", ".join(shortened) if shortened else ""
                self.install_status.config(text=prefix + "\n".join(str(p) for p in targets_done) + names)

        self._run_in_background(work, done)

    # ---------- setup page ----------

    def _build_setup_page(self) -> None:
        page = self._new_page("setup")
        ttk.Label(page, text="GAME SETUP", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(
            page,
            wraplength=900,
            justify="left",
            style="Muted.TLabel",
            text=(
                "Import data from your own Mario Kart Wii backup. The app keeps a working copy on this PC; "
                "game data is not bundled with the app."
            ),
        ).pack(anchor="w", pady=(3, 12))
        form = ttk.LabelFrame(
            page,
            text="  GAME IMAGE AND DOLPHIN TOOL  ",
            padding=12,
            style="Panel.TLabelframe",
        )
        form.pack(fill="x")
        self.disc_var = tk.StringVar(value=self.settings.disc)
        self.tool_var = tk.StringVar(value=self.settings.dolphintool)
        self._importing = False
        ttk.Label(form, text="GAME IMAGE", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.disc_var, width=70).grid(row=0, column=1, padx=8)
        ttk.Button(form, text="BROWSE", style="Secondary.TButton", command=self._browse_disc).grid(row=0, column=2)
        ttk.Label(form, text="DOLPHINTOOL.EXE", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(form, textvariable=self.tool_var, width=70).grid(row=1, column=1, padx=8, pady=(8, 0))
        ttk.Button(form, text="BROWSE", style="Secondary.TButton", command=self._browse_tool).grid(
            row=1, column=2, pady=(8, 0)
        )
        form.columnconfigure(1, weight=1)
        search_row = ttk.Frame(page, style="App.TFrame")
        search_row.pack(fill="x", pady=(10, 0))
        ttk.Label(search_row, text="Or search a drive:", style="App.TLabel").pack(side="left")
        if os.name == "nt":
            mask = ctypes.windll.kernel32.GetLogicalDrives()
            drives = [f"{chr(65 + i)}:\\" for i in range(26) if mask & (1 << i)
                      and ctypes.windll.kernel32.GetDriveTypeW(f"{chr(65 + i)}:\\") in (2, 3)]
        else:
            drives = [Path.cwd().anchor]
        selected_drive = Path(self.settings.disc).anchor if self.settings.disc else Path.cwd().anchor
        self.search_drive_var = tk.StringVar(value=selected_drive if selected_drive in drives else (drives[0] if drives else ""))
        ttk.Combobox(search_row, textvariable=self.search_drive_var, values=drives, state="readonly", width=8).pack(side="left", padx=8)
        self.search_drive_button = ttk.Button(search_row, text="SEARCH DRIVE", style="Secondary.TButton", command=self._search_setup_drive)
        self.search_drive_button.pack(side="left")
        if not drives:
            self.search_drive_button.state(["disabled"])
        self.import_button = ttk.Button(
            page,
            text="IMPORT GAME DATA",
            style="Primary.TButton",
            command=self._import_game,
        )
        self.import_button.pack(anchor="w", pady=12)
        self.setup_status = ttk.Label(
            page,
            text="",
            style="Muted.TLabel",
            wraplength=900,
            justify="left",
        )
        self.setup_status.pack(anchor="w", pady=4)
        ttk.Label(
            page,
            wraplength=900,
            justify="left",
            style="Muted.TLabel",
            text="DolphinTool.exe comes with Dolphin (https://dolphin-emu.org). Put it anywhere and point to it here.",
        ).pack(anchor="w")
        if not self.settings.dolphintool:
            self._autodetect_tool(quiet=True)
        self.disc_var.trace_add("write", lambda *_: self._update_import_button())
        self.tool_var.trace_add("write", lambda *_: self._update_import_button())
        self._update_import_button()

    def _update_import_button(self) -> None:
        valid = (not self._importing and Path(self.disc_var.get().strip()).is_file()
                 and Path(self.tool_var.get().strip()).is_file())
        self.import_button.state(["!disabled"] if valid else ["disabled"])

    def _search_setup_drive(self) -> None:
        root = Path(self.search_drive_var.get())
        window = tk.Toplevel(self)
        window.title(f"Search {root}")
        window.transient(self)
        window.geometry("800x500")
        window.configure(background=COLORS["background"])
        cancelled = threading.Event()
        ttk.Label(window, text="Select a game image and/or DolphinTool, then choose USE SELECTED.",
                  style="Muted.TLabel").pack(anchor="w", padx=12, pady=10)
        body = ttk.Frame(window, style="App.TFrame")
        body.pack(fill="both", expand=True, padx=12)
        lists = {}
        for kind, title in (("image", "GAME IMAGES"), ("tool", "DOLPHIN TOOL")):
            section = ttk.Frame(body, style="App.TFrame")
            section.pack(side="left", fill="both", expand=True, padx=4)
            ttk.Label(section, text=title, style="Section.TLabel").pack(anchor="w")
            box = tk.Listbox(section, exportselection=False, background=COLORS["panel"],
                             foreground=COLORS["text"], selectbackground=COLORS["selected"])
            box.pack(fill="both", expand=True)
            lists[kind] = box
        status = ttk.Label(window, text="Searching likely locations first...", style="Muted.TLabel", wraplength=760)
        status.pack(anchor="w", padx=12, pady=6)
        actions = ttk.Frame(window, style="App.TFrame")
        actions.pack(fill="x", padx=12, pady=8)
        stop = ttk.Button(actions, text="STOP SEARCH", style="Secondary.TButton", command=cancelled.set)
        stop.pack(side="left")
        use = ttk.Button(actions, text="USE SELECTED", style="Primary.TButton")
        use.pack(side="right")
        use.state(["disabled"])

        def selection_changed(_event=None):
            use.state(["!disabled"] if any(box.curselection() for box in lists.values()) else ["disabled"])
        for box in lists.values():
            box.bind("<<ListboxSelect>>", selection_changed)

        def close():
            cancelled.set()
            window.destroy()
        window.protocol("WM_DELETE_WINDOW", close)

        def apply_selection():
            for kind, var in (("image", self.disc_var), ("tool", self.tool_var)):
                selected = lists[kind].curselection()
                if selected:
                    var.set(lists[kind].get(selected[0]))
            close()
        use.config(command=apply_selection)

        last_report = 0.0
        def found(kind, path):
            def update():
                if window.winfo_exists():
                    lists[kind].insert("end", str(path))
            self.events.put(update)
        def report(path):
            nonlocal last_report
            now = time.monotonic()
            if now - last_report >= 0.5:
                last_report = now
                self.events.put(lambda: status.config(text=f"Searching: {path}") if window.winfo_exists() else None)
        def done(skipped, error):
            if not window.winfo_exists():
                return
            stop.state(["disabled"])
            if error:
                status.config(text=f"Search failed: {error}")
            else:
                state = "Stopped" if cancelled.is_set() else "Finished"
                status.config(text=f"{state}. {skipped} folders could not be read. Select results to use.")
        self._run_in_background(lambda: disc.search_drive(root, cancelled, found, report), done)

    def _browse_disc(self) -> None:
        chosen = self._choose_path(
            "game_image", is_file=True, existing=self.disc_var.get(),
            title="Mario Kart Wii image",
            filetypes=[("Game images", "*.iso *.rvz *.wbfs *.wia *.gcz *.ciso"), ("All files", "*.*")],
        )
        if chosen:
            self.disc_var.set(chosen)

    def _browse_tool(self) -> None:
        chosen = self._choose_path(
            "dolphin_tool", is_file=True, existing=self.tool_var.get(), title="DolphinTool.exe",
            filetypes=[("DolphinTool", "DolphinTool.exe"), ("All files", "*.*")],
        )
        if chosen:
            self.tool_var.set(chosen)

    def _autodetect_tool(self, quiet: bool = False) -> None:
        here = [Path(__file__).resolve().parent.parent, Path.cwd()]
        found = disc.find_dolphintool(here)
        if found:
            self.tool_var.set(str(found))
        elif not quiet:
            messagebox.showinfo("Not found", "DolphinTool.exe was not found. Browse to it in your Dolphin folder.")

    def _refresh_setup(self) -> None:
        if self.stock is not None:
            self.setup_status.config(text=f"Game data ready ({self.settings.game_id}). You can create vehicles now.")
            self.header.itemconfigure(
                self.game_status,
                text=f"GAME DATA READY  |  {self.settings.game_id}",
                fill="#a7f5c2",
            )
        else:
            self.setup_status.config(text="No game data yet. Choose your game image and DolphinTool.exe, then import.")
            self.header.itemconfigure(
                self.game_status,
                text="SETUP REQUIRED",
                fill="#ffe08a",
            )

    def _import_game(self) -> None:
        image = Path(self.disc_var.get().strip())
        tool = Path(self.tool_var.get().strip())
        if not image.is_file():
            messagebox.showwarning("Game image", "Choose your Mario Kart Wii image file.")
            return
        if not tool.is_file():
            messagebox.showwarning("DolphinTool", "Choose DolphinTool.exe from your Dolphin folder.")
            return
        self.import_button.state(["disabled"])
        self._importing = True
        self.setup_status.config(text="Importing...")

        def done(game_id, error):
            self._importing = False
            self._update_import_button()
            if error:
                self.setup_status.config(text=f"Import failed: {error}")
                return
            self.settings.disc = str(image)
            self.settings.dolphintool = str(tool)
            self.settings.game_id = game_id
            self.settings.save(self.root_dir)
            self.folders = dolphin.find_folders(tool.with_name("Dolphin.exe"))
            self.riivolution_path_label.config(text=str(self.folders.riivolution))
            self.sd_sync_path_label.config(text=str(self.folders.sd_sync))
            self._load_stock()
            self._refresh_setup()
            self._refresh_garage()
            self.show_page("garage")

        self._run_in_background(lambda: disc.import_game(tool, image, self.cache), done)


def main(root_dir: Path | None = None) -> None:
    if os.name == "nt":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    GarageApp(root_dir).mainloop()
