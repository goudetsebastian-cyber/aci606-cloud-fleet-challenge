@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Primero prepara el entorno siguiendo el README.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -X utf8 scripts\run_demo.py
if errorlevel 1 pause
