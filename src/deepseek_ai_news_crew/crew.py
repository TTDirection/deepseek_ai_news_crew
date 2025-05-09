from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from langchain_openai import ChatOpenAI
from .tools.custom_tool import NewsSearchTool, NewsFilterTool
import os
from dotenv import load_dotenv
# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

@CrewBase
class DeepseekAiNewsCrew():
    """DeepseekAiNewsCrew crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    def __init__(self):
        # 加载环境变量
        load_dotenv()
        
        # 设置搜索API类型和控制选项
        # 默认使用Google API，可在.env中设置SEARCH_API_TYPE为"google"、"bing"或"serper"
        search_api_type = os.getenv("SEARCH_API_TYPE", "google")
        os.environ["SEARCH_API_TYPE"] = search_api_type
        
        # 设置是否在输出中包含来源和链接，默认都包含
        # 可在.env中设置INCLUDE_SOURCE和INCLUDE_LINK为"true"或"false"
        include_source = os.getenv("INCLUDE_SOURCE", "true")
        include_link = os.getenv("INCLUDE_LINK", "true")
        os.environ["INCLUDE_SOURCE"] = include_source
        os.environ["INCLUDE_LINK"] = include_link
        
        # 设置是否验证URL，默认不验证以提高速度
        validate_urls = os.getenv("VALIDATE_URLS", "false")
        os.environ["VALIDATE_URLS"] = validate_urls
        
        # 设置 litellm 环境变量以指定 DeepSeek 提供者
        os.environ["LITELLM_PROVIDER"] = "deepseek"
        
        # 初始化研究员使用的 DeepSeek LLM
        self.researcher_llm = ChatOpenAI(
            model="deepseek/deepseek-chat",
            base_url="https://api.deepseek.com/v1",
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            temperature=0.3,
            model_kwargs={
                "system_message": "你是一个专注于AI技术新闻的研究员，擅长收集最新的AI相关新闻。你的回答简洁、准确、全面，并以简体中文输出。"
            }
        )
        
        # 初始化分析师使用的 DeepSeek LLM
        self.analyst_llm = ChatOpenAI(
            model="deepseek/deepseek-chat",
            base_url="https://api.deepseek.com/v1",
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            temperature=0.7,
            model_kwargs={
                "system_message": "你是一个以简体中文进行对话和输出的 AI 新闻分析师。你擅长提取关键信息，生成简洁清晰的摘要，并按重要性排序。所有回答和生成内容必须使用简体中文，语言自然、流畅，符合中文表达习惯。"
            }
        )
    
    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    
    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools
    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['researcher'], # type: ignore[index]
            tools=[NewsSearchTool(), NewsFilterTool()],
            llm=self.researcher_llm,
            verbose=True
        )

    @agent
    def analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['analyst'], # type: ignore[index]
            llm=self.analyst_llm,
            verbose=True
        )

    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config['research_task'], # type: ignore[index]
        )

    @task
    def analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config['analysis_task'], # type: ignore[index]
            output_file='ai_news_report.md'
        )

    @crew
    def crew(self) -> Crew:
        """Creates the DeepseekAiNewsCrew crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        # 定义AI相关关键词列表
        ai_keywords = [
            "openai", "anthropic", "gemini", "nvidia nim", "grok", "ollama", "watson",
            "bedrock", "azure", "cerebras", "sambanova", "deepseek", "qwen", "xAI",
            "文心一言", "豆包", "元宝",
            "人工智能", "机器学习", "深度学习", "生成式ai", "大语言模型", "神经网络",
            "计算机视觉", "自然语言处理", "强化学习", "多模态ai", "ai芯片",
            "量子计算", "自动驾驶"
        ]

        # 定义屏蔽关键词列表
        block_keywords = [
            "色情", "成人", "裸体", "性", "政治", "政府", "选举", "抗议", "违法", "毒品",
            "赌博", "邪教", "宗教", "恐怖主义", "暴力", "战争"
        ]

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            inputs={
                "ai_keywords": ai_keywords,
                "block_keywords": block_keywords
            }
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )
