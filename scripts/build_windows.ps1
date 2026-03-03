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

# Build the Inno Setup installer if ISCC is available
$iscc = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
if (-not $iscc) {
    # Try the default Inno Setup installation path
    $defaultPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if (Test-Path $defaultPath) {
        $iscc = $defaultPath
    }
}

if ($iscc) {
    Write-Host "==> Building Windows installer with Inno Setup..."
    & "$iscc" "installer\windows\jinkies.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compilation failed (exit code $LASTEXITCODE)"
    }
    Write-Host "==> Done: dist/JinkiesSetup.exe"
} else {
    Write-Host "==> Inno Setup (ISCC.exe) not found; skipping installer creation."
    Write-Host "    Install Inno Setup from https://jrsoftware.org/isdl.php to produce an installer."
}
