"""Discover community textures and safely prepare vehicle archive replacements."""

import hashlib
import json
import re
import struct
import time
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath

from vehiclegarage import u8, yaz0

WIKI = "https://mkwiiki.org"
API = WIKI + "/w/api.php"
USER_AGENT = "CustomVehicleGarage/1.0 (vehicle texture browser)"
MAX_DOWNLOAD = 32 * 1024 * 1024
MAX_UNPACKED = 32 * 1024 * 1024
MAX_PACK = 128 * 1024 * 1024
MAX_ENTRIES = 1000
CATALOGUE_AGE = 7 * 24 * 60 * 60

# These are the game's Race/Kart filenames in kartParam slot order.
VEHICLE_PREFIXES = (
    "sdf_kart", "mdf_kart", "ldf_kart", "sa_kart", "ma_kart", "la_kart",
    "sb_kart", "mb_kart", "lb_kart", "sc_kart", "mc_kart", "lc_kart",
    "sd_kart", "md_kart", "ld_kart", "se_kart", "me_kart", "le_kart",
    "sdf_bike", "mdf_bike", "ldf_bike", "sa_bike", "ma_bike", "la_bike",
    "sb_bike", "mb_bike", "lb_bike", "sc_bike", "mc_bike", "lc_bike",
    "sd_bike", "md_bike", "ld_bike", "se_bike", "me_bike", "le_bike",
)
CHARACTERS = (
    frozenset(("bds", "blg", "bmr", "bpc", "ka", "kk", "ko", "nk",
               "sa_mii_f", "sa_mii_m", "sb_mii_f", "sb_mii_m")),
    frozenset(("ca", "dd", "ds", "jr", "lg", "mr", "pc", "ys",
               "ma_mii_f", "ma_mii_m", "mb_mii_f", "mb_mii_m")),
    frozenset(("bk", "dk", "fk", "kp", "kt", "rs", "wl", "wr",
               "la_mii_f", "la_mii_m", "lb_mii_f", "lb_mii_m")),
)


@dataclass(frozen=True)
class TexturePack:
    name: str
    slot: int
    files: dict[str, str]
    source: str = ""

    def to_json(self) -> dict:
        return {"name": self.name, "slot": self.slot, "files": self.files, "source": self.source}

    @classmethod
    def from_json(cls, data: dict) -> "TexturePack":
        pack = cls(data["name"], data["slot"], data["files"], data.get("source", ""))
        if not isinstance(pack.name, str) or not isinstance(pack.source, str):
            raise ValueError("invalid texture pack description")
        if not isinstance(pack.slot, int) or not 0 <= pack.slot < len(VEHICLE_PREFIXES):
            raise ValueError("invalid texture pack vehicle slot")
        if not isinstance(pack.files, dict) or not pack.files:
            raise ValueError("texture pack contains no files")
        for name, digest in pack.files.items():
            if not isinstance(name, str) or not matches_slot(name, pack.slot):
                raise ValueError(f"invalid texture filename: {name}")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError(f"invalid texture file checksum: {name}")
        return pack


def matches_slot(filename: str, slot: int) -> bool:
    if not 0 <= slot < len(VEHICLE_PREFIXES):
        return False
    prefix = VEHICLE_PREFIXES[slot] + "-"
    if not filename.startswith(prefix) or not filename.endswith(".szs"):
        return False
    character = filename[len(prefix):-4]
    if character.endswith("_4"):
        character = character[:-2]
    return character in CHARACTERS[slot % 3]


def _validate_szs(data: bytes, filename: str) -> None:
    if len(data) < 16 or len(data) > MAX_DOWNLOAD or data[:4] != b"Yaz0":
        raise ValueError(f"{filename}: expected a valid Yaz0-compressed SZS archive")
    size = int.from_bytes(data[4:8], "big")
    if not 0 < size <= MAX_UNPACKED:
        raise ValueError(f"{filename}: uncompressed archive is too large or empty")
    try:
        raw = yaz0.decompress(data)
        if len(raw) < 32 or raw[:4] != u8.MAGIC:
            raise ValueError("not a U8 archive")
        root = int.from_bytes(raw[4:8], "big")
        if root < 16 or root + 12 > len(raw) or raw[root] != 1:
            raise ValueError("invalid U8 root")
        count = int.from_bytes(raw[root + 8:root + 12], "big")
        if count < 1 or count > 10000 or root + count * 12 > len(raw):
            raise ValueError("invalid U8 file table")
        files = u8.find_files(raw)
        if any(offset < 0 or length < 0 or offset + length > len(raw) for offset, length in files.values()):
            raise ValueError("file extends outside archive")
        if not any(path.lower().endswith(".brres") and length >= 4 and raw[offset:offset + 4] == b"bres"
                   for path, (offset, length) in files.items()):
            raise ValueError("no valid BRRES model found")
    except (ValueError, IndexError, KeyError, struct.error, UnicodeError) as err:
        raise ValueError(f"{filename}: invalid vehicle archive ({err})") from err


def import_pack(path: Path, slot: int, storage: Path, name: str = "", source: str = "") -> TexturePack:
    """Import only correctly named race archives; do not extract arbitrary ZIP paths."""
    if not 0 <= slot < len(VEHICLE_PREFIXES):
        raise ValueError("Choose a valid vehicle first")
    if path.stat().st_size > MAX_PACK:
        raise ValueError("Texture download is too large")
    items: dict[str, bytes] = {}
    if path.suffix.lower() == ".szs":
        if matches_slot(path.name, slot):
            items[path.name] = path.read_bytes()
    elif path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                if len(entries) > MAX_ENTRIES:
                    raise ValueError("ZIP contains too many files")
                total = 0
                for entry in entries:
                    parts = PurePosixPath(entry.filename.replace("\\", "/"))
                    if parts.is_absolute() or ".." in parts.parts or ":" in entry.filename:
                        raise ValueError("ZIP contains an unsafe path")
                    filename = parts.name
                    if entry.is_dir() or not matches_slot(filename, slot):
                        continue
                    if filename in items:
                        raise ValueError(f"ZIP contains more than one {filename}")
                    if entry.file_size > MAX_DOWNLOAD:
                        raise ValueError(f"{filename} is too large")
                    total += entry.file_size
                    if total > MAX_PACK:
                        raise ValueError("Texture files are too large")
                    items[filename] = archive.read(entry)
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as err:
            raise ValueError(f"Cannot read texture ZIP: {err}") from err
    else:
        raise ValueError("Choose an SZS or ZIP file. Other archive formats must be extracted first.")
    if not items:
        raise ValueError(
            f"No matching {VEHICLE_PREFIXES[slot]}-<character>.szs files found for this vehicle. "
            "The pack may be for a different vehicle or use a different format."
        )
    for filename, data in items.items():
        _validate_szs(data, filename)
    storage.mkdir(parents=True, exist_ok=True)
    files = {}
    for filename, data in sorted(items.items()):
        digest = hashlib.sha256(data).hexdigest()
        destination = storage / (digest + ".szs")
        if not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            destination.write_bytes(data)
        files[filename] = digest
    return TexturePack(name or path.stem, slot, files, source)


def texture_outputs(pack: TexturePack, slot: int, storage: Path) -> list[tuple[str, bytes]]:
    pack = TexturePack.from_json(pack.to_json())
    if pack.slot != slot:
        raise ValueError("The selected texture belongs to a different vehicle slot")
    result = []
    for filename, digest in sorted(pack.files.items()):
        path = storage / (digest + ".szs")
        if not path.is_file():
            raise ValueError(f"Texture file is missing: {filename}. Import the pack again.")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"Texture file failed its checksum: {filename}")
        _validate_szs(data, filename)
        result.append(("Race/Kart/" + filename, data))
    return result


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, hosts: frozenset[str]):
        self.hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname not in self.hosts:
            raise ValueError("Download redirected to an unsupported host")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _get(url: str, limit: int = MAX_DOWNLOAD, hosts: frozenset[str] = frozenset(("mkwiiki.org",))) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.password:
        raise ValueError("Unsupported download host")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    opener = urllib.request.build_opener(_SafeRedirect(hosts))
    with opener.open(request, timeout=20) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Download exceeds the allowed size")
    return data


def _api(params: dict) -> dict:
    query = urllib.parse.urlencode({"format": "json", **params})
    result = json.loads(_get(API + "?" + query, 8 * 1024 * 1024))
    if "error" in result:
        raise ValueError(result["error"].get("info", "Wiki API error"))
    return result


def catalogue(cache: Path, refresh: bool = False) -> list[str]:
    path = cache / "catalogue.json"
    if not refresh and path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list) and all(isinstance(item, str) for item in data):
            return data
        raise ValueError("Cached texture catalogue is invalid; refresh it.")
    titles = []
    continuation = {}
    while True:
        response = _api({
            "action": "query", "list": "categorymembers",
            "cmtitle": "Category:Vehicle/Texture", "cmlimit": 500, "cmtype": "page",
            **continuation,
        })
        titles.extend(item["title"] for item in response["query"]["categorymembers"])
        continuation = response.get("continue", {})
        if not continuation:
            break
    cache.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(titles, ensure_ascii=False), encoding="utf-8")
    return titles


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_row = False
        self.in_heading = False
        self.in_cell = False
        self.heading = ""
        self.cell = ""
        self.author = ""
        self.downloads: list[str] = []
        self.preview = ""
        self.in_figure = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr":
            self.in_row, self.heading, self.cell = True, "", ""
        elif tag == "th" and self.in_row:
            self.in_heading = True
        elif tag == "td" and self.in_row:
            self.in_cell = True
        elif tag == "a" and self.in_cell and "download" in self.heading.lower():
            url = attrs.get("href", "")
            if urllib.parse.urlsplit(url).scheme in ("http", "https"):
                self.downloads.append(url)
        elif tag == "figure":
            self.in_figure = True
        elif tag == "img" and self.in_figure and not self.preview:
            self.preview = urllib.parse.urljoin(WIKI, attrs.get("src", ""))

    def handle_endtag(self, tag):
        if tag == "th":
            self.in_heading = False
        elif tag == "td":
            self.in_cell = False
        elif tag == "tr":
            if self.heading.strip().lower().rstrip(":") == "author":
                self.author = " ".join(self.cell.split())
            self.in_row = False
        elif tag == "figure":
            self.in_figure = False

    def handle_data(self, data):
        if self.in_heading:
            self.heading += data
        elif self.in_cell:
            self.cell += data


def page_details(title: str, cache: Path) -> dict:
    key = hashlib.sha256(title.encode("utf-8")).hexdigest()
    path = cache / "pages" / (key + ".json")
    if path.is_file() and time.time() - path.stat().st_mtime < CATALOGUE_AGE:
        return json.loads(path.read_text(encoding="utf-8"))
    data = _api({"action": "parse", "page": title, "prop": "text"})
    parser = _PageParser()
    parser.feed(data["parse"]["text"]["*"])
    details = {
        "title": title,
        "author": parser.author,
        "downloads": parser.downloads,
        "preview": parser.preview,
        "url": WIKI + "/wiki/" + urllib.parse.quote(title.replace(" ", "_"), safe="()"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(details, ensure_ascii=False), encoding="utf-8")
    return details


def preview_bytes(url: str, cache: Path) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "mkwiiki.org":
        raise ValueError("Preview is not hosted on the wiki")
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    path = cache / "previews" / key
    if path.is_file():
        return path.read_bytes()
    data = _get(url, 4 * 1024 * 1024)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


DIRECT_HOSTS = frozenset(("mkwiiki.org", "github.com", "raw.githubusercontent.com", "githubusercontent.com"))


def direct_download(url: str) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in DIRECT_HOSTS or not parsed.path.lower().endswith((".szs", ".zip")):
        raise ValueError("This host does not provide a supported direct SZS or ZIP download")
    return _get(url, MAX_PACK, DIRECT_HOSTS)
