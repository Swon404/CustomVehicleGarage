"""The Custom Vehicle Garage desktop app."""

import ctypes
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from vehiclegarage import bmg, disc, dolphin, export, unlock, updater
from vehiclegarage.creations import Creation, Library, slot_conflicts
from vehiclegarage.kartparam import KartParam
from vehiclegarage.settings import Settings, cache_dir, data_dir, library_dir, texture_dir
from vehiclegarage.stats import ADVANCED_FIELDS, BARS
from vehiclegarage.texture_browser import TextureBrowser
from vehiclegarage.textures import TexturePack
from vehiclegarage.vehicles import VEHICLES, WEIGHT_CLASSES
from vehiclegarage.version import VERSION

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


class GarageApp(tk.Tk):
    def __init__(self, root_dir: Path | None = None):
        super().__init__()
        self.title("Custom Vehicle Garage")
        self.geometry("1100x760")
        self.minsize(900, 640)
        self.configure(background=COLORS["background"])
        self._configure_styles()
        assets = Path(__file__).resolve().parent / "assets"
        self.app_icon = tk.PhotoImage(file=str(assets / "garage.png"))
        self.iconphoto(True, self.app_icon)
        self.header_icon = self.app_icon.subsample(5, 5)
        self.header_art = tk.PhotoImage(file=str(assets / "racing-banner.png"))
        self.root_dir = root_dir or data_dir()
        self.settings = Settings.load(self.root_dir)
        self.library = Library(library_dir(self.root_dir))
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
            84, 58, text="Build your ride. Choose its stock vehicle. Install it to Dolphin.",
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
            text=f"UPDATE  |  v{VERSION}",
            style="Nav.TButton",
            command=self._check_update,
        )
        self.update_button.pack(side="right", padx=(0, 7))

        self.page_host = ttk.Frame(self, style="App.TFrame", padding=(14, 4, 14, 14))
        self.page_host.pack(fill="both", expand=True)
        self.pages: dict[str, ttk.Frame] = {}

        footer = tk.Frame(self, height=24, background=COLORS["footer"])
        footer.pack(fill="x", side="bottom")
        tk.Frame(footer, height=3, background=COLORS["purple"]).pack(fill="x")
        tk.Label(
            footer,
            text="CUSTOM VEHICLE GARAGE",
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
        self.update_button.state(["disabled"])

        def checked(release, error):
            if error:
                self.update_button.state(["!disabled"])
                messagebox.showerror("Update check failed", str(error))
            elif release is None:
                self.update_button.state(["!disabled"])
                messagebox.showinfo("Up to date", f"Version {VERSION} is the latest available.")
            elif not messagebox.askyesno(
                "Update available",
                f"Version {release.version} is available (you have {VERSION}).\n\n"
                "Install it and restart now? Unsaved edits will be lost.",
            ):
                self.update_button.state(["!disabled"])
            else:
                def installed(_result, install_error):
                    if install_error:
                        self.update_button.state(["!disabled"])
                        messagebox.showerror("Update failed", str(install_error))
                    else:
                        self.destroy()

                self._run_in_background(lambda: updater.install_release(release), installed)

        self._run_in_background(updater.latest_release, checked)

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
        self.tree = ttk.Treeview(panel, columns=columns, show="headings", selectmode="browse")
        for col, text, width in (
            ("number", "NO.", 70),
            ("name", "CREATION", 250),
            ("vehicle", "REPLACES STOCK VEHICLE", 260),
            ("class", "CLASS", 100),
            ("on", "IN MOD", 90),
        ):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("conflict", foreground=COLORS["danger"])
        self.tree.tag_configure("off", foreground="#85838b")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        actions = ttk.Frame(panel, style="Panel.TFrame")
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="EDIT SELECTED", style="Secondary.TButton", command=self._edit_selected).pack(side="left")
        ttk.Button(actions, text="INCLUDE / EXCLUDE", style="Secondary.TButton", command=self._toggle_selected).pack(side="left", padx=6)
        ttk.Button(actions, text="DELETE", style="Secondary.TButton", command=self._delete_selected).pack(side="left")
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
        for index, vehicle in enumerate(visible):
            row, column = divmod(index, 3)
            selected = vehicle.slot == self.selected_slot
            button = tk.Button(
                self.vehicle_grid,
                text=f"{vehicle.name}\n{vehicle.kind.upper()}  /  {vehicle.weight_label.upper()}",
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
                anchor="w",
                font=("Segoe UI", 10, "bold"),
                cursor="hand2",
            )
            button.grid(row=row, column=column, sticky="ew", padx=5, pady=5)
            self.visible_slots.append(vehicle.slot)

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
        self.selected_slot = slot
        self._fill_vehicles()

    def _continue_vehicle_selection(self) -> None:
        if self.selected_slot is not None:
            self._start_editing(self.editing, slot=self.selected_slot)

    # ---------- editor page ----------

    def _build_editor_page(self) -> None:
        page = self._new_page("editor")
        actions = ttk.Frame(page, style="App.TFrame")
        actions.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(actions, text="< BACK TO GARAGE", style="Secondary.TButton", command=self._cancel_editing).pack(side="left")
        ttk.Button(actions, text="RESET STATS", style="Secondary.TButton", command=self._reset_to_stock).pack(side="left", padx=8)
        ttk.Button(actions, text="SAVE VEHICLE", style="Primary.TButton", command=self._save_creation).pack(side="right")

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
        ttk.Label(identity_left, text="IN-GAME NAME", style="Section.TLabel").pack(anchor="w")
        name_row = ttk.Frame(identity_left, style="Panel.TFrame")
        name_row.pack(anchor="w", pady=(4, 0))
        self.name_var = tk.StringVar()
        name_validation = self.register(bmg.vehicle_name_fits_ui_limit)
        self.name_entry = ttk.Entry(
            name_row,
            textvariable=self.name_var,
            width=28,
            validate="key",
            validatecommand=(name_validation, "%P"),
        )
        self.name_entry.pack(side="left")
        self.name_counter = ttk.Label(name_row, text=f"0 / {bmg.MAX_VEHICLE_NAME_CODE_UNITS}", style="Panel.TLabel")
        self.name_counter.pack(side="left", padx=8)
        self.name_var.trace_add("write", lambda *_: self._update_name_counter())
        texture_row = ttk.Frame(identity_left, style="Panel.TFrame")
        texture_row.pack(anchor="w", pady=(8, 0))
        ttk.Button(texture_row, text="BROWSE TEXTURES", style="Secondary.TButton", command=self._browse_textures).pack(side="left")
        ttk.Button(texture_row, text="CLEAR", style="Secondary.TButton", command=self._clear_texture).pack(side="left", padx=6)
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
        ttk.Button(
            identity_right,
            text="CHANGE STOCK VEHICLE",
            style="Secondary.TButton",
            command=self._change_stock_vehicle,
        ).pack(anchor="e", pady=(8, 0))

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
        self._syncing_bar = False
        for row, bar in enumerate(BARS):
            ttk.Label(bars, text=bar.label.upper(), width=15, style="Panel.TLabel").grid(
                row=row,
                column=0,
                sticky="w",
                pady=3,
            )
            var = tk.DoubleVar(value=50.0)
            self.bar_vars[bar.key] = var
            ttk.Scale(
                bars,
                from_=0,
                to=100,
                variable=var,
                length=310,
                command=lambda _v, b=bar: self._bar_moved(b),
            ).grid(row=row, column=1, padx=10, pady=3, sticky="ew")
            value_var = tk.StringVar()
            self.bar_value_vars[bar.key] = value_var
            entry = ttk.Entry(bars, textvariable=value_var, width=13)
            entry.grid(row=row, column=2, padx=4, pady=3)
            entry.bind("<Return>", lambda _e, b=bar: self._numeric_bar_edited(b))
            entry.bind("<FocusOut>", lambda _e, b=bar: self._numeric_bar_edited(b))
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
        ttk.Label(
            content,
            text=(
                "The slider is the normal range; type an exact value to go beyond it. "
                "Use the stock value as a reference when setting 2x, 3x, or 4x."
            ),
            style="Muted.TLabel",
            wraplength=900,
        ).pack(anchor="w", pady=(0, 8))

        self.advanced_open = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            content,
            text="SHOW ADVANCED GAME VALUES",
            variable=self.advanced_open,
            command=self._toggle_advanced,
        ).pack(anchor="w")
        self.advanced_frame = ttk.LabelFrame(
            content,
            text="  ADVANCED STATS  ",
            padding=8,
            style="Panel.TLabelframe",
        )
        self.advanced_vars: dict[str, tk.StringVar] = {}
        for i, (field, label, _hint) in enumerate(ADVANCED_FIELDS):
            var = tk.StringVar()
            self.advanced_vars[field] = var
            row, column = divmod(i, 2)
            ttk.Label(self.advanced_frame, text=label, width=27, style="Panel.TLabel").grid(
                row=row,
                column=column * 2,
                sticky="w",
                pady=2,
            )
            ttk.Entry(self.advanced_frame, textvariable=var, width=12).grid(
                row=row,
                column=column * 2 + 1,
                padx=(2, 18),
                pady=2,
            )

    def _toggle_advanced(self) -> None:
        if self.advanced_open.get():
            self.advanced_frame.pack(fill="x", pady=6)
        else:
            self.advanced_frame.pack_forget()

    def _update_name_counter(self) -> None:
        units = len(self.name_var.get().encode("utf-16-be", errors="surrogatepass")) // 2
        self.name_counter.config(text=f"{units} / {bmg.MAX_VEHICLE_NAME_CODE_UNITS}")

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

    def _refresh_texture_label(self) -> None:
        if self.edit_texture:
            self.texture_label.config(
                text=f"Texture: {self.edit_texture.name} ({len(self.edit_texture.files)} race files). "
                     "The in-game selection preview remains stock."
            )
        else:
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
            self.advanced_vars[field].set(f"{value:.4g}")

    def _set_bar_value(self, bar, value, slot: int) -> None:
        self._syncing_bar = True
        self.bar_vars[bar.key].set(bar.to_percent(float(value)))
        self.bar_value_vars[bar.key].set(str(value))
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
        self.bar_value_vars[bar.key].set(str(value))
        stock = self._stock_value(slot, bar.field)
        self.bar_stock_labels[bar.key].config(text=f"Stock: {stock:g}")

    def _numeric_bar_edited(self, bar) -> None:
        try:
            value = bar.parse_value(self.bar_value_vars[bar.key].get().strip())
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
        self.number_label.config(text=f"#{creation.number}" if creation else f"#{self.library.next_number()} (new)")
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
            value = bar.parse_value(self.bar_value_vars[bar.key].get().strip())
            stock = self._stock_value(slot, bar.field)
            tolerance = (bar.high - bar.low) / 200
            if abs(value - stock) > tolerance:
                stats[bar.field] = value
        for field, label, _hint in ADVANCED_FIELDS:
            text = self.advanced_vars[field].get().strip()
            try:
                value = float(text)
            except ValueError:
                raise ValueError(f"{label} must be a number, got '{text}'") from None
            stock = self._stock_value(slot, field)
            if abs(value - stock) > max(abs(stock) * 1e-3, 1e-6):
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
            return
        if not bmg.vehicle_name_fits_ui_limit(name):
            messagebox.showwarning(
                "Name too long",
                f"Vehicle names are limited to {bmg.MAX_VEHICLE_NAME_CODE_UNITS} UTF-16 characters to fit in-game.",
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
        page = self._new_page("install")
        ttk.Label(page, text="BUILD & INSTALL", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(
            page,
            text="Review your vehicles and choose where the mod should go.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(3, 12))

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
        actions.pack(fill="x")
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
        self.unlock_button = ttk.Button(
            page,
            text="SET UP CHARACTER & VEHICLE UNLOCK",
            style="Secondary.TButton",
            command=self._setup_unlock,
        )
        self.unlock_button.pack(anchor="w", pady=(8, 0))
        self.install_status = ttk.Label(
            page,
            text="",
            style="Muted.TLabel",
            wraplength=900,
            justify="left",
        )
        self.install_status.pack(anchor="w", pady=(8, 0))
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

    def _setup_unlock(self) -> None:
        if not self._require_stock():
            return
        game = self.settings.game_id
        tool = Path(self.settings.dolphintool) if self.settings.dolphintool else None
        image = Path(self.settings.disc) if self.settings.disc else None
        exe = tool.with_name("Dolphin.exe") if tool else None
        if tool is None or not tool.is_file() or image is None or not image.is_file() or exe is None or not exe.is_file():
            messagebox.showwarning("Dolphin setup", "Choose a valid game image and DolphinTool.exe on the Setup page.")
            return
        try:
            disc.validate_game_id(game)
        except ValueError as err:
            messagebox.showerror("Unsupported game", str(err))
            return
        folders = dolphin.find_folders(exe)
        if not messagebox.askyesno(
            "Set up License Unlock",
            f"Close Dolphin and back up your Mario Kart Wii save first.\n\n"
            f"This adds Wiimm's region-specific Gecko code to Dolphin for {game} and enables cheats "
            "for this game. Other enabled cheats for this game may also run.\n\n"
            "Activating the code in-game and saving makes the unlock permanent. "
            "The code unlocks one licence's characters, vehicles and courses, not trophies.\n\n"
            f"Dolphin user folder: {folders.user_dir}\n\nContinue?",
        ):
            return
        self.unlock_button.state(["disabled"])
        self.install_status.config(text="Setting up License Unlock...")

        def work():
            actual_game = disc.read_game_id(tool, image)
            if actual_game != game:
                raise ValueError(f"The selected image is {actual_game}, but the imported data is {game}. Re-import the game.")
            code = unlock.fetch_code(game)
            return unlock.install(folders.user_dir, game, code)

        def done(result, error):
            self.unlock_button.state(["!disabled"])
            if error:
                self.install_status.config(text=f"License Unlock setup failed: {error}")
                messagebox.showerror("License Unlock setup failed", str(error))
                return
            target, backup = result
            self.install_status.config(text=f"License Unlock configured for {game}.")
            backup_text = f"\n\nPrevious game settings backup: {backup}" if backup else ""
            messagebox.showinfo(
                "License Unlock ready",
                f"Configured {target}.{backup_text}\n\n"
                "In Dolphin, start the game. At the licence selection screen, hold PLUS, MINUS, 1 and B "
                "on controller 1, then press the D-pad direction of the licence you want. "
                "The code's original instructions describe a Wii Remote rotated 45 degrees counterclockwise.\n\n"
                "A sound speed-up indicates success. Complete a race or change a Mii to save permanently. "
                "Trophies are not changed.\n\n"
                f"Instructions: {unlock.SOURCE}",
            )

        self._run_in_background(work, done)

    def _browse_dir(self, var: tk.StringVar) -> None:
        chosen = filedialog.askdirectory(initialdir=var.get() or None)
        if chosen:
            var.set(chosen)

    def _refresh_install_summary(self) -> None:
        active = [c for c in self.library.all() if c.enabled]
        if active:
            lines = [f"{len(active)} creation(s) will be installed:"]
            lines += [f"   #{c.number} {c.name}  ->  replaces {VEHICLES[c.slot].name}" for c in active]
        else:
            lines = ["No creations are included yet. Add a vehicle in My Garage before installing."]
        self.install_summary.config(text="\n".join(lines))

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

    def _build_mod(self, play: bool = False) -> None:
        if not self._require_stock():
            return
        creations = self.library.all()
        if slot_conflicts(creations):
            messagebox.showwarning("Conflict", "Two included creations replace the same vehicle. Fix that in My Garage first.")
            return
        targets = self._install_targets()
        if play and self.folders.riivolution not in targets:
            targets.insert(0, self.folders.riivolution)
        if not targets:
            messagebox.showwarning("Choose a folder", "Tick at least one place to install the mod.")
            return
        self.settings.install_riivolution = self.use_riivolution.get()
        self.settings.install_sd_sync = self.use_sd_sync.get()
        self.settings.install_custom = self.use_custom.get()
        self.settings.output = self.custom_var.get()
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
            if play:
                imported_game = disc.read_game_id(tool, image)
                if imported_game != game:
                    raise ValueError(
                        f"The selected game image is {imported_game}, but the imported data is {game}. "
                        "Re-import the game on the Setup page."
                    )
            result = export.install_mod(self.cache / game, game, creations, targets, progress, texture_dir(self.root_dir), cancel)
            if play:
                dolphin.launch_mod(exe, image, game, self.folders.riivolution, self.root_dir / "dolphin-launch.json")
            return result

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
                self.install_status.config(text=prefix + "\n".join(str(p) for p in result))

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
        ttk.Label(form, text="GAME IMAGE", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.disc_var, width=70).grid(row=0, column=1, padx=8)
        ttk.Button(form, text="BROWSE", style="Secondary.TButton", command=self._browse_disc).grid(row=0, column=2)
        ttk.Label(form, text="DOLPHINTOOL.EXE", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(form, textvariable=self.tool_var, width=70).grid(row=1, column=1, padx=8, pady=(8, 0))
        ttk.Button(form, text="BROWSE", style="Secondary.TButton", command=self._browse_tool).grid(
            row=1, column=2, pady=(8, 0)
        )
        ttk.Button(form, text="FIND", style="Secondary.TButton", command=self._autodetect_tool).grid(
            row=1, column=3, padx=6, pady=(8, 0)
        )
        form.columnconfigure(1, weight=1)
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

    def _browse_disc(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Mario Kart Wii image",
            filetypes=[("Game images", "*.iso *.rvz *.wbfs *.wia *.gcz *.ciso"), ("All files", "*.*")],
        )
        if chosen:
            self.disc_var.set(chosen)

    def _browse_tool(self) -> None:
        chosen = filedialog.askopenfilename(title="DolphinTool.exe", filetypes=[("DolphinTool", "DolphinTool.exe"), ("All files", "*.*")])
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
        self.setup_status.config(text="Importing...")

        def done(game_id, error):
            self.import_button.state(["!disabled"])
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
