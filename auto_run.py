#!/usr/bin/env python
"""
自动运行AI新闻收集和发送脚本
每天早上9点自动运行，生成AI热点新闻报告并发送至企业微信
"""

import os
import sys
import subprocess
import shutil
import logging
from datetime import datetime
from dotenv import load_dotenv
from text_to_speech import convert_text_to_speech
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv(override=True)

# 设置日志记录
def setup_logging():
    # 创建logs目录
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # 生成日志文件名，格式：ai_news_YYMMDD_HHMMSS.log
    current_time = datetime.now().strftime("%y%m%d_%H%M%S")
    log_file = logs_dir / f"ai_news_{current_time}.log"
    
    # 创建日志记录器
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # 创建文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='w')
    file_handler.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器到记录器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # 记录初始信息
    logger.info("日志系统初始化完成")
    logger.info(f"日志文件路径: {log_file}")
    logger.info(f"当前工作目录: {os.getcwd()}")
    
    return logger

# 导入crew
from src.deepseek_ai_news_crew.crew import DeepseekAiNewsCrew

def send_to_wechat(report_file, mp3_file):
    """
    使用企业微信API直接发送文本和MP3文件
    
    Args:
        report_file: 报告文件路径
        mp3_file: MP3文件路径
    """
    logger = logging.getLogger(__name__)
    try:
        # 读取报告内容
        with open(report_file, 'r', encoding='utf-8') as f:
            report_content = f.read()
        
        # 导入企业微信发送工具
        from src.deepseek_ai_news_crew.tools.wechat_tool import WechatMessageTool
        
        # 创建工具实例并发送
        wechat_tool = WechatMessageTool()
        result = wechat_tool._run(content=report_content, mp3_file=mp3_file)
        
        logger.info(f"企业微信发送结果: {result}")
        return True
    except Exception as e:
        logger.error(f"发送到企业微信失败: {str(e)}")
        return False

def main():
    # 设置日志记录
    logger = setup_logging()
    
    logger.info("=== 开始生成AI新闻日报 ===")
    
    try:
        # 创建并运行crew
        crew = DeepseekAiNewsCrew()
        result = crew.crew().kickoff()
        logger.info("=== AI新闻日报生成完成 ===")
        return result
    except Exception as e:
        logger.error(f"错误: {str(e)}")
        import traceback
        logger.error(f"错误详情:\n{traceback.format_exc()}")
        return None

if __name__ == "__main__":
    main()