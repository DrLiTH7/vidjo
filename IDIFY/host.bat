@echo off
set "PATH=%~dp0venv\Scripts;%PATH%"
"%~dp0venv\Scripts\python.exe" "%~dp0host.py" %*
