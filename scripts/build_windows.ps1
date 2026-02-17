$ErrorActionPreference = "Stop"

Write-Host "==> Building Jinkies for Windows..."

$iconFlag = @()
if (Test-Path "assets/icon.ico") {
    $iconFlag = @("--icon=assets/icon.ico")
}

uv run pyinstaller `
    --onefile `
    --windowed `
    --name Jinkies `
    @iconFlag `
    --add-data "sounds;sounds" `
    main.py

Write-Host "==> Done: dist/Jinkies.exe"
