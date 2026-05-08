@echo off
chcp 65001 > nul
setlocal

cd /d "%~dp0"

echo [PDF Binding Sample Tool] Installing dependencies...

set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%PYTHON_EXE%" goto :python_found

for /f "delims=" %%P in ('where python 2^>nul') do (
    "%%P" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" > nul 2> nul
    if not errorlevel 1 (
        set "PYTHON_EXE=%%P"
        goto :python_found
    )
)

where winget > nul 2> nul
if errorlevel 1 (
    echo Python 3.10 or later is required.
    echo Install Python from https://www.python.org/downloads/ and run this file again.
    pause
    exit /b 1
)

echo Python was not found. Installing Python 3.12 with winget...
winget install --id Python.Python.3.12 -e --scope user --accept-package-agreements --accept-source-agreements
set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Python installation finished, but python.exe was not found.
    echo Close this window and run install_windows.bat again.
    pause
    exit /b 1
)

:python_found
echo Python: "%PYTHON_EXE%"

if not exist ".venv\Scripts\python.exe" (
    "%PYTHON_EXE%" -m venv .venv
    if errorlevel 1 (
        echo Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Installation complete.
echo Run run_windows.bat to open the tool.
pause
