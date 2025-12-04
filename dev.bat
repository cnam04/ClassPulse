@echo off
setlocal enabledelayedexpansion

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

echo Activating virtual environment...
call .venv\Scripts\activate

echo Installing requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

tasklist /FI "IMAGENAME eq redis-server.exe" | find /I "redis-server.exe" >NUL
if errorlevel 1 (
    echo Starting local Redis...
    start "" redis-server --save "" --appendonly no
)

if "%REDIS_URL%"=="" (
    echo REDIS_URL not set; defaulting to redis://localhost:6379/0
    set REDIS_URL=redis://localhost:6379/0
)

echo Starting ClassPulse...
python -m ClassPulse.app
