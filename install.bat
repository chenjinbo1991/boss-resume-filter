@echo off
echo ========================================
echo BOSS 简历筛选器 - 安装脚本
echo ========================================
echo.

echo [1/3] 安装 Python 依赖...
pip install -r requirements.txt

echo.
echo [2/3] 创建必要目录...
if not exist "resumes" mkdir resumes
if not exist "output" mkdir output
if not exist "temp" mkdir temp

echo.
echo ========================================
echo 安装完成！
echo.
echo 下一步:
echo 1. 复制 .env.example 为 .env 并配置 API 密钥
echo 2. 运行：python gui_main.py
echo ========================================
pause
