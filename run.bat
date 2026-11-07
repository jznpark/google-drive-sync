@echo off
chcp 65001 > nul
title Google Drive 동기화 상태 검사기

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [알림] 가상환경을 초기화하고 필요한 패키지를 설치합니다...
    if exist "%USERPROFILE%\.local\bin\uv.exe" (
        "%USERPROFILE%\.local\bin\uv.exe" venv --python 3.11
        "%USERPROFILE%\.local\bin\uv.exe" pip install -r requirements.txt
    ) else (
        python -m venv .venv
        .venv\Scripts\python -m pip install -r requirements.txt
    )
)

echo [실행] Google Drive 동기화 상태 검사기를 실행합니다...
".venv\Scripts\pythonw.exe" main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [오류 발생] 프로그램 실행 중 오류가 발생했습니다:
    ".venv\Scripts\python.exe" main.py
    echo.
    pause
)
