#!/usr/bin/env python
"""
环境变量检查工具，用于诊断环境变量加载问题
"""

import os
import sys
from dotenv import load_dotenv, find_dotenv

def print_section(title):
    """打印带分隔符的标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def main():
    """检查环境变量加载情况"""
    print_section("当前工作目录和Python路径")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"Python 路径: {sys.executable}")
    
    print_section("检查.env文件")
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        print(f"找到.env文件: {dotenv_path}")
        try:
            with open(dotenv_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            print(f"文件内容 ({len(content)} 字符):\n{content}")
            
            # 检查INCLUDE_WECHAT配置
            for line in content.splitlines():
                if line.strip().startswith("INCLUDE_WECHAT="):
                    print(f"\n[.env] INCLUDE_WECHAT设置: {line.strip()}")
                    break
            else:
                print("\n[.env] 未找到INCLUDE_WECHAT设置")
        except Exception as e:
            print(f"读取.env文件出错: {str(e)}")
    else:
        print("未找到.env文件")
    
    print_section("当前环境变量 (加载.env前)")
    include_wechat_before = os.environ.get("INCLUDE_WECHAT", "未设置")
    print(f"INCLUDE_WECHAT = {include_wechat_before}")
    
    print_section("加载.env文件")
    loaded = load_dotenv(dotenv_path=dotenv_path, override=True)
    print(f"加载结果: {'成功' if loaded else '失败 或 无变量更新'}")
    
    print_section("当前环境变量 (加载.env后)")
    include_wechat_after = os.environ.get("INCLUDE_WECHAT", "未设置")
    print(f"INCLUDE_WECHAT = {include_wechat_after}")
    
    # 检查是否有变化
    if include_wechat_before != include_wechat_after:
        print(f"\n环境变量已更新: {include_wechat_before} -> {include_wechat_after}")
    else:
        print(f"\n环境变量无变化，保持为: {include_wechat_after}")
    
    print_section("直接设置环境变量测试")
    os.environ["INCLUDE_WECHAT"] = "false"
    print(f"直接设置后 INCLUDE_WECHAT = {os.environ.get('INCLUDE_WECHAT')}")
    
    # 验证环境变量处理逻辑
    print_section("环境变量处理逻辑验证")
    raw_value = os.environ.get("INCLUDE_WECHAT", "未设置")
    processed_value = raw_value.lower() == "true" if raw_value != "未设置" else False
    print(f"原始值: '{raw_value}'")
    print(f"处理后: {processed_value}")
    
    print("\n环境变量检查完成.")

if __name__ == "__main__":
    main() 