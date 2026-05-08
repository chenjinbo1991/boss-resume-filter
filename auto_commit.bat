@echo off
chcp 65001 >nul
cd /d C:\Users\yaououzhong\work\boss-resume-filter

:: 检查是否有更改
git status --porcelain > nul
if %errorlevel% equ 0 (
    for /f %%i in ('git status --porcelain 2^>nul ^| find /c /v ""') do set CHANGES=%%i
) else (
    set CHANGES=0
)

if %CHANGES% gtr 0 (
    git add -A
    for /f "tokens=1-3 delims=/- " %%a in ('date /t') do set TODAY=%%a-%%b-%%c
    git commit -m "Auto: 每日自动提交 %TODAY%"
    echo [%date% %time%] 已提交 %CHANGES% 个文件
) else (
    echo [%date% %time%] 没有需要提交的更改
)
