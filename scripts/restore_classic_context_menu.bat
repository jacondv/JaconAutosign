@echo off
REM Khoi phuc menu chuot phai kieu co dien (Windows 10) cho TOAN BO he thong
REM - de "Open with AutoSign" (va moi muc khac) hien thang ra, khong con bi
REM an duoi "Show more options" nua. Anh huong den tat ca ung dung, khong
REM rieng AutoSign. Khong can quyen Admin.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restore_classic_context_menu.ps1"
pause
