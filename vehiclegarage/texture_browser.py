"""A responsive browser for community vehicle textures."""

import tempfile
import tkinter as tk
import urllib.parse
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from vehiclegarage import preview, textures
from vehiclegarage.settings import texture_dir
from vehiclegarage.vehicles import VEHICLES


class TextureBrowser(tk.Toplevel):
    def __init__(self, app, slot: int, apply):
        super().__init__(app)
        self.app = app
        self.slot = slot
        self.apply = apply
        self.cache = app.root_dir / "texture-cache"
        self.titles: list[str] = []
        self.visible: list[str] = []
        self.details: dict | None = None
        self.image = None
        self.title("Browse Vehicle Textures")
        self.transient(app)
        self.grab_set()
        self.geometry("900x600")
        self.minsize(760, 500)
        self.configure(background="#07152d")

        top = ttk.Frame(self, style="App.TFrame", padding=12)
        top.pack(fill="x")
        ttk.Label(top, text="BROWSE TEXTURES", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(
            top, text=f"Selected vehicle: {VEHICLES[slot].name}. Compatibility is checked when importing.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 8))
        search_row = ttk.Frame(top, style="App.TFrame")
        search_row.pack(fill="x")
        ttk.Label(search_row, text="Search", style="App.TLabel").pack(side="left")
        self.search = tk.StringVar()
        ttk.Entry(search_row, textvariable=self.search).pack(side="left", fill="x", expand=True, padx=8)
        self.only_vehicle = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            search_row, text="Match vehicle name", variable=self.only_vehicle, command=self._filter
        ).pack(side="left", padx=8)
        self.refresh_button = ttk.Button(search_row, text="REFRESH", style="Secondary.TButton", command=lambda: self._load(True))
        self.refresh_button.pack(side="right")
        self.search.trace_add("write", lambda *_: self._filter())

        body = ttk.Frame(self, style="App.TFrame", padding=(12, 0, 12, 8))
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body, style="App.TFrame")
        left.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(left, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self.listbox = tk.Listbox(
            left, background="#102444", foreground="#f7f6f8", selectbackground="#755700",
            selectforeground="#ffffff", highlightthickness=0, borderwidth=0,
            yscrollcommand=scrollbar.set, exportselection=False,
        )
        self.listbox.pack(fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)
        self.listbox.bind("<<ListboxSelect>>", self._selected)

        right = ttk.Frame(body, style="Panel.TFrame", padding=12, width=420)
        right.pack(side="right", fill="both", padx=(12, 0))
        right.pack_propagate(False)
        self.detail_title = ttk.Label(right, text="Select a texture", style="Section.TLabel", wraplength=390)
        self.detail_title.pack(anchor="w")
        self.author = ttk.Label(right, text="", style="Panel.TLabel", wraplength=390)
        self.author.pack(anchor="w", pady=(6, 8))
        self.preview_label = ttk.Label(right, text="No preview selected", style="Panel.TLabel", anchor="center")
        self.preview_label.pack(fill="both", expand=True)
        self.detail_status = ttk.Label(right, text="", style="Panel.TLabel", wraplength=390, justify="left")
        self.detail_status.pack(anchor="w", pady=6)
        links = ttk.Frame(right, style="Panel.TFrame")
        links.pack(fill="x")
        self.source_button = ttk.Button(links, text="OPEN WIKI PAGE", style="Secondary.TButton", command=self._open_page)
        self.source_button.pack(side="left")
        self.download_button = ttk.Button(links, text="OPEN DOWNLOAD", style="Secondary.TButton", command=self._open_download)
        self.download_button.pack(side="left", padx=6)

        bottom = ttk.Frame(self, style="App.TFrame", padding=(12, 0, 12, 12))
        bottom.pack(fill="x")
        self.import_button = ttk.Button(bottom, text="IMPORT SZS / ZIP", style="Primary.TButton", command=self._import_file)
        self.import_button.pack(side="left")
        self.direct_button = ttk.Button(bottom, text="DOWNLOAD & APPLY", style="Secondary.TButton", command=self._direct)
        self.direct_button.pack(side="left", padx=8)
        ttk.Button(bottom, text="CLOSE", style="Secondary.TButton", command=self.destroy).pack(side="right")
        self.status = ttk.Label(bottom, text="Loading catalogue...", style="Muted.TLabel")
        self.status.pack(side="left", padx=8)
        self._set_detail_buttons(False)
        self._load(False)

    def _alive(self) -> bool:
        return bool(self.winfo_exists())

    def _load(self, refresh: bool) -> None:
        self.refresh_button.state(["disabled"])
        self.status.config(text="Loading catalogue...")

        def done(titles, error):
            if not self._alive():
                return
            self.refresh_button.state(["!disabled"])
            if error:
                self.status.config(text="Catalogue unavailable")
                messagebox.showerror("Texture catalogue", str(error), parent=self)
                return
            self.titles = titles
            self._filter()

        self.app._run_in_background(lambda: textures.catalogue(self.cache, refresh), done)

    def _filter(self) -> None:
        query = self.search.get().strip().casefold()
        vehicle = VEHICLES[self.slot].name.casefold()
        self.visible = [
            title for title in self.titles
            if query in title.casefold() and (not self.only_vehicle.get() or vehicle in title.casefold())
        ]
        self.listbox.delete(0, "end")
        for title in self.visible:
            self.listbox.insert("end", title)
        self.details = None
        self.image = None
        self.detail_title.config(text="Select a texture")
        self.author.config(text="")
        self.preview_label.config(image="", text="No preview selected")
        self.detail_status.config(text="")
        self._set_detail_buttons(False)
        self.status.config(text=f"{len(self.visible)} textures")

    def _set_detail_buttons(self, enabled: bool) -> None:
        state = ["!disabled"] if enabled else ["disabled"]
        self.source_button.state(state)
        self.download_button.state(state)
        self.direct_button.state(state)

    def _selected(self, _event=None) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        title = self.visible[selection[0]]
        self.details = None
        self._set_detail_buttons(False)
        self.detail_title.config(text=title)
        self.author.config(text="")
        self.preview_label.config(image="", text="Loading preview...")
        self.detail_status.config(text="Loading source details...")

        def work():
            details = textures.page_details(title, self.cache)
            image_data = None
            image_error = None
            if details.get("preview"):
                try:
                    image_data = textures.preview_bytes(details["preview"], self.cache)
                    if not image_data.startswith((b"\x89PNG", b"GIF8")):
                        image_data = preview.decode(image_data)
                except (OSError, ValueError) as err:
                    image_error = str(err)
            return details, image_data, image_error

        def done(result, error):
            if not self._alive() or self.detail_title.cget("text") != title:
                return
            if error:
                self.preview_label.config(text="Preview unavailable")
                self.detail_status.config(text=f"Could not load details: {error}")
                return
            details, image_data, image_error = result
            self.details = details
            self.author.config(text=f"Creator: {details.get('author') or 'Unknown'}")
            self.source_button.state(["!disabled"])
            if details.get("downloads"):
                self.download_button.state(["!disabled"])
                self.direct_button.state(["!disabled"])
            if image_data:
                try:
                    self.image = tk.PhotoImage(data=image_data)
                    self.preview_label.config(image=self.image, text="")
                except tk.TclError as err:
                    image_error = str(err)
            if not image_data or image_error:
                self.preview_label.config(image="", text="No preview available")
            self.detail_status.config(
                text=(f"Preview unavailable: {image_error}" if image_error else
                      "Download the pack, then import its SZS or ZIP file.")
            )

        self.app._run_in_background(work, done)

    def _open_url(self, url: str) -> None:
        if not webbrowser.open(url):
            messagebox.showerror("Open browser", f"Could not open {url}", parent=self)

    def _open_page(self) -> None:
        if self.details:
            self._open_url(self.details["url"])

    def _open_download(self) -> None:
        if self.details and self.details["downloads"]:
            self._open_url(self.details["downloads"][0])

    def _import_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self, title="Choose a texture pack",
            filetypes=[("Vehicle texture packs", "*.szs *.zip"), ("All files", "*.*")],
        )
        if path:
            details = self.details
            self._import(Path(path), details["title"] if details else "", details["url"] if details else "")

    def _import(self, path: Path, name: str, source: str) -> None:
        self.status.config(text="Checking texture files...")
        self.import_button.state(["disabled"])
        self.direct_button.state(["disabled"])

        def done(pack, error):
            if not self._alive():
                return
            if error:
                self.import_button.state(["!disabled"])
                if self.details and self.details.get("downloads"):
                    self.direct_button.state(["!disabled"])
                self.status.config(text="Import failed")
                messagebox.showerror("Texture import", str(error), parent=self)
                return
            self.apply(pack)
            messagebox.showinfo(
                "Texture ready",
                f"Added {len(pack.files)} race archive(s). Only the characters and modes included in "
                "this pack will change. Save the vehicle, then Build & Install to use it.",
                parent=self,
            )
            self.destroy()

        self.app._run_in_background(lambda: textures.import_pack(path, self.slot, texture_dir(self.app.root_dir), name, source), done)

    def _direct(self) -> None:
        if not self.details or not self.details["downloads"]:
            return
        details = self.details
        url = details["downloads"][0]
        filename = Path(urllib.parse.unquote(urllib.parse.urlsplit(url).path)).name
        if not filename.lower().endswith((".szs", ".zip")):
            messagebox.showinfo(
                "Manual download required",
                "This link is not a direct SZS or ZIP file. Open Download, save the file, then choose Import SZS / ZIP.",
                parent=self,
            )
            return
        self.status.config(text="Downloading texture...")
        self.import_button.state(["disabled"])
        self.direct_button.state(["disabled"])

        def work():
            data = textures.direct_download(url)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / filename
                path.write_bytes(data)
                return textures.import_pack(path, self.slot, texture_dir(self.app.root_dir), details["title"], details["url"])

        def done(pack, error):
            if not self._alive():
                return
            if error:
                self.import_button.state(["!disabled"])
                if self.details and self.details.get("downloads"):
                    self.direct_button.state(["!disabled"])
                self.status.config(text="Download failed")
                messagebox.showerror("Texture download", f"{error}\n\nTry Open Download and import the saved file.", parent=self)
                return
            self.apply(pack)
            messagebox.showinfo(
                "Texture ready", f"Added {len(pack.files)} race archive(s). Save the vehicle, then Build & Install.",
                parent=self,
            )
            self.destroy()

        self.app._run_in_background(work, done)
