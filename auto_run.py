#!/usr/bin/env python
"""
自动运行AI新闻收集和发送脚本
每天早上9点自动运行，生成AI热点新闻报告并发送至企业微信
"""

import os
import sys
import subprocess
import shutil
from datetime import datetime
from dotenv import load_dotenv
from text_to_speech import convert_text_to_speech
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv(override=True)

# 导入crew
from src.deepseek_ai_news_crew.crew import DeepseekAiNewsCrew

def send_to_wechat(report_file, mp3_file):
    """
    使用企业微信API直接发送文本和MP3文件
    
    Args:
        report_file: 报告文件路径
        mp3_file: MP3文件路径
    """
    try:
        # 读取报告内容
        with open(report_file, 'r', encoding='utf-8') as f:
            report_content = f.read()
        
        # 导入企业微信发送工具
        from src.deepseek_ai_news_crew.tools.wechat_tool import WechatMessageTool
        
        # 创建工具实例并发送
        wechat_tool = WechatMessageTool()
        result = wechat_tool._run(content=report_content, mp3_file=mp3_file)
        
        print(f"企业微信发送结果: {result}")
        return True
    except Exception as e:
        print(f"发送到企业微信失败: {str(e)}")
        return False

def main():
    print("\n=== 开始生成AI新闻日报 ===")
    print(f"当前工作目录: {os.getcwd()}")
    
    try:
        # 创建并运行crew
        crew = DeepseekAiNewsCrew()
        result = crew.crew().kickoff()
        print("\n=== AI新闻日报生成完成 ===")
        return result
    except Exception as e:
        print(f"\n错误: {str(e)}")
        import traceback
        print(f"错误详情:\n{traceback.format_exc()}")
        return None

if __name__ == "__main__":
    main()