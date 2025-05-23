@echo off
chcp 65001
echo Starting AI News Generation Task - %date% %time%

:: Activate virtual environment
call .venv\Scripts\activate

:: Run the news generation script
python auto_run.py

:: Deactivate virtual environment
deactivate

echo Task completed - %date% %time%
pause