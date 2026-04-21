@echo off
setlocal EnableDelayedExpansion
title WAV Dead Air Tool

:: ─────────────────────────────────────────
:: MENU
:: ─────────────────────────────────────────
:MENU
cls
echo.
echo  ==========================================
echo   WAV Dead Air Tool
echo  ==========================================
echo.
echo   1.  Remove dead air from WAV file
echo   2.  Restore original audio from cleaned WAV
echo   3.  Check / install dependencies
echo   4.  Exit
echo.
set /p CHOICE=  Select option (1-4): 

if "%CHOICE%"=="1" goto CHECK_PYTHON_PLAY
if "%CHOICE%"=="2" goto CHECK_PYTHON_RESTORE
if "%CHOICE%"=="3" goto INSTALL_DEPS
if "%CHOICE%"=="4" goto EXIT
echo   Invalid choice. Try again.
timeout /t 1 >nul
goto MENU


:: ─────────────────────────────────────────
:: FIND PYTHON
:: ─────────────────────────────────────────
:FIND_PYTHON
set PYTHON_CMD=

:: Try 'python' first
python --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set PYTHON_CMD=python
    goto :PYTHON_FOUND
)

:: Try 'python3'
python3 --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set PYTHON_CMD=python3
    goto :PYTHON_FOUND
)

:: Try 'py' launcher (Windows)
py --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set PYTHON_CMD=py
    goto :PYTHON_FOUND
)

:: Try common install paths
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "C:\Python314\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
) do (
    if exist %%P (
        set PYTHON_CMD=%%P
        goto :PYTHON_FOUND
    )
)

:: Not found
echo.
echo  [ERROR] Python not found on this machine.
echo.
echo  Please install Python from https://www.python.org/downloads/
echo  Make sure to check "Add Python to PATH" during install.
echo.
pause
goto MENU

:PYTHON_FOUND
for /f "tokens=*" %%V in ('!PYTHON_CMD! --version 2^>^&1') do set PY_VER=%%V
goto :EOF


:: ─────────────────────────────────────────
:: CHECK PYTHON THEN RUN PLAY_AUDIO
:: ─────────────────────────────────────────
:CHECK_PYTHON_PLAY
call :FIND_PYTHON
if "!PYTHON_CMD!"=="" goto MENU
echo.
echo  [OK] Using: !PY_VER!  (!PYTHON_CMD!)

if not exist "%~dp0play_audio.py" (
    echo.
    echo  [ERROR] play_audio.py not found in:
    echo  %~dp0
    echo.
    pause
    goto MENU
)

echo  [RUN] Starting dead air remover...
echo.
!PYTHON_CMD! "%~dp0play_audio.py"
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo  [ERROR] Script exited with an error.
    echo  Check that dependencies are installed ^(option 3^).
)
echo.
pause
goto MENU


:: ─────────────────────────────────────────
:: CHECK PYTHON THEN RUN RESTORE_AUDIO
:: ─────────────────────────────────────────
:CHECK_PYTHON_RESTORE
call :FIND_PYTHON
if "!PYTHON_CMD!"=="" goto MENU
echo.
echo  [OK] Using: !PY_VER!  (!PYTHON_CMD!)

if not exist "%~dp0restore_audio.py" (
    echo.
    echo  [ERROR] restore_audio.py not found in:
    echo  %~dp0
    echo.
    pause
    goto MENU
)

echo  [RUN] Starting audio restorer...
echo.
!PYTHON_CMD! "%~dp0restore_audio.py"
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo  [ERROR] Script exited with an error.
    echo  Check that dependencies are installed ^(option 3^).
)
echo.
pause
goto MENU


:: ─────────────────────────────────────────
:: INSTALL DEPENDENCIES
:: ─────────────────────────────────────────
:INSTALL_DEPS
call :FIND_PYTHON
if "!PYTHON_CMD!"=="" goto MENU

echo.
echo  [OK] Using: !PY_VER!  (!PYTHON_CMD!)
echo.

:: Check numpy
echo  Checking numpy...
!PYTHON_CMD! -c "import numpy; print('  numpy ' + numpy.__version__ + ' — OK')" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo  Installing numpy...
    !PYTHON_CMD! -m pip install numpy --quiet
    if !ERRORLEVEL! NEQ 0 echo  [WARN] numpy install may have failed.
)

:: Check soundfile
echo  Checking soundfile...
!PYTHON_CMD! -c "import soundfile; print('  soundfile ' + soundfile.__version__ + ' — OK')" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo  Installing soundfile...
    !PYTHON_CMD! -m pip install soundfile --quiet
    if !ERRORLEVEL! NEQ 0 echo  [WARN] soundfile install may have failed.
)

:: Check playsound
echo  Checking playsound...
!PYTHON_CMD! -c "import playsound; print('  playsound — OK')" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo  Installing playsound==1.2.2...
    !PYTHON_CMD! -m pip install playsound==1.2.2 --quiet
    if !ERRORLEVEL! NEQ 0 echo  [WARN] playsound install may have failed.
)

echo.
echo  ──────────────────────────────────────
echo   Dependency check complete.
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