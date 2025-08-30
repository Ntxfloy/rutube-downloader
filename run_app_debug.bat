@echo off
chcp 65001 >nul
title Rutube Downloader - Отладка

echo.
echo ========================================
echo    RUTUBE DOWNLOADER - ОТЛАДКА
echo ========================================
echo.
echo Запускаю приложение в режиме отладки...
echo.

cd /d "%~dp0"

echo Текущая папка: %CD%
echo Python версия:
py --version
echo.

echo Проверяю зависимости:
py -m pip list | findstr -i "yt-dlp\|requests\|beautifulsoup4\|ttkbootstrap"
echo.

echo Запускаю main.py с отладкой...
echo ========================================
echo.

py -u main.py

echo.
echo ========================================
echo Приложение завершено
echo Нажмите любую клавишу для закрытия...
echo ========================================
pause >nul
