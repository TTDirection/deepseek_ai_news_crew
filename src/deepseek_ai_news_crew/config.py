"""
配置处理模块，用于处理和应用配置
"""
import os
import yaml
import pathlib
from string import Template

def load_env_vars():
    """加载并返回环境变量"""
    # 从环境变量读取新闻评分和条数设置
    min_news_score = float(os.getenv("MIN_NEWS_SCORE", "6"))
    min_news_count = int(os.getenv("MIN_NEWS_COUNT", "5"))
    max_news_count = int(os.getenv("MAX_NEWS_COUNT", "20"))
    target_news_count = int(os.getenv("TARGET_NEWS_COUNT", "12"))
    
    return {
        "min_news_score": min_news_score,
        "min_news_count": min_news_count,
        "max_news_count": max_news_count,
        "target_news_count": target_news_count
    }

def apply_config_to_templates():
    """将环境变量配置应用到任务模板"""
    env_vars = load_env_vars()
    
    # 任务配置文件路径
    config_dir = pathlib.Path(__file__).parent / "config"
    tasks_yaml_path = config_dir / "tasks.yaml"
    
    # 读取tasks.yaml文件
    try:
        with open(tasks_yaml_path, "r", encoding="utf-8") as f:
            tasks_yaml = f.read()
        
        # 替换占位符
        template = Template(tasks_yaml)
        updated_yaml = template.safe_substitute(
            min_news_count=env_vars["min_news_count"],
            max_news_count=env_vars["max_news_count"],
            target_news_count=env_vars["target_news_count"]
        )
        
        # 写回文件
        with open(tasks_yaml_path, "w", encoding="utf-8") as f:
            f.write(updated_yaml)
        
        print(f"已应用配置到任务模板: {tasks_yaml_path}")
        return True
    except Exception as e:
        print(f"应用配置到任务模板时出错: {str(e)}")
        return False

def get_config():
    """返回当前配置"""
    return load_env_vars()

if __name__ == "__main__":
    # 测试配置加载和应用
    config = get_config()
    print("当前配置:")
    for key, value in config.items():
        print(f"- {key}: {value}")
    
    result = apply_config_to_templates()
    print(f"应用配置结果: {'成功' if result else '失败'}") 