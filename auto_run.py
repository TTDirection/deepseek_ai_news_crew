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
    """主函数，执行crewai并记录日志"""
    
    # 设置工作目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # 设置日志文件
    log_dir = os.path.join(script_dir, "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    today_date = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"ai_news_run_{current_time}.log")
    
    # 读取并设置环境变量
    load_dotenv(override=True)  # 加载.env文件
    
    # 强制设置某些环境变量，覆盖.env文件的值
    override_vars = {
        "INCLUDE_SOURCE": "false",
        "INCLUDE_LINK": "false",
        "RAW_SEARCH_COUNT": "30",
        "MIN_NEWS_COUNT": "7",
        "MAX_NEWS_COUNT": "15",
        "TARGET_NEWS_COUNT": "10"
    }
    
    # 应用覆盖值
    for key, value in override_vars.items():
        os.environ[key] = value
        print(f"覆盖环境变量: {key}={value}")
    
    # 读取INCLUDE_WECHAT设置，不覆盖它
    include_wechat = os.getenv("INCLUDE_WECHAT", "false")
    print(f"保留环境变量: INCLUDE_WECHAT={include_wechat}")
    
    # 记录环境变量设置
    with open(log_file, "a", encoding="utf-8") as f:
        for key, value in override_vars.items():
            f.write(f"{key}设置为: {value}\n")
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
            encoding="utf-8",
            env=dict(os.environ, PYTHONIOENCODING="utf-8")
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
        
        # 处理输出文件 - 复制并重命名带日期的版本
        outputs_dir = os.path.join(script_dir, "Outputs")
        if not os.path.exists(outputs_dir):
            os.makedirs(outputs_dir)
        
        # 原始文件路径
        original_report_file = os.path.join(outputs_dir, "ai_news_report.md")
        original_data_file = os.path.join(outputs_dir, "raw_news_data.json")
        
        # 带日期的目标文件路径
        dated_report_file = os.path.join(outputs_dir, f"ai_news_report_{today_date}.md")
        dated_data_file = os.path.join(outputs_dir, f"raw_news_data_{today_date}.json")
        dated_mp3_file = os.path.join(outputs_dir, f"ai_news_report_{today_date}.mp3")
        
        # 复制文件并记录到日志
        with open(log_file, "a", encoding="utf-8") as f:
            if os.path.exists(original_report_file):
                shutil.copy2(original_report_file, dated_report_file)
                f.write(f"生成报告文件: {dated_report_file}\n")
                
                # 生成语音文件
                try:
                    f.write(f"开始生成语音文件...\n")
                    # 检查gtts是否已安装
                    try:
                        import gtts
                        f.write("gtts包已安装\n")
                    except ImportError:
                        f.write("错误: gtts包未安装，尝试安装...\n")
                        subprocess.check_call([sys.executable, "-m", "pip", "install", "gtts"])
                        f.write("gtts包安装完成\n")
                    
                    # 确保输出目录存在
                    if not os.path.exists(outputs_dir):
                        os.makedirs(outputs_dir)
                        f.write(f"创建输出目录: {outputs_dir}\n")
                    
                    # 生成MP3文件
                    success = convert_text_to_speech(dated_report_file, dated_mp3_file)
                    if success:
                        f.write(f"成功生成语音文件: {dated_mp3_file}\n")
                        
                        # 发送到企业微信
                        if include_wechat.lower() == "true":
                            f.write(f"开始发送到企业微信...\n")
                            send_success = send_to_wechat(dated_report_file, dated_mp3_file)
                            if send_success:
                                f.write(f"成功发送到企业微信\n")
                            else:
                                f.write(f"发送到企业微信失败\n")
                        else:
                            f.write(f"INCLUDE_WECHAT设置为{include_wechat}，跳过企业微信发送\n")
                    else:
                        f.write(f"生成语音文件失败\n")
                except Exception as e:
                    f.write(f"生成语音文件或发送到企业微信时出错: {str(e)}\n")
                    print(f"错误: {str(e)}")
            else:
                f.write(f"警告: 未找到报告文件 {original_report_file}\n")
                
            if os.path.exists(original_data_file):
                shutil.copy2(original_data_file, dated_data_file)
                f.write(f"生成数据文件: {dated_data_file}\n")
            else:
                f.write(f"警告: 未找到数据文件 {original_data_file}\n")
        
        return process.returncode
    
    except Exception as e:
        # 记录异常
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n=== 发生异常 ===\n{str(e)}\n")
        print(f"运行出错: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())