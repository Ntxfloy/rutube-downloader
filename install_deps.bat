@echo off
chcp 65001 >nul
title Rutube Downloader - Установка зависимостей

echo.
echo ========================================
echo    RUTUBE DOWNLOADER - УСТАНОВКА
echo ========================================
echo.
echo Устанавливаю зависимости...
echo.

cd /d "%~dp0"

echo Текущая папка: %CD%
echo Python версия:
py --version
echo.

echo Обновляю pip:
py -m pip install --upgrade pip
echo.

echo Устанавливаю зависимости из requirements.txt:
py -m pip install -r requirements.txt
echo.

echo Проверяю установленные пакеты:
py -m pip list | findstr -i "yt-dlp\|requests\|beautifulsoup4\|ttkbootstrap\|lxml"
echo.

echo ========================================
echo Установка завершена!
echo Теперь можно запустить run_app.bat
echo ========================================
pause
