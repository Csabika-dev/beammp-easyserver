@echo off
title BeamMP wake helper - Install
echo Installing the BeamMP wake helper... (click "Yes" if Windows asks for permission)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-wake-helper.ps1"
