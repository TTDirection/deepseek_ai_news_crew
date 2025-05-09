#!/usr/bin/env python
import sys
import warnings
import os
from datetime import datetime, timedelta

from deepseek_ai_news_crew.crew import DeepseekAiNewsCrew

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run():
    """
    Run the crew.
    """
    # 获取当前日期和昨天日期
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    yesterday_9am = yesterday.replace(hour=9, minute=0, second=0, microsecond=0)
    today_9am = today.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # 读取环境变量
    include_source = os.getenv("INCLUDE_SOURCE", "true").lower() == "true"
    include_link = os.getenv("INCLUDE_LINK", "true").lower() == "true"
    
    inputs = {
        'topic': 'AI LLMs',
        'current_year': str(today.year),
        'today_date': today.strftime("%Y-%m-%d"),
        'yesterday_date': yesterday.strftime("%Y-%m-%d"),
        'today_time': today_9am.strftime("%H:%M:%S"),
        'yesterday_time': yesterday_9am.strftime("%H:%M:%S"),
        'time_range_start': yesterday_9am.strftime("%Y-%m-%d %H:%M:%S"),
        'time_range_end': today_9am.strftime("%Y-%m-%d %H:%M:%S"),
        'include_source': include_source,
        'include_link': include_link
    }
    
    try:
        DeepseekAiNewsCrew().crew().kickoff(inputs=inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


def train():
    """
    Train the crew for a given number of iterations.
    """
    # 获取当前日期和昨天日期
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    yesterday_9am = yesterday.replace(hour=9, minute=0, second=0, microsecond=0)
    today_9am = today.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # 读取环境变量
    include_source = os.getenv("INCLUDE_SOURCE", "true").lower() == "true"
    include_link = os.getenv("INCLUDE_LINK", "true").lower() == "true"
    
    inputs = {
        "topic": "AI LLMs",
        'current_year': str(today.year),
        'today_date': today.strftime("%Y-%m-%d"),
        'yesterday_date': yesterday.strftime("%Y-%m-%d"),
        'today_time': today_9am.strftime("%H:%M:%S"),
        'yesterday_time': yesterday_9am.strftime("%H:%M:%S"),
        'time_range_start': yesterday_9am.strftime("%Y-%m-%d %H:%M:%S"),
        'time_range_end': today_9am.strftime("%Y-%m-%d %H:%M:%S"),
        'include_source': include_source,
        'include_link': include_link
    }
    
    try:
        DeepseekAiNewsCrew().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        DeepseekAiNewsCrew().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    # 获取当前日期和昨天日期
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    yesterday_9am = yesterday.replace(hour=9, minute=0, second=0, microsecond=0)
    today_9am = today.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # 读取环境变量
    include_source = os.getenv("INCLUDE_SOURCE", "true").lower() == "true"
    include_link = os.getenv("INCLUDE_LINK", "true").lower() == "true"
    
    inputs = {
        "topic": "AI LLMs",
        'current_year': str(today.year),
        'today_date': today.strftime("%Y-%m-%d"),
        'yesterday_date': yesterday.strftime("%Y-%m-%d"),
        'today_time': today_9am.strftime("%H:%M:%S"),
        'yesterday_time': yesterday_9am.strftime("%H:%M:%S"),
        'time_range_start': yesterday_9am.strftime("%Y-%m-%d %H:%M:%S"),
        'time_range_end': today_9am.strftime("%Y-%m-%d %H:%M:%S"),
        'include_source': include_source,
        'include_link': include_link
    }
    
    try:
        DeepseekAiNewsCrew().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")
