# Dong goi Autosign thanh .exe chay doc lap (khong can cai Python) tren May Windows.
# Chay tu thu muc goc project: .\scripts\build.ps1

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install pyinstaller

Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

.\.venv\Scripts\python.exe -m PyInstaller autosign.spec --noconfirm

Write-Host ""
Write-Host "Da dong goi xong. File chay: dist\AutoSign\AutoSign.exe"
Write-Host "Copy ca thu muc dist\AutoSign sang may khac de cai dat/chay (khong can cai Python)."
