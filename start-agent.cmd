@echo off
setlocal
title Resume Agent

cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "APP_URL=http://localhost:8501"
set "LAN_IP="

echo.
echo ==========================================
echo   Resume Agent launcher
echo ==========================================
echo.
echo Project directory: %cd%
echo.

set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 set "PY_CMD=py -3"

if "%PY_CMD%"=="" (
    where python >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
)

if "%PY_CMD%"=="" (
    echo [ERROR] Python was not found.
    echo Install Python 3.11 or 3.12, then enable "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

if not exist "app.py" (
    echo [ERROR] app.py was not found.
    echo Put this launcher in the resume-agent project folder.
    echo.
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo [ERROR] requirements.txt was not found.
    echo.
    pause
    exit /b 1
)

for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$ip = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like '192.168.*' -or $_.IPAddress -like '10.*' -or $_.IPAddress -like '172.16.*' -or $_.IPAddress -like '172.17.*' -or $_.IPAddress -like '172.18.*' -or $_.IPAddress -like '172.19.*' -or $_.IPAddress -like '172.2?.*' -or $_.IPAddress -like '172.30.*' -or $_.IPAddress -like '172.31.*' } | Sort-Object InterfaceMetric | Select-Object -First 1 -ExpandProperty IPAddress; if ($ip) { $ip }"`) do set "LAN_IP=%%I"

%PY_CMD% -c "import streamlit, langgraph, openai, pydantic" >nul 2>nul
if errorlevel 1 (
    echo [SETUP] Installing missing dependencies...
    %PY_CMD% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Dependency installation failed.
        echo Check your network connection, then run this launcher again.
        echo.
        pause
        exit /b 1
    )
)

echo.
echo Starting Resume Agent...
echo Local URL, only for this computer: %APP_URL%
if not "%LAN_IP%"=="" (
    echo LAN URL, for other computers on the same network: http://%LAN_IP%:8501
) else (
    echo LAN URL: use this computer's LAN IP with port 8501.
    echo Example: http://192.168.x.x:8501
)
echo Public URL: use your Streamlit Cloud deployment URL, not localhost.
echo.
echo Keep this window open while using the app.
echo Close this window to stop the app.
echo.

start "" "%APP_URL%"
%PY_CMD% -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501

echo.
echo Resume Agent stopped.
pause
