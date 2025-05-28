#!/bin/bash
echo "开始执行AI新闻自动生成任务 - $(date)"

# 设置工作目录（使用绝对路径）
cd /home/taotao/Desktop/PythonProject/deepseek_ai_news_crew

# 激活Python环境（如果使用虚拟环境，取消下面的注释并修改路径）
source .venv/bin/activate

# 执行Python脚本
python3 auto_run_linux.py

# 记录运行日志
echo "$(date) - AI新闻日报生成完成" >> ai_news_run.log
echo "任务执行完成 - $(date)"
exit $? 