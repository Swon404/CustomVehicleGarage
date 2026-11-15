"""Install Wiimm's region-specific License Unlock code into Dolphin's game settings."""

import hashlib
import json
import os
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

from vehiclegarage.disc import validate_game_id

SOURCE = "https://mkwiiki.org/wiki/License_Unlock"
REVISION = 356317
CODE_NAME = "Custom Vehicle Garage - License Unlock"
REGIONS = {
    "E": ("USA", "5f921511f2e08bc566fb725fd4fec9e231af8d10f8d05ea0bdf1421011cd7187"),
    "P": ("PAL", "0afcef068c46977c15305b841034f3004ae301d88d801d63f285fbc3802b5d58"),
    "J": ("JAP", "c6c65c58190655b18d8d77b480343b596e13d515a94b15f62340f6c9a322367a"),
    "K": ("KOR", "e97e08e3ed310a41496aca89e544724021eb2bf96c3b6df599c439ed598090c2"),
}
HEX_LINE = re.compile(r"[0-9A-F]{8} [0-9A-F]{8}\Z")


def fetch_code(game_id: str) -> list[str]:
    validate_game_id(game_id)
    region, expected = REGIONS[game_id[3]]
    query = urlencode({
        "action": "query", "prop": "revisions", "revids": REVISION,
        "rvprop": "ids|content", "rvslots": "main", "formatversion": 2, "format": "json",
    })
    request = urllib.request.Request(
        "https://mkwiiki.org/w/api.php?" + query,
        headers={"User-Agent": "CustomVehicleGarage/1.0 (License Unlock setup)"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(256 * 1024 + 1)
    if len(raw) > 256 * 1024:
        raise ValueError("The License Unlock source response is too large")
    try:
        page = json.loads(raw)["query"]["pages"][0]
        revision = page["revisions"][0]
        if revision["revid"] != REVISION:
            raise ValueError("Unexpected License Unlock source revision")
        text = revision["slots"]["main"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as err:
        raise ValueError("Could not read the License Unlock source") from err
    title = f"License Unlock {region} [Wiimm]"
    blocks = re.findall(r"<pre>\s*(.*?)\s*</pre>", text, flags=re.DOTALL)
    matching = [block for block in blocks if block.splitlines() and block.splitlines()[0].strip() == title]
    if len(matching) != 1:
        raise ValueError(f"Could not find a unique License Unlock code for {region}")
    lines = [line.strip().upper() for line in matching[0].splitlines()[1:] if line.strip()]
    if len(lines) != 28 or not all(HEX_LINE.fullmatch(line) for line in lines):
        raise ValueError("License Unlock source contains invalid code")
    digest = hashlib.sha256("\n".join(lines).encode("ascii")).hexdigest()
    if digest != expected:
        raise ValueError("License Unlock source failed verification; no settings were changed")
    return lines


def _section(lines: list[str], name: str) -> tuple[int, int]:
    header = re.compile(r"^\s*\[([^]]+)\]\s*(?:[#;].*)?$")
    starts = [i for i, line in enumerate(lines) if (m := header.match(line)) and m.group(1).casefold() == name.casefold()]
    if len(starts) > 1:
        raise ValueError(f"Dolphin's game settings contain multiple [{name}] sections")
    if not starts:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"[{name}]")
        return len(lines), len(lines)
    start = starts[0] + 1
    end = next((i for i in range(start, len(lines)) if header.match(lines[i])), len(lines))
    return start, end


def configure_text(text: str, code: list[str]) -> str:
    if len(code) != 28 or not all(HEX_LINE.fullmatch(line) for line in code):
        raise ValueError("Invalid Gecko code")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    start, end = _section(lines, "Core")
    matches = [i for i in range(start, end) if re.match(r"^\s*EnableCheats\s*=", lines[i], re.IGNORECASE)]
    if len(matches) > 1:
        raise ValueError("Dolphin's game settings contain multiple EnableCheats entries")
    if matches:
        lines[matches[0]] = "EnableCheats = True"
    else:
        lines.insert(end, "EnableCheats = True")

    start, end = _section(lines, "Gecko")
    title = f"${CODE_NAME} [Wiimm]"
    found = [i for i in range(start, end) if lines[i].strip().lstrip("+").split("[", 1)[0].strip() == f"${CODE_NAME}"]
    if len(found) > 1:
        raise ValueError("Dolphin's game settings contain duplicate License Unlock codes")
    if found:
        pos = found[0]
        stop = next((i for i in range(pos + 1, end) if lines[i].strip().startswith(("$", "+$"))), end)
        existing = [line.strip() for line in lines[pos + 1:stop] if line.strip() and not line.strip().startswith(("#", "*"))]
        if existing != code:
            raise ValueError("Existing License Unlock code was changed; review it in Dolphin before continuing")
    else:
        lines[end:end] = [title, *code]

    start, end = _section(lines, "Gecko_Disabled")
    lines[start:end] = [line for line in lines[start:end] if line.strip() != f"${CODE_NAME}"]
    start, end = _section(lines, "Gecko_Enabled")
    if not any(line.strip() == f"${CODE_NAME}" for line in lines[start:end]):
        lines.insert(end, f"${CODE_NAME}")
    return newline.join(lines) + newline


def install(user_dir: Path, game_id: str, code: list[str]) -> tuple[Path, Path | None]:
    validate_game_id(game_id)
    if not user_dir.is_dir():
        raise ValueError(f"Dolphin user folder was not found: {user_dir}")
    settings = user_dir / "GameSettings"
    if settings.is_dir() and any(settings.glob(f"{game_id}r[0-9]*.ini")):
        raise ValueError(
            "A revision-specific Dolphin game settings file exists. Configure License Unlock in Dolphin "
            "instead, so its higher-priority settings are not overwritten."
        )
    target = settings / f"{game_id}.ini"
    original = target.read_bytes() if target.exists() else b""
    try:
        text = original.decode("utf-8-sig")
    except UnicodeDecodeError as err:
        raise ValueError(f"Dolphin game settings are not UTF-8: {target}") from err
    output = configure_text(text, code).encode("utf-8")
    if original.startswith(b"\xef\xbb\xbf"):
        output = b"\xef\xbb\xbf" + output
    if original == output:
        return target, None
    settings.mkdir(parents=True, exist_ok=True)
    backup = None
    if target.exists():
        with tempfile.NamedTemporaryFile(prefix=f"{game_id}.before-unlock-", suffix=".ini", dir=settings, delete=False) as file:
            backup = Path(file.name)
        shutil.copy2(target, backup)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(prefix=f".{game_id}-", suffix=".tmp", dir=settings, delete=False) as file:
            temp = Path(file.name)
            file.write(output)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, target)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()
    return target, backup
