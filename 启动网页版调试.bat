@echo off
chcp 65001 >nul
title Amiya NotebookLM Web 调试工作台
echo ========================================================
echo   Amiya NotebookLM Web 网页版调试工作台
echo   访问地址: http://127.0.0.1:5050
echo ========================================================
python run_web.py
pause
