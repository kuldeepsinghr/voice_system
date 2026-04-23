@echo off
setlocal EnableDelayedExpansion
title WAV Dead Air Tool

:MENU
cls
echo.
echo  ==========================================
echo   WAV Dead Air Tool
echo  ==========================================
echo.
echo   1.  Remove dead air       (play_audio.py)
echo   2.  ElevenLabs voice change  (voice_clone.py)
echo   3.  Restore original audio  (restore_audio.py)
echo   4.  Check / install dependencies
echo   5.  Exit
echo.
echo   Pipeline:  1  --^>  2  --^>  3
echo.
set /p CHOICE=  Select option (1-5): 

if "%CHOICE%"=="1" goto RUN_PLAY
if "%CHOICE%"=="2" goto RUN_VOICE
if "%CHOICE%"=="3" goto RUN_RESTORE
if "%CHOICE%"=="4" goto INSTALL_DEPS
if "%CHOICE%"=="5" goto EXIT
echo   Invalid choice. Try again.
timeout /t 1 >nul
goto MENU


:: ─────────────────────────────────────────
:: FIND PYTHON
:: ─────────────────────────────────────────
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
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python310\python.exe" & goto PYTHON_FOUND )
if exist "C:\Python314\python.exe" (
    set PYTHON_CMD="C:\Python314\python.exe" & goto PYTHON_FOUND )
if exist "C:\Python312\python.exe" (
    set PYTHON_CMD="C:\Python312\python.exe" & goto PYTHON_FOUND )

echo.
echo  [ERROR] Python not found on this machine.
echo.
echo  Install from: https://www.python.org/downloads/
echo  Tick "Add Python to PATH" during install.
echo.
pause
goto MENU

:PYTHON_FOUND
for /f "tokens=*" %%V in ('!PYTHON_CMD! --version 2^>^&1') do set PY_VER=%%V
goto %AFTER_FIND%


:: ─────────────────────────────────────────
:: 1 — REMOVE DEAD AIR
:: ─────────────────────────────────────────
:RUN_PLAY
set AFTER_FIND=DO_PLAY
goto FIND_PYTHON

:DO_PLAY
echo.
echo  [OK] Using: !PY_VER!  (!PYTHON_CMD!)
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
    echo  Run option 4 to check dependencies.
)
echo.
pause
goto MENU


:: ─────────────────────────────────────────
:: 2 — ELEVENLABS VOICE CHANGE
:: ─────────────────────────────────────────
:RUN_VOICE
set AFTER_FIND=DO_VOICE
goto FIND_PYTHON

:DO_VOICE
echo.
echo  [OK] Using: !PY_VER!  (!PYTHON_CMD!)
if not exist "%~dp0voice_clone.py" (
    echo  [ERROR] voice_clone.py not found in %~dp0
    pause & goto MENU
)
echo  [RUN] Starting ElevenLabs voice changer...
echo.
!PYTHON_CMD! "%~dp0voice_clone.py"
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo  [ERROR] Script exited with an error.
    echo  Check your API key and run option 4 to check dependencies.
)
echo.
pause
goto MENU


:: ─────────────────────────────────────────
:: 3 — RESTORE ORIGINAL AUDIO
:: ─────────────────────────────────────────
:RUN_RESTORE
set AFTER_FIND=DO_RESTORE
goto FIND_PYTHON

:DO_RESTORE
echo.
echo  [OK] Using: !PY_VER!  (!PYTHON_CMD!)
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
    echo  Run option 4 to check dependencies.
)
echo.
pause
goto MENU


:: ─────────────────────────────────────────
:: 4 — INSTALL DEPENDENCIES
:: ─────────────────────────────────────────
:INSTALL_DEPS
set AFTER_FIND=DO_INSTALL
goto FIND_PYTHON

:DO_INSTALL
echo.
echo  [OK] Using: !PY_VER!  (!PYTHON_CMD!)
echo.

echo  Checking numpy...
!PYTHON_CMD! -c "import numpy; print('  numpy ' + numpy.__version__ + ' OK')" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo  Installing numpy...
    !PYTHON_CMD! -m pip install numpy --quiet
    if !ERRORLEVEL! NEQ 0 ( echo  [WARN] numpy install may have failed. ) else ( echo  numpy installed OK. )
)

echo  Checking soundfile...
!PYTHON_CMD! -c "import soundfile; print('  soundfile ' + soundfile.__version__ + ' OK')" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo  Installing soundfile...
    !PYTHON_CMD! -m pip install soundfile --quiet
    if !ERRORLEVEL! NEQ 0 ( echo  [WARN] soundfile install may have failed. ) else ( echo  soundfile installed OK. )
)

echo  Checking requests...
!PYTHON_CMD! -c "import requests; print('  requests ' + requests.__version__ + ' OK')" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo  Installing requests...
    !PYTHON_CMD! -m pip install requests --quiet
    if !ERRORLEVEL! NEQ 0 ( echo  [WARN] requests install may have failed. ) else ( echo  requests installed OK. )
)

echo  Checking static-ffmpeg...
!PYTHON_CMD! -c "import static_ffmpeg; print('  static-ffmpeg OK')" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo  Installing static-ffmpeg...
    !PYTHON_CMD! -m pip install static-ffmpeg --quiet
    if !ERRORLEVEL! NEQ 0 ( echo  [WARN] static-ffmpeg install may have failed. ) else ( echo  static-ffmpeg installed OK. )
)

echo  Checking playsound...
!PYTHON_CMD! -c "import playsound; print('  playsound OK')" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo  Installing playsound==1.2.2...
    !PYTHON_CMD! -m pip install playsound==1.2.2 --quiet
    if !ERRORLEVEL! NEQ 0 ( echo  [WARN] playsound install may have failed. ) else ( echo  playsound installed OK. )
)

echo.
echo  ──────────────────────────────────────
echo   All dependencies checked.
echo  ──────────────────────────────────────
echo.
pause
goto MENU


:: ─────────────────────────────────────────
:: EXIT
:: ─────────────────────────────────────────
:EXIT
echo.
echo  Goodbye.
timeout /t 1 >nul
exit
