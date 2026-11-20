@echo off
title HeimDall Observability Platform
echo ==========================================================================
echo   Starting HeimDall Observability Platform (1-Click Launcher)
echo ==========================================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
pause
