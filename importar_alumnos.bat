@echo off
cd /d "C:\Users\Candela\Desktop\academia\academia_api"
call venv\Scripts\activate.bat
python import_from_sheets.py
pause
