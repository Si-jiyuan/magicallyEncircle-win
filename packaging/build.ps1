param(
    [switch]$Installer,
    [string]$Python = "D:\work\env\miniconda\envs\p3.11\python.exe"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $running = Get-Process -Name "MagicallyEncircle" -ErrorAction SilentlyContinue
    if ($running) {
        throw "MagicallyEncircle is running. Quit it from the tray before building; dist\MagicallyEncircle\data\logs\app.log is locked."
    }

    Write-Host "Using Python: $Python"
    & $Python -c "import PySide6, PIL, PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Missing build dependencies. Run: $Python -m pip install -r requirements-build.txt"
    }

    if (-not (Test-Path "assets\app.ico")) {
        Write-Host "Generating assets\app.ico"
        & $Python -c "from PIL import Image; im=Image.open('assets/icon.png'); im.save('assets/app.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
    }

    Write-Host "Running PyInstaller"
    & $Python -m PyInstaller --clean --noconfirm packaging\app.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

    Copy-Item -Path "portable.flag" -Destination "dist\MagicallyEncircle\portable.flag" -Force
    Copy-Item -Path "README.md" -Destination "dist\MagicallyEncircle\README.md" -Force
    Copy-Item -Path "LICENSE" -Destination "dist\MagicallyEncircle\LICENSE" -Force
    Copy-Item -Path "assets" -Destination "dist\MagicallyEncircle\assets" -Recurse -Force
    if (Test-Path "dist\MagicallyEncircle-portable.zip") {
        Remove-Item "dist\MagicallyEncircle-portable.zip" -Force
    }
    Compress-Archive -Path "dist\MagicallyEncircle\*" -DestinationPath "dist\MagicallyEncircle-portable.zip" -Force
    Write-Host "Portable build: dist\MagicallyEncircle\ and dist\MagicallyEncircle-portable.zip"

    if ($Installer) {
        Remove-Item "dist\MagicallyEncircle\portable.flag" -ErrorAction SilentlyContinue
        $iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
        if (-not (Test-Path $iscc)) {
            throw "Inno Setup 6 not found at $iscc"
        }
        & $iscc "packaging\installer.iss"
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
        Write-Host "Installer: dist\MagicallyEncircle-Setup.exe"
    }
}
finally {
    Pop-Location
}
