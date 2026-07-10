@echo off
title Build TPL Heygen with Nuitka
echo ========================================================
echo  BAT DAU DONG GOI TPL HEYGEN BANG NUITKA
echo ========================================================
echo.

:: Xoa thu muc build cu
if exist build_out rmdir /s /q build_out

:: Chay Nuitka de bien dich code local
:: dung --nofollow-imports de khong bien dich site-packages, giup build nhanh va nhe
nuitka --standalone ^
       --windows-disable-console ^
       --nofollow-imports ^
       --output-dir=build_out ^
       --windows-icon-from-ico=logo.ico ^
       main.py

echo.
echo ========================================================
echo  DANG DOI TEN VA COPY CAC THU VIEN PYTHON...
echo ========================================================
python copy_packages.py

echo.
echo ========================================================
echo  DONG GOI THANH CONG!
echo  File exe nam tai: build_out\TPL_Heygen.dist\TPL_Heygen.exe
echo ========================================================
pause
