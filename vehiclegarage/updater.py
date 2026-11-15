"""Check and install Windows releases published by Custom Vehicle Garage."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from vehiclegarage.version import VERSION

RELEASE_API = "https://api.github.com/repos/Swon404/CustomVehicleGarage/releases/latest"
ASSET_NAME = "CustomVehicleGarage.exe"
MAX_DOWNLOAD_BYTES = 150 * 1024 * 1024
TIMEOUT = 30


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    sha256: str


def _version_tuple(version: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise UpdateError(f"Invalid release version: {version}")
    return tuple(int(part) for part in version.split("."))


def latest_release() -> Release | None:
    request = Request(RELEASE_API, headers={"Accept": "application/vnd.github+json", "User-Agent": "CustomVehicleGarage"})
    with urlopen(request, timeout=TIMEOUT) as response:
        data = json.load(response)
    if not isinstance(data, dict) or not isinstance(data.get("tag_name"), str):
        raise UpdateError("GitHub returned an invalid release.")
    tag = data["tag_name"]
    if not tag.startswith("v"):
        raise UpdateError(f"Invalid release tag: {tag}")
    version = tag[1:]
    if _version_tuple(version) <= _version_tuple(VERSION):
        return None
    assets = data.get("assets")
    if not isinstance(assets, list):
        raise UpdateError("The release has no downloadable assets.")
    matches = [asset for asset in assets if isinstance(asset, dict) and asset.get("name") == ASSET_NAME]
    if len(matches) != 1:
        raise UpdateError("The release does not contain exactly one application executable.")
    asset = matches[0]
    url = asset.get("browser_download_url")
    digest = asset.get("digest")
    if not isinstance(url, str) or not isinstance(digest, str):
        raise UpdateError("The release is missing the download URL or SHA-256 digest.")
    parsed = urlparse(url)
    expected_prefix = f"/Swon404/CustomVehicleGarage/releases/download/{tag}/"
    if parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.path != expected_prefix + ASSET_NAME:
        raise UpdateError("The release download URL is not the expected GitHub asset.")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise UpdateError("The release has an invalid SHA-256 digest.")
    return Release(version, url, digest.removeprefix("sha256:"))


def download_release(release: Release, destination: Path) -> None:
    request = Request(release.url, headers={"User-Agent": "CustomVehicleGarage"})
    digest = hashlib.sha256()
    size = 0
    try:
        with urlopen(request, timeout=TIMEOUT) as response, destination.open("wb") as output:
            if urlparse(response.geturl()).scheme != "https":
                raise UpdateError("The update download did not use HTTPS.")
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_DOWNLOAD_BYTES:
                    raise UpdateError("The update exceeds the maximum download size.")
                digest.update(chunk)
                output.write(chunk)
        if not size or digest.hexdigest() != release.sha256:
            raise UpdateError("The downloaded update failed its SHA-256 check.")
    except Exception:
        destination.unlink(missing_ok=True)
        raise


_INSTALL_SCRIPT = r"""
param([string]$Source, [string]$Target, [int]$ParentId, [string]$WorkDir)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$backup = Join-Path $WorkDir 'previous.exe'
try {
    try { Wait-Process -Id $ParentId -Timeout 30 -ErrorAction Stop }
    catch {
        if (Get-Process -Id $ParentId -ErrorAction SilentlyContinue) { throw 'The app did not close in time.' }
    }
    $deadline = (Get-Date).AddSeconds(30)
    do {
        $running = @(Get-Process -Name ([IO.Path]::GetFileNameWithoutExtension($Target)) -ErrorAction SilentlyContinue |
            Where-Object { $_.Path -eq $Target })
        if ($running.Count -eq 0) { break }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
    if ($running.Count -gt 0) { throw 'The app is still running. Close all copies and try again.' }
    Copy-Item -LiteralPath $Target -Destination $backup
    try {
        Copy-Item -LiteralPath $Source -Destination $Target -Force
        $env:PYINSTALLER_RESET_ENVIRONMENT = '1'
        Start-Process -FilePath $Target -WorkingDirectory (Split-Path -Parent $Target)
    } catch {
        Copy-Item -LiteralPath $backup -Destination $Target -Force
        throw
    }
} catch {
    [System.Windows.Forms.MessageBox]::Show("Update failed: $($_.Exception.Message)`nIf needed, the previous app backup is in: $WorkDir", 'Custom Vehicle Garage') | Out-Null
    exit 1
}
try {
    Remove-Item -LiteralPath $Source, $backup -Force
    Remove-Item -LiteralPath (Join-Path $WorkDir 'install.ps1') -Force
    Remove-Item -LiteralPath $WorkDir -Force
} catch {
    [System.Windows.Forms.MessageBox]::Show("The update was installed, but temporary files could not be removed from: $WorkDir`n$($_.Exception.Message)", 'Custom Vehicle Garage') | Out-Null
}
"""


def install_release(release: Release) -> None:
    if os.name != "nt" or not getattr(sys, "frozen", False):
        raise UpdateError("Automatic updates are available only in the Windows executable.")
    target = Path(sys.executable).resolve()
    work_dir = Path(tempfile.mkdtemp(prefix="CustomVehicleGarage-update-"))
    download = work_dir / ASSET_NAME
    try:
        download_release(release, download)
        script = work_dir / "install.ps1"
        script.write_text(_INSTALL_SCRIPT, encoding="utf-8")
        subprocess.Popen(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-File", str(script), "-Source", str(download), "-Target", str(target),
                "-ParentId", str(os.getpid()), "-WorkDir", str(work_dir),
            ],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except Exception:
        shutil.rmtree(work_dir)
        raise
