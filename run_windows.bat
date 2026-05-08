@echo off
chcp 65001 > nul
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\streamlit.exe" (
    echo First-time setup is required.
    call "%~dp0install_windows.bat"
    if errorlevel 1 exit /b 1
)

".venv\Scripts\streamlit.exe" run app.py --server.headless=false --browser.gatherUsageStats=false
