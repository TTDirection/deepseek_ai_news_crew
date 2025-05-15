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
            
            # 检查关键配置
            important_vars = ["INCLUDE_WECHAT", "MIN_NEWS_SCORE", "RAW_SEARCH_COUNT", "MIN_NEWS_COUNT", "MAX_NEWS_COUNT"]
            for var in important_vars:
                for line in content.splitlines():
                    if line.strip().startswith(f"{var}="):
                        print(f"\n[.env] {var}设置: {line.strip()}")
                        break
                else:
                    print(f"\n[.env] 未找到{var}设置")
        except Exception as e:
            print(f"读取.env文件出错: {str(e)}")
    else:
        print("未找到.env文件")
    
    print_section("当前环境变量 (加载.env前)")
    include_wechat_before = os.environ.get("INCLUDE_WECHAT", "未设置")
    raw_search_count_before = os.environ.get("RAW_SEARCH_COUNT", "未设置")
    min_news_score_before = os.environ.get("MIN_NEWS_SCORE", "未设置")
    min_news_count_before = os.environ.get("MIN_NEWS_COUNT", "未设置")
    max_news_count_before = os.environ.get("MAX_NEWS_COUNT", "未设置")
    
    print(f"INCLUDE_WECHAT = {include_wechat_before}")
    print(f"RAW_SEARCH_COUNT = {raw_search_count_before}")
    print(f"MIN_NEWS_SCORE = {min_news_score_before}")
    print(f"MIN_NEWS_COUNT = {min_news_count_before}")
    print(f"MAX_NEWS_COUNT = {max_news_count_before}")
    
    print_section("加载.env文件")
    loaded = load_dotenv(dotenv_path=dotenv_path, override=True)
    print(f"加载结果: {'成功' if loaded else '失败 或 无变量更新'}")
    
    print_section("当前环境变量 (加载.env后)")
    include_wechat_after = os.environ.get("INCLUDE_WECHAT", "未设置")
    raw_search_count_after = os.environ.get("RAW_SEARCH_COUNT", "未设置")
    min_news_score_after = os.environ.get("MIN_NEWS_SCORE", "未设置")
    min_news_count_after = os.environ.get("MIN_NEWS_COUNT", "未设置")
    max_news_count_after = os.environ.get("MAX_NEWS_COUNT", "未设置")
    
    print(f"INCLUDE_WECHAT = {include_wechat_after}")
    print(f"RAW_SEARCH_COUNT = {raw_search_count_after}")
    print(f"MIN_NEWS_SCORE = {min_news_score_after}")
    print(f"MIN_NEWS_COUNT = {min_news_count_after}")
    print(f"MAX_NEWS_COUNT = {max_news_count_after}")
    
    # 检查是否有变化
    vars_to_check = [
        ("INCLUDE_WECHAT", include_wechat_before, include_wechat_after),
        ("RAW_SEARCH_COUNT", raw_search_count_before, raw_search_count_after),
        ("MIN_NEWS_SCORE", min_news_score_before, min_news_score_after),
        ("MIN_NEWS_COUNT", min_news_count_before, min_news_count_after),
        ("MAX_NEWS_COUNT", max_news_count_before, max_news_count_after)
    ]
    
    for name, before, after in vars_to_check:
        if before != after:
            print(f"\n环境变量 {name} 已更新: {before} -> {after}")
        else:
            print(f"\n环境变量 {name} 无变化，保持为: {after}")
    
    print_section("直接设置环境变量测试")
    os.environ["INCLUDE_WECHAT"] = "false"
    os.environ["RAW_SEARCH_COUNT"] = "50"
    print(f"直接设置后 INCLUDE_WECHAT = {os.environ.get('INCLUDE_WECHAT')}")
    print(f"直接设置后 RAW_SEARCH_COUNT = {os.environ.get('RAW_SEARCH_COUNT')}")
    
    # 验证环境变量处理逻辑
    print_section("环境变量处理逻辑验证")
    raw_value = os.environ.get("INCLUDE_WECHAT", "未设置")
    processed_value = raw_value.lower() == "true" if raw_value != "未设置" else False
    print(f"原始值: '{raw_value}'")
    print(f"处理后: {processed_value}")
    
    print("\n环境变量检查完成.")

if __name__ == "__main__":
    main() 