# Them muc "Open with AutoSign" vao menu chuot phai cua file .pdf trong
# Windows Explorer. Chi ghi vao HKEY_CURRENT_USER nen khong can quyen Admin,
# va chi anh huong toi user hien tai.
#
# AutoSign.exe phai nam CUNG THU MUC voi script nay (vd: copy script vao
# dist\AutoSign\ sau khi build, hoac vao thu muc da cai dat AutoSign).
#
# Cach dung:
#   .\register_context_menu.ps1
#
# De go bo:
#   .\register_context_menu.ps1 -Unregister

param(
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"

$exePath = Join-Path $PSScriptRoot "AutoSign.exe"
$regKey = "HKCU:\Software\Classes\SystemFileAssociations\.pdf\shell\AutoSign"

if ($Unregister) {
    if (Test-Path $regKey) {
        Remove-Item -Path $regKey -Recurse -Force
        Write-Host "Da go muc 'Open with AutoSign' khoi menu chuot phai."
    } else {
        Write-Host "Muc 'Open with AutoSign' chua duoc dang ky."
    }
    return
}

if (-not (Test-Path $exePath)) {
    Write-Host "Khong tim thay AutoSign.exe cung thu muc voi script nay ($exePath)."
    Write-Host "Hay dat script nay vao thu muc chua AutoSign.exe roi chay lai."
    return
}

New-Item -Path $regKey -Force | Out-Null
Set-ItemProperty -Path $regKey -Name "(Default)" -Value "Open with AutoSign"
Set-ItemProperty -Path $regKey -Name "Icon" -Value "`"$exePath`""
# "Document" invokes the command once with every selected file passed as
# "%1" (Explorer expands it to all quoted paths, space-separated) instead
# of the default "Player" model, which would launch AutoSign once per file.
Set-ItemProperty -Path $regKey -Name "MultiSelectModel" -Value "Document"

$commandKey = Join-Path $regKey "command"
New-Item -Path $commandKey -Force | Out-Null
Set-ItemProperty -Path $commandKey -Name "(Default)" -Value "`"$exePath`" `"%1`""

Write-Host "Da them muc 'Open with AutoSign' vao menu chuot phai cua file .pdf."
Write-Host "Chuot phai vao mot file .pdf de kiem tra."
