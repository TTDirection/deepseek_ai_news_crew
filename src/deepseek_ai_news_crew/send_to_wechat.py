#!/usr/bin/env python
"""
发送AI新闻报告到企业微信

用法:
    python -m deepseek_ai_news_crew.send_to_wechat [报告文件路径] [MP3文件路径]

如果不指定报告文件路径，默认使用 Outputs/ai_news_report.md
如果不指定MP3文件路径，默认使用与报告同名的MP3文件
"""

import os
import sys
from dotenv import load_dotenv
from deepseek_ai_news_crew.tools.wechat_tool import WechatMessageTool

def send_report_to_wechat(report_path="Outputs/ai_news_report.md", mp3_path=None):
    """
    读取报告并发送到企业微信
    
    Args:
        report_path: 报告文件路径，默认为 Outputs/ai_news_report.md
        mp3_path: MP3文件路径，如果为None则尝试查找与报告同名的MP3文件
    """
    # 加载环境变量
    load_dotenv()
    
    # 检查INCLUDE_WECHAT环境变量
    include_wechat = os.getenv("INCLUDE_WECHAT", "false").lower() == "true"
    print(f"INCLUDE_WECHAT 配置: {include_wechat}")
    
    if not include_wechat:
        print("INCLUDE_WECHAT 设置为 false，跳过企业微信发送")
        return False
    
    # 检查文件是否存在
    if not os.path.exists(report_path):
        print(f"错误: 找不到报告文件 {report_path}")
        return False
    
    # 如果没有指定MP3文件，尝试使用同名的MP3文件
    if mp3_path is None:
        base_path = os.path.splitext(report_path)[0]
        mp3_path = f"{base_path}.mp3"
        print(f"未指定MP3文件，尝试使用: {mp3_path}")
    
    # 检查MP3文件是否存在
    has_mp3 = os.path.exists(mp3_path) if mp3_path else False
    if mp3_path and not has_mp3:
        print(f"警告: 找不到MP3文件 {mp3_path}，将只发送文本报告")
    
    try:
        # 读取报告内容
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 使用企业微信工具发送
        wechat_tool = WechatMessageTool()
        result = wechat_tool._run(content=content, mp3_file=mp3_path if has_mp3 else None)
        print(f"企业微信发送结果: {result}")
        return True
    except Exception as e:
        print(f"发送到企业微信时发生错误: {str(e)}")
        return False

def main():
    # 获取命令行参数
    mp3_path = None
    if len(sys.argv) > 2:
        report_path = sys.argv[1]
        mp3_path = sys.argv[2]
    elif len(sys.argv) > 1:
        report_path = sys.argv[1]
    else:
        report_path = "Outputs/ai_news_report.md"
    
    # 发送报告
    success = send_report_to_wechat(report_path, mp3_path)
    if success:
        print("报告已成功发送到企业微信")
    else:
        print("发送报告失败")
        sys.exit(1)

if __name__ == "__main__":
    main() 