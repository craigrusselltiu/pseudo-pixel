@echo off
rem Double-click: rebuild the viewer with every sheet in characters/ and examples/, then open it.
cd /d "%~dp0.."
python pp.py view
if errorlevel 1 pause
