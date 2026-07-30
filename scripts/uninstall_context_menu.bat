@echo off
REM Go muc "Open with AutoSign" khoi menu chuot phai cua file .pdf.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0register_context_menu.ps1" -Unregister
pause
