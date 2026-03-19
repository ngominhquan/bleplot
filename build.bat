@echo off
:: Build BLEPlot as a standalone Windows executable.
:: Output: dist\BLEPlot\BLEPlot.exe  (onedir, recommended)
::         dist\BLEPlot.exe           (onefile, with --onefile flag)
::
:: Usage:
::   build.bat            -- onedir bundle (faster startup, recommended)
::   build.bat --onefile  -- single .exe   (slower startup)
::
:: Requirements:
::   pip install pyinstaller  (handled automatically below)
::   Windows 10 / 11 with Bluetooth 4.0+ adapter

setlocal

set VENV=.venv
set ENTRY=src\bleplot\main.py
set APP_NAME=BLEPlot

if not exist "%VENV%\Scripts\python.exe" (
    echo ERROR: virtualenv '%VENV%' not found.
    echo Run: python -m venv .venv ^&^& .venv\Scripts\pip install -e .
    exit /b 1
)

echo =^> Installing / upgrading PyInstaller...
"%VENV%\Scripts\pip" install --quiet --upgrade pyinstaller

set MODE=--onedir
if "%1"=="--onefile" (
    set MODE=--onefile
    echo =^> Mode: onefile ^(single executable^)
) else (
    echo =^> Mode: onedir ^(bundle directory^)
)

echo =^> Building %APP_NAME% for Windows...
"%VENV%\Scripts\pyinstaller" ^
    --clean ^
    --noconfirm ^
    %MODE% ^
    --windowed ^
    --name "%APP_NAME%" ^
    --collect-all dearpygui ^
    --hidden-import bleak ^
    --hidden-import bleak.backends.winrt ^
    --hidden-import bleak.backends.winrt.scanner ^
    --hidden-import bleak.backends.winrt.client ^
    --hidden-import bleak.backends.winrt.utils ^
    "%ENTRY%"

if errorlevel 1 (
    echo ERROR: Build failed.
    exit /b 1
)

echo.
if "%MODE%"=="--onefile" (
    echo =^> Done: dist\%APP_NAME%.exe
) else (
    echo =^> Done: dist\%APP_NAME%\%APP_NAME%.exe
)
endlocal
