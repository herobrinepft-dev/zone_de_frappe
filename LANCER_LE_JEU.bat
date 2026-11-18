@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -c "import pygame, moderngl, numpy" 2>nul
if errorlevel 1 (
    echo Installation des dependances...
    python -m pip install -r requirements.txt
)
python main.py %*
if errorlevel 1 pause
