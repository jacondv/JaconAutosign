# Khoi phuc kieu menu chuot phai "co dien" (nhu Windows 10) cho TOAN BO he
# thong - khong rieng AutoSign. Tren Windows 11, menu chuot phai mac dinh
# chi hien vai muc, con lai (bao gom "Open with AutoSign") bi an duoi
# "Show more options". Sau khi chay script nay, moi muc se hien thang ra
# ngay, khong can bam "Show more options" nua.
#
# Day la thay doi toan he thong (anh huong den TAT CA ung dung, khong rieng
# AutoSign) va co the hoan tac bat cu luc nao.
#
# Cach dung:
#   .\restore_classic_context_menu.ps1
#
# De hoan tac (tra ve menu rut gon mac dinh cua Windows 11):
#   .\restore_classic_context_menu.ps1 -Undo

param(
    [switch]$Undo
)

$ErrorActionPreference = "Stop"

$clsidKey = "HKCU:\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}"

if ($Undo) {
    if (Test-Path $clsidKey) {
        Remove-Item -Path $clsidKey -Recurse -Force
        Write-Host "Da tra lai menu chuot phai rut gon mac dinh cua Windows 11."
    } else {
        Write-Host "Menu chuot phai dang o che do mac dinh (chua bi doi)."
    }
} else {
    New-Item -Path "$clsidKey\InprocServer32" -Force | Out-Null
    Set-ItemProperty -Path "$clsidKey\InprocServer32" -Name "(Default)" -Value ""
    Write-Host "Da khoi phuc menu chuot phai kieu co dien (Windows 10)."
}

Write-Host "Dang khoi dong lai explorer.exe de ap dung thay doi..."
Stop-Process -Name explorer -Force
Start-Sleep -Seconds 1
Start-Process explorer.exe
