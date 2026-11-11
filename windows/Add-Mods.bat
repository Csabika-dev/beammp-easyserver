@echo off
title BeamMP EasyServer - Add mods
rem Drag mod .zip files onto this file. Double-click to open the mods folder.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0add-mods.ps1" %*
