@echo off
REM Tra menu chuot phai ve kieu rut gon mac dinh cua Windows 11.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restore_classic_context_menu.ps1" -Undo
pause
