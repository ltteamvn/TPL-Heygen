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
call nuitka --standalone ^
       --windows-disable-console ^
       --no-deployment-flag=excluded-module-usage ^
       --include-package=unittest ^
       --include-package=ctypes ^
       --include-package=urllib ^
       --include-package=http ^
       --include-package=html ^
       --include-package=xml ^
       --include-package=email ^
       --include-module=pdb ^
       --nofollow-import-to=yt_dlp ^
       --nofollow-import-to=torch ^
       --nofollow-import-to=numpy ^
       --nofollow-import-to=matplotlib ^
       --nofollow-import-to=numba ^
       --nofollow-import-to=scipy ^
       --nofollow-import-to=whisper ^
       --nofollow-import-to=PySide6 ^
       --nofollow-import-to=shiboken6 ^
       --nofollow-import-to=qfluentwidgets ^
       --nofollow-import-to=selenium ^
       --nofollow-import-to=requests ^
       --nofollow-import-to=tiktoken ^
       --nofollow-import-to=tiktoken_ext ^
       --nofollow-import-to=librosa ^
       --nofollow-import-to=websocket ^
       --nofollow-import-to=websockets ^
       --nofollow-import-to=pyperclip ^
       --nofollow-import-to=undetected_chromedriver ^
       --nofollow-import-to=darkdetect ^
       --nofollow-import-to=qframelesswindow ^
       --follow-import-to=app_worker ^
       --follow-import-to=browser_controller ^
       --follow-import-to=video_processor ^
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
echo  DANG DONG GOI FILE CAI DAT (.EXE) BANG INNO SETUP...
echo ========================================================
if not exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" goto no_inno
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" setup.iss
echo.
echo ========================================================
echo  DONG GOI CAI DAT SETUP THANH CONG!
echo  File setup tai: build_out\TPL_Heygen_Setup.exe
echo ========================================================
explorer.exe /select,"build_out\TPL_Heygen_Setup.exe"
goto end_build

:no_inno
echo [Warning] Khong tim thay Inno Setup tai C:\Program Files (x86)\Inno Setup 6\ISCC.exe.
echo Vui long tu compile file setup.iss bang tay.
explorer.exe /select,"build_out\TPL_Heygen.dist\TPL_Heygen.exe"

:end_build
rem pause

