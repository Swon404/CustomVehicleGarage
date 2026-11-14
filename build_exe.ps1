$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m pip install --quiet pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name CustomVehicleGarage garage.py
Write-Host "Built dist\CustomVehicleGarage.exe"
