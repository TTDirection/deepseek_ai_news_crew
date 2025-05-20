@echo off
chcp 65001 > nul
echo 开始执行AI新闻自动生成任务 - %date% %time%

:: 切换到脚本所在目录
cd /d "%~dp0"

:: 激活Python环境（如果有的话）
:: 注意：如果你使用conda或其他虚拟环境，需要相应修改这里
:: call conda activate your_env_name

:: 执行Python脚本
python auto_run.py

echo 任务执行完成 - %date% %time%
exit /b %errorlevel%