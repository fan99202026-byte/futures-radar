@echo off
REM Start Futures Sound Radar (Windows)
cd /d %~dp0
if not exist .venv (
  python -m venv .venv
  call .venv\Scripts\activate
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate
)
python monitor.py ws
pause
