@echo off
REM Them muc "Open with AutoSign" vao menu chuot phai cua file .pdf.
REM Chi can double-click file nay - khong can quyen Admin.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0register_context_menu.ps1"
pause
