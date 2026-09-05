@echo off
cd /d "%~dp0..\IDIFY"
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" main.py
) else (
    python main.py
)
