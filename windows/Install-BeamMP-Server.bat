@echo off
title BeamMP EasyServer - Install
echo Starting BeamMP EasyServer setup... (click "Yes" if Windows asks for permission)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
