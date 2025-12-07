# PowerShell build script for JobDocs Windows installer
# Run this from the windows_installer directory

Clear-Host
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "        JobDocs Windows Installer Build Script" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if we're in the right directory
if (-not (Test-Path "..\JobDocs-qt.py")) {
    Write-Host "ERROR: JobDocs-qt.py not found in parent directory" -ForegroundColor Red
    Write-Host ""
    Write-Host "This script must be run from the windows_installer directory" -ForegroundColor Yellow
    Write-Host "Current directory: $PWD" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 1: Check Python
Write-Host "[1/5] Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = py --version 2>&1
    Write-Host "Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

# Step 2: Install dependencies
Write-Host "[2/5] Installing/upgrading build dependencies..." -ForegroundColor Yellow
py -m pip install --upgrade pyinstaller pillow
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

# Step 3: Create icon
Write-Host "[3/5] Creating application icon..." -ForegroundColor Yellow
py create_icon.py
Write-Host ""

# Step 4: Build executable
Write-Host "[4/5] Building executable with PyInstaller..." -ForegroundColor Yellow
py build_windows.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Build failed" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

# Step 5: Build installer
Write-Host "[5/5] Building installer with Inno Setup..." -ForegroundColor Yellow
$innoSetupPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

if (Test-Path $innoSetupPath) {
    & $innoSetupPath "JobDocs-installer.iss"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Inno Setup compilation failed" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "                   BUILD COMPLETE!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "Installer: ..\installer_output\JobDocs-1.0.0-Setup.exe" -ForegroundColor Green
    Write-Host "Executable: ..\dist\JobDocs.exe" -ForegroundColor Green
    Write-Host ""
    Get-ChildItem -Path "..\installer_output\*.exe" -ErrorAction SilentlyContinue | ForEach-Object {
        $sizeMB = [math]::Round($_.Length / 1MB, 2)
        Write-Host "  $($_.Name) ($sizeMB MB)" -ForegroundColor Green
    }
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "Inno Setup not found at default location." -ForegroundColor Yellow
    Write-Host "Please install Inno Setup from: https://jrsoftware.org/isinfo.php" -ForegroundColor Yellow
    Write-Host "Then run: ISCC.exe JobDocs-installer.iss" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Executable is ready in: ..\dist\JobDocs.exe" -ForegroundColor Green
}

Read-Host "Press Enter to exit"
