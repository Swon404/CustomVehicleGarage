$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m pip install --quiet pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name CustomVehicleGarage --icon vehiclegarage\assets\garage.ico --add-data "vehiclegarage\assets;vehiclegarage\assets" garage.py
Write-Host "Built dist\CustomVehicleGarage.exe"
