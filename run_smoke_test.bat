@echo off
chcp 65001 > nul
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    call "%~dp0install_windows.bat"
    if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" tests\smoke_test.py
pause
