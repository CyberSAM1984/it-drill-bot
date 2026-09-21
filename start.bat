@echo off
chcp 65001 >nul
cd /d %~dp0
if not exist .env (
    echo Создай .env с BOT_TOKEN! Пример: copy .env.example .env
    pause
    exit /b 1
)
venv\Scripts\python.exe bot.py
pause
