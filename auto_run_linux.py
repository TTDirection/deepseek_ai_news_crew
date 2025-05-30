#!/usr/bin/env python
"""
Linux系统专用的AI新闻收集和发送脚本
每天早上9点自动运行，生成AI热点新闻报告并发送至企业微信
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv(override=True)

def main():
    print("\n=== 开始生成AI新闻日报 (Linux版) ===")
    print(f"当前工作目录: {os.getcwd()}")
    
    try:
        # 使用 crewai run 命令运行
        print("使用 crewai run 命令运行...")
        result = subprocess.run(["crewai", "run"], check=True, capture_output=True, text=True)
        
        # 打印输出
        print(result.stdout)
        if result.stderr:
            print(f"警告: {result.stderr}")
            
        print("\n=== AI新闻日报生成完成 ===")
        return result
        
    except subprocess.CalledProcessError as e:
        print(f"crewai run 命令执行失败: {e}")
        print(f"错误输出: {e.stderr}")
        return None
    except FileNotFoundError:
        print("错误: 未找到 crewai 命令，请确保已正确安装 crewai")
        return None
    except Exception as e:
        print(f"\n错误: {str(e)}")
        import traceback
        print(f"错误详情:\n{traceback.format_exc()}")
        return None

if __name__ == "__main__":
    main()