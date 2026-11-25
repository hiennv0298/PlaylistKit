@echo off
rem PlaylistKit - run from source. The first run creates .venv and installs the dependencies.
rem   run.cmd                                  open the app window
rem   run.cmd doctor
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
set "VENV=%ROOT%.venv"

if exist "%VENV%\Scripts\playlistkit-gui.exe" goto run

where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Install Python 3.10 or newer, then run this again:
  echo     winget install Python.Python.3.12
  exit /b 1
)
echo First run: creating the environment and installing dependencies, this takes a few minutes...
if not exist "%VENV%\Scripts\python.exe" python -m venv "%VENV%" || exit /b 1
"%VENV%\Scripts\python.exe" -m pip install --quiet --upgrade pip
"%VENV%\Scripts\python.exe" -m pip install --quiet "%ROOT%." || exit /b 1

:run
if "%~1"=="" (
  start "" "%VENV%\Scripts\playlistkit-gui.exe"
  exit /b 0
)
"%VENV%\Scripts\playlistkit.exe" %*
exit /b %errorlevel%
