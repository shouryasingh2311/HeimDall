@echo off
setlocal
cd /d "%~dp0" || exit /b 1

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m scripts.demo %*
) else (
    where /q py.exe
    if errorlevel 1 (
        python.exe -m scripts.demo %*
    ) else (
        py -3 -m scripts.demo %*
    )
)

set "HEIMDAL_EXIT=%errorlevel%"
if not "%HEIMDAL_EXIT%"=="0" pause
exit /b %HEIMDAL_EXIT%
