#!/usr/bin/env python
"""
Linux系统专用的AI新闻收集和发送脚本
每天早上9点自动运行，生成AI热点新闻报告并发送至企业微信
"""

import os
import sys
import subprocess
import shutil
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv(override=True)

# 导入crew
from src.deepseek_ai_news_crew.crew import DeepseekAiNewsCrew

def send_to_wechat(report_file, audio_file=None):
    """
    使用企业微信API直接发送文本
    
    Args:
        report_file: 报告文件路径
        audio_file: 音频文件路径（可选）
    """
    try:
        # 读取报告内容
        with open(report_file, 'r', encoding='utf-8') as f:
            report_content = f.read()
        
        # 导入企业微信发送工具
        from src.deepseek_ai_news_crew.tools.wechat_tool import WechatMessageTool
        
        # 创建工具实例并发送
        wechat_tool = WechatMessageTool()
        # 注意：WechatMessageTool._run() 不接受 audio_file 参数
        result = wechat_tool._run(content=report_content)
        
        print(f"企业微信发送结果: {result}")
        return True
    except Exception as e:
        print(f"发送到企业微信失败: {str(e)}")
        import traceback
        print(f"错误详情:\n{traceback.format_exc()}")
        return False

def generate_audio(text_file, output_file):
    """
    生成语音文件
    
    Args:
        text_file: 文本文件路径
        output_file: 输出音频文件路径
    """
    try:
        # 导入语音转换模块
        from text_to_speech import convert_text_to_speech
        
        print(f"开始生成语音文件: {output_file}")
        convert_text_to_speech(text_file, output_file)
        print(f"语音文件生成完成: {output_file}")
        return True
    except Exception as e:
        print(f"生成语音文件失败: {str(e)}")
        import traceback
        print(f"错误详情:\n{traceback.format_exc()}")
        return False

def main():
    print("\n=== 开始生成AI新闻日报 (Linux版) ===")
    print(f"当前工作目录: {os.getcwd()}")
    
    try:
        # 使用与 crewai run 相同的方式运行
        # 方法1：使用 subprocess 调用 crewai run 命令
        try:
            print("使用 crewai run 命令运行...")
            result = subprocess.run(["crewai", "run"], check=True, capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print(f"警告: {result.stderr}")
        except subprocess.CalledProcessError as e:
            print(f"crewai run 命令执行失败: {e}")
            print(f"错误输出: {e.stderr}")
            
            # 如果命令执行失败，回退到原来的方式
            print("回退到直接调用方式...")
            crew = DeepseekAiNewsCrew()
            result = crew.crew().kickoff()
        except FileNotFoundError:
            # 如果找不到 crewai 命令，回退到原来的方式
            print("未找到 crewai 命令，回退到直接调用方式...")
            crew = DeepseekAiNewsCrew()
            result = crew.crew().kickoff()
            
        print("\n=== AI新闻日报生成完成 ===")
        
        # 生成当前日期字符串
        today_date = datetime.now().strftime("%Y%m%d")
        date_str = datetime.now().strftime("%Y年%m月%d日")
        
        # 定义报告文件和音频文件路径
        report_file = f"Outputs/ai_news_report_{today_date}.md"
        audio_file = f"Outputs/【AI日报】{date_str}.wav" 
        
        # 确保Outputs目录存在
        os.makedirs("Outputs", exist_ok=True)
        
        # 生成语音文件
        if os.path.exists(report_file):
            generate_audio(report_file, audio_file)
        else:
            print(f"报告文件不存在: {report_file}")
        
        # 发送到企业微信
        if os.path.exists(report_file):
            print("开始发送到企业微信...")
            send_to_wechat(report_file)
            print("企业微信发送完成")
        
        return result
    except Exception as e:
        print(f"\n错误: {str(e)}")
        import traceback
        print(f"错误详情:\n{traceback.format_exc()}")
        return None

if __name__ == "__main__":
    main()