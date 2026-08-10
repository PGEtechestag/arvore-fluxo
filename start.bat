@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
python run.py %*
if errorlevel 1 exit /b 1