@echo off
setlocal
title Open Resume Agent

cd /d "%~dp0"
set "CLOUD_URL=https://hanabi-resume-agent.streamlit.app/"

if exist "cloud-url.txt" (
    for /f "usebackq delims=" %%U in ("cloud-url.txt") do (
        if not "%%U"=="" set "CLOUD_URL=%%U"
        goto :url_loaded
    )
)

:url_loaded

echo.
echo ==========================================
echo   Resume Agent cloud launcher
echo ==========================================
echo.

echo %CLOUD_URL% | findstr /i ".streamlit.app" >nul
if errorlevel 1 (
    echo [ERROR] Invalid Streamlit Cloud URL:
    echo %CLOUD_URL%
    echo.
    echo The URL should look like:
    echo https://xxx.streamlit.app
    echo.
    pause
    exit /b 1
)

echo Opening:
echo %CLOUD_URL%
echo.
echo This launcher does not start localhost.
echo It opens the public Streamlit Cloud URL.
echo.
start "" "%CLOUD_URL%"
exit /b 0
