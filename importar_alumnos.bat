@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
python import_from_sheets.py
pause
