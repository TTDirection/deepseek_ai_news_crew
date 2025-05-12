#!/usr/bin/env python
"""
自动运行AI新闻收集和发送脚本
每天早上9点自动运行，生成AI热点新闻报告并发送至企业微信
"""

import os
import sys
import subprocess
from datetime import datetime
from dotenv import load_dotenv

def main():
    """主函数，执行crewai并记录日志"""
    
    # 设置工作目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # 设置日志文件
    log_dir = os.path.join(script_dir, "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"ai_news_run_{current_time}.log")
    
    # 设置环境变量
    os.environ["INCLUDE_SOURCE"] = "false"
    os.environ["INCLUDE_LINK"] = "false"
    
    # 读取.env文件中的INCLUDE_WECHAT设置，如果没有则默认为false
    load_dotenv()
    include_wechat = os.getenv("INCLUDE_WECHAT", "false")
    # 记录当前设置
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"INCLUDE_WECHAT设置为: {include_wechat}\n")
    
    # 记录开始运行的时间
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"=== 开始运行时间: {current_time} ===\n")
    
    try:
        # 执行crewai命令
        print(f"开始生成AI新闻报告，日志文件: {log_file}")
        
        # 使用subprocess执行命令并捕获输出
        process = subprocess.Popen(
            ["crewai", "run"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        
        # 实时获取输出并同时写入日志
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(output)
        
        # 获取错误输出
        stderr_output = process.stderr.read()
        if stderr_output:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write("\n=== 错误输出 ===\n")
                f.write(stderr_output)
        
        # 记录结束时间和返回码
        with open(log_file, "a", encoding="utf-8") as f:
            end_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            f.write(f"\n=== 结束运行时间: {end_time} ===\n")
            f.write(f"返回码: {process.returncode}\n")
        
        return process.returncode
    
    except Exception as e:
        # 记录异常
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n=== 发生异常 ===\n{str(e)}\n")
        print(f"运行出错: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())