@echo off
chcp 65001 >nul
title 🚀 Автоматический деплой Jyotish-Bot на Serv00 (24/7)
cls
echo ========================================================
echo   Автоматический деплой Telegram-бота на Serv00 (FreeBSD)
echo ========================================================
echo.
echo Для запуска деплоя введите данные из регистрационного письма:
echo.

python "%~dp0..\tools\deploy_serv00.py"

echo.
pause

