@echo off
setlocal

set "DIR=%~dp0"
set "DIR=%DIR:~0,-1%"

if exist "%DIR%\.venv\Scripts\python.exe" (
    set "PYTHON=%DIR%\.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

"%PYTHON%" -c "import telemcp" 2>nul
if errorlevel 1 (
    set "PYTHONPATH=%DIR%\src;%PYTHONPATH%"
)

"%PYTHON%" -m telemcp %*
