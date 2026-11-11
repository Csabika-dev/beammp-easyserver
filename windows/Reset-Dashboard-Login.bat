@echo off
title BeamMP EasyServer - Reset dashboard login
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -ResetLogin
