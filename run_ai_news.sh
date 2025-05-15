#!/bin/bash
echo "开始执行AI新闻自动生成任务 - $(date)"

# 切换到脚本所在目录
cd "$(dirname "$0")"

# 激活Python环境（如果使用虚拟环境，取消下面的注释并修改路径）
# source .venv/bin/activate

# 执行Python脚本
python3 auto_run.py

echo "任务执行完成 - $(date)"
exit $? 