#Requires -Version 5.1
<#
.SYNOPSIS
    Builds the portable CactusReader folder in this directory.

.DESCRIPTION
    Runs PyInstaller in one-folder mode, then copies CactusReader.exe and the
    _internal folder next to this script.  The resulting folder is the whole
    application: copy it anywhere and run CactusReader.exe.

.PARAMETER Clean
    Remove build/, dist/ and the previous CactusReader.exe/_internal before
    building.  This is the default behaviour.  Use -NoClean to reuse caches.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\build.ps1
#>
param(
    [switch]$NoClean
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "[1/3] Checking dependencies..." -ForegroundColor Cyan
python -c "import PySide6, pymupdf, PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Missing build dependency. Install with: python -m pip install PySide6 pymupdf pyinstaller"
}

if (-not $NoClean) {
    Write-Host "[2/3] Cleaning previous build output..." -ForegroundColor Cyan
    Remove-Item -Recurse -Force "$root\build", "$root\dist" -ErrorAction SilentlyContinue
    Remove-Item -Force "$root\CactusReader.exe" -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force "$root\_internal" -ErrorAction SilentlyContinue
} else {
    Write-Host "[2/3] Keeping previous build output (-NoClean)." -ForegroundColor Cyan
}

Write-Host "[3/3] Building one-folder application..." -ForegroundColor Cyan
python -m PyInstaller --clean --noconfirm "$root\CactusReader.spec"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$built = Join-Path $root "dist\CactusReader\CactusReader.exe"
if (-not (Test-Path $built)) {
    throw "Build completed but $built was not found."
}

# Put the executable and its runtime files directly in the folder the user
# opens.  settings.json stays here too, which is what makes the folder portable.
Copy-Item -Path "$root\dist\CactusReader\*" -Destination $root -Recurse -Force

$size = (Get-ChildItem "$root\_internal" -Recurse -File | Measure-Object Length -Sum).Sum
Write-Host ""
Write-Host "Build complete." -ForegroundColor Green
Write-Host "  Executable: $root\CactusReader.exe"
Write-Host ("  Runtime:    {0:N1} MB" -f ($size / 1MB))
Write-Host "Copy the whole CactusReader folder to move the reader (settings included)."
