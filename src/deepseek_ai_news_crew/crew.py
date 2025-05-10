from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task, before_kickoff, after_kickoff
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from langchain_openai import ChatOpenAI
from .tools.custom_tool import NewsSearchTool, NewsFilterTool
from .tools.wechat_tool import WechatMessageTool, MarkdownCleanerTool
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

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
        
        # 设置是否发送到企业微信
        include_wechat = os.getenv("INCLUDE_WECHAT", "false")
        os.environ["INCLUDE_WECHAT"] = include_wechat
        
        # 企业微信webhook key
        wechat_webhook_key = os.getenv("WECHAT_WEBHOOK_KEY", "8b529e9f-1dc9-4b5c-a60a-1b8d3298acdd")
        os.environ["WECHAT_WEBHOOK_KEY"] = wechat_webhook_key
        
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
                "system_message": """你是一个以简体中文进行对话和输出的 AI 新闻分析师。

你的任务是为每日AI热点新闻生成高质量的摘要报告，要求如下：
1. 确保报告标题使用当前日期（而非过去日期），格式为"【AI日报】YYYY-MM-DD AI热点新闻"
2. 只关注过去24小时内（昨天早上9点到今天早上9点）的AI新闻
3. 为每条新闻生成详细的摘要分析，不少于150字，包含核心要点、技术细节和潜在影响
4. 摘要应该全面、客观，即使原文摘要简短，也要基于上下文和你的知识进行合理扩展
5. 严格遵循环境变量设置：
   - 若INCLUDE_SOURCE=false，则你绝对不能在报告中包含任何来源信息，包括不要添加"来源"、"出处"或类似字段
   - 若INCLUDE_LINK=false，则你绝对不能在报告中包含任何链接信息，包括不要添加URL、网址或任何可点击链接
   - 当这些信息被禁用时，你必须调整报告格式，确保格式美观、可读性良好
   - 具体而言，当INCLUDE_SOURCE=false时，不要显示"来源: [网站名]"这一行
   - 当INCLUDE_LINK=false时，不要在网站名后附加链接
6. 不要在输出的开头和结尾添加```markdown和```标记
7. 如果环境变量INCLUDE_SOURCE和INCLUDE_LINK都设置为false，你的每条新闻报告格式应该是：
   
   ## 序号. 标题
   **摘要**: 详细摘要内容
   **技术细节**: 技术细节内容
   **潜在影响**: 潜在影响分析
   **发布时间**: 相对时间

所有回答和生成内容必须使用简体中文，语言自然、流畅，符合中文表达习惯。"""
            }
        )
    
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
            tools=[MarkdownCleanerTool()],
            llm=self.analyst_llm,
            verbose=True
        )

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
    
    @after_kickoff
    def send_to_wechat(self, result):
        """
        在执行完所有任务后，根据配置将结果发送到企业微信
        
        Args:
            result: Crew执行的结果
        """
        include_wechat = os.getenv("INCLUDE_WECHAT", "false").lower() == "true"
        if include_wechat:
            try:
                # 读取生成的AI日报
                report_path = "ai_news_report.md"
                if os.path.exists(report_path):
                    with open(report_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # 使用企业微信工具发送
                    wechat_tool = WechatMessageTool()
                    result = wechat_tool._run(content=content)
                    print(f"企业微信发送结果: {result}")
                else:
                    print(f"无法找到报告文件: {report_path}")
            except Exception as e:
                print(f"发送到企业微信时发生错误: {str(e)}")
        
        # 返回原始结果
        return result

    @crew
    def crew(self) -> Crew:
        """Creates the DeepseekAiNewsCrew crew"""
        # 获取当前日期和昨天日期用于时间范围
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        yesterday_9am = yesterday.replace(hour=9, minute=0, second=0, microsecond=0)
        today_9am = today.replace(hour=9, minute=0, second=0, microsecond=0)

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
                "block_keywords": block_keywords,
                "today_date": today.strftime("%Y-%m-%d"),
                "yesterday_date": yesterday.strftime("%Y-%m-%d"),
                "time_range_start": yesterday_9am.strftime("%Y-%m-%d %H:%M:%S"),
                "time_range_end": today_9am.strftime("%Y-%m-%d %H:%M:%S"),
                "include_source": os.getenv("INCLUDE_SOURCE", "true").lower() == "true",
                "include_link": os.getenv("INCLUDE_LINK", "true").lower() == "true"
            }
        )
