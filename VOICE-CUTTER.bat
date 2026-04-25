@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title WAV Dead Air Tool

:MENU
cls
echo.
echo  ==========================================
echo   WAV Dead Air Tool
echo  ==========================================
echo.
echo   [*] 1.  Full pipeline  (recommended)
echo           Remove dead air + Voice clone + Restore
echo           All in one go - pick files once
echo.
echo   --- Run steps individually ---
echo   2.  Remove dead air only    (play_audio.py)
echo   3.  Voice clone only        (voice_clone.py)
echo   4.  Restore audio only      (restore_audio.py)
echo   ------------------------------
echo   5.  Check / install dependencies
echo   6.  Exit
echo.
set /p CHOICE=  Select option (1-6): 

if "%CHOICE%"=="1" goto RUN_PIPELINE
if "%CHOICE%"=="2" goto RUN_PLAY
if "%CHOICE%"=="3" goto RUN_VOICE
if "%CHOICE%"=="4" goto RUN_RESTORE
if "%CHOICE%"=="5" goto INSTALL_DEPS
if "%CHOICE%"=="6" goto EXIT
echo   Invalid choice. Try again.
timeout /t 1 >nul
goto MENU


:: ?????????????????????????????????????????
:: FIND PYTHON
:: ?????????????????????????????????????????
:FIND_PYTHON
set PYTHON_CMD=

python --version >nul 2>&1
if !ERRORLEVEL! EQU 0 ( set PYTHON_CMD=python & goto PYTHON_FOUND )
python3 --version >nul 2>&1
if !ERRORLEVEL! EQU 0 ( set PYTHON_CMD=python3 & goto PYTHON_FOUND )
py --version >nul 2>&1
if !ERRORLEVEL! EQU 0 ( set PYTHON_CMD=py & goto PYTHON_FOUND )

if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python314\python.exe" & goto PYTHON_FOUND )
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python313\python.exe" & goto PYTHON_FOUND )
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python312\python.exe" & goto PYTHON_FOUND )
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python311\python.exe" & goto PYTHON_FOUND )
if exist "C:\Python314\python.exe" (
    set PYTHON_CMD="C:\Python314\python.exe" & goto PYTHON_FOUND )
if exist "C:\Python312\python.exe" (
    set PYTHON_CMD="C:\Python312\python.exe" & goto PYTHON_FOUND )

echo.
echo  [ERROR] Python not found.
echo  Install from: https://www.python.org/downloads/
echo  Tick "Add Python to PATH" during install.
echo.
pause
goto MENU

:PYTHON_FOUND
for /f "tokens=*" %%V in ('!PYTHON_CMD! --version 2^>^&1') do set PY_VER=%%V
goto %AFTER_FIND%


:: ?????????????????????????????????????????
:: 1 - FULL PIPELINE
:: ?????????????????????????????????????????
:RUN_PIPELINE
set AFTER_FIND=DO_PIPELINE
goto FIND_PYTHON

:DO_PIPELINE
echo.
echo  [OK] !PY_VER!
if not exist "%~dp0pipeline.py" (
    echo  [ERROR] pipeline.py not found in %~dp0
    pause & goto MENU
)
echo  [RUN] Starting full pipeline...
echo.
!PYTHON_CMD! "%~dp0pipeline.py"
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo  [ERROR] Pipeline exited with an error.
    echo  Run option 5 to check dependencies.
)
echo.
pause
goto MENU


:: ?????????????????????????????????????????
:: 2 - REMOVE DEAD AIR
:: ?????????????????????????????????????????
:RUN_PLAY
set AFTER_FIND=DO_PLAY
goto FIND_PYTHON

:DO_PLAY
echo.
echo  [OK] !PY_VER!
if not exist "%~dp0play_audio.py" (
    echo  [ERROR] play_audio.py not found in %~dp0
    pause & goto MENU
)
echo  [RUN] Starting dead air remover...
echo.
!PYTHON_CMD! "%~dp0play_audio.py"
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo  [ERROR] Script exited with an error.
    echo  Run option 5 to check dependencies.
)
echo.
pause
goto MENU


:: ?????????????????????????????????????????
:: 3 - VOICE CLONE
:: ?????????????????????????????????????????
:RUN_VOICE
set AFTER_FIND=DO_VOICE
goto FIND_PYTHON

:DO_VOICE
echo.
echo  [OK] !PY_VER!
if not exist "%~dp0voice_clone.py" (
    echo  [ERROR] voice_clone.py not found in %~dp0
    pause & goto MENU
)
echo  [RUN] Starting voice changer...
echo.
!PYTHON_CMD! "%~dp0voice_clone.py"
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo  [ERROR] Script exited with an error.
    echo  Check your API key and run option 5.
)
echo.
pause
goto MENU


:: ?????????????????????????????????????????
:: 4 - RESTORE
:: ?????????????????????????????????????????
:RUN_RESTORE
set AFTER_FIND=DO_RESTORE
goto FIND_PYTHON

:DO_RESTORE
echo.
echo  [OK] !PY_VER!
if not exist "%~dp0restore_audio.py" (
    echo  [ERROR] restore_audio.py not found in %~dp0
    pause & goto MENU
)
echo  [RUN] Starting audio restorer...
echo.
!PYTHON_CMD! "%~dp0restore_audio.py"
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo  [ERROR] Script exited with an error.
    echo  Run option 5 to check dependencies.
)
echo.
pause
goto MENU


:: ?????????????????????????????????????????
:: 5 - INSTALL DEPENDENCIES
:: ?????????????????????????????????????????
:INSTALL_DEPS
set AFTER_FIND=DO_INSTALL
goto FIND_PYTHON

:DO_INSTALL
echo.
echo  [OK] !PY_VER!
echo.

echo  Checking numpy...
!PYTHON_CMD! -c "import numpy; print('  numpy ' + numpy.__version__ + ' OK')" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo  Installing numpy...
    !PYTHON_CMD! -m pip install numpy --quiet
)

echo  Checking soundfile...
!PYTHON_CMD! -c "import soundfile; print('  soundfile ' + soundfile.__version__ + ' OK')" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo  Installing soundfile...
    !PYTHON_CMD! -m pip install soundfile --quiet
)

echo  Checking requests...
!PYTHON_CMD! -c "import requests; print('  requests ' + requests.__version__ + ' OK')" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo  Installing requests...
    !PYTHON_CMD! -m pip install requests --quiet
)

echo  Checking static-ffmpeg...
!PYTHON_CMD! -c "import static_ffmpeg; print('  static-ffmpeg OK')" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo  Installing static-ffmpeg...
    !PYTHON_CMD! -m pip install static-ffmpeg --quiet
)

echo  Checking playsound...
!PYTHON_CMD! -c "import playsound; print('  playsound OK')" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo  Installing playsound==1.2.2...
    !PYTHON_CMD! -m pip install playsound==1.2.2 --quiet
)

echo.
echo  ------------------------------------------
echo   All dependencies checked.
echo  ------------------------------------------
echo.
pause
goto MENU


:: ?????????????????????????????????????????
:: EXIT
:: ?????????????????????????????????????????
:EXIT
echo.
echo  Goodbye.
timeout /t 1 >nul
exit
