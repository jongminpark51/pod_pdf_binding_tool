@echo off
chcp 65001 > nul
setlocal

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\make_release_zip.ps1"
pause
