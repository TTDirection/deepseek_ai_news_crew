from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task, before_kickoff, after_kickoff
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from langchain_openai import ChatOpenAI
from .tools.custom_tool import NewsSearchTool, NewsFilterTool, DiversityFilterTool
from .tools.wechat_tool import WechatMessageTool, MarkdownCleanerTool
from .analyst_config import ANALYST_SYSTEM_PROMPT
from .researcher_config import RESEARCHER_SYSTEM_PROMPT
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pathlib

# 添加辅助函数检查.env文件
def check_env_file():
    """检查.env文件是否存在且能正确加载"""
    env_path = pathlib.Path(".env")
    if not env_path.exists():
        print(f"警告: .env文件不存在于当前目录: {os.getcwd()}")
        return False
    
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(f".env文件存在，内容长度: {len(content)} 字符")
        
        # 检查INCLUDE_WECHAT设置
        for line in content.splitlines():
            if line.strip().startswith("INCLUDE_WECHAT="):
                print(f"在.env文件中找到设置: {line.strip()}")
                break
        else:
            print("警告: 在.env文件中未找到INCLUDE_WECHAT设置")
        
        return True
    except Exception as e:
        print(f"读取.env文件时出错: {str(e)}")
        return False

# 确保Outputs目录存在
def ensure_outputs_dir():
    """确保Outputs目录存在"""
    outputs_dir = pathlib.Path("Outputs")
    if not outputs_dir.exists():
        print(f"创建Outputs目录: {outputs_dir.absolute()}")
        outputs_dir.mkdir(parents=True, exist_ok=True)
    else:
        print(f"Outputs目录已存在: {outputs_dir.absolute()}")
    return outputs_dir.exists()

# 读取新闻评分和条数环境变量
def get_news_config():
    """读取并返回新闻配置"""
    # 从环境变量读取新闻评分和条数设置
    min_news_score = float(os.getenv("MIN_NEWS_SCORE", "6"))
    min_news_count = int(os.getenv("MIN_NEWS_COUNT", "5"))
    max_news_count = int(os.getenv("MAX_NEWS_COUNT", "20"))
    target_news_count = int(os.getenv("TARGET_NEWS_COUNT", "12"))
    raw_search_count = int(os.getenv("RAW_SEARCH_COUNT", "30"))
    
    return {
        "min_news_score": min_news_score,
        "min_news_count": min_news_count,
        "max_news_count": max_news_count,
        "target_news_count": target_news_count,
        "raw_search_count": raw_search_count
    }

@CrewBase
class DeepseekAiNewsCrew():
    """DeepseekAiNewsCrew crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    def __init__(self):
        # 加载环境变量前检查.env文件
        print("\n=== 初始化配置 ===")
        print(f"当前工作目录: {os.getcwd()}")
        check_env_file()
        
        # 确保Outputs目录存在
        ensure_outputs_dir()
        
        # 检查环境变量加载前的状态
        include_wechat_before = os.environ.get("INCLUDE_WECHAT", "未设置")
        print(f"加载环境变量前 INCLUDE_WECHAT = {include_wechat_before}")
        
        # 加载环境变量
        load_dotenv(override=True)
        
        # 检查环境变量加载后的状态
        include_wechat_after_load = os.environ.get("INCLUDE_WECHAT", "未设置")
        print(f"加载环境变量后 INCLUDE_WECHAT = {include_wechat_after_load}")
        
        # 获取配置
        config = get_news_config()
        print("新闻评分和条数设置:")
        for key, value in config.items():
            print(f"- {key}: {value}")
        
        # 设置搜索API类型和控制选项
        # 默认使用Google API，可在.env中设置SEARCH_API_TYPE为"google"、"bing"或"serper"
        search_api_type = os.getenv("SEARCH_API_TYPE", "google")
        os.environ["SEARCH_API_TYPE"] = search_api_type
        
        # 设置原始搜索数量
        raw_search_count = os.getenv("RAW_SEARCH_COUNT", "30")
        os.environ["RAW_SEARCH_COUNT"] = raw_search_count
        
        # 设置是否在输出中包含来源和链接，默认都包含
        # 可在.env中设置INCLUDE_SOURCE和INCLUDE_LINK为"true"或"false"
        include_source = os.getenv("INCLUDE_SOURCE", "true")
        include_link = os.getenv("INCLUDE_LINK", "true")
        os.environ["INCLUDE_SOURCE"] = include_source
        os.environ["INCLUDE_LINK"] = include_link
        
        # 设置是否发送到企业微信
        include_wechat_raw = os.getenv("INCLUDE_WECHAT", "false")
        print(f"读取到的INCLUDE_WECHAT原始值: '{include_wechat_raw}'")
        self.include_wechat = include_wechat_raw.lower() == "true"
        print(f"INCLUDE_WECHAT配置解析结果: {self.include_wechat}")
        
        # 强制将环境变量设置为与配置一致的值
        os.environ["INCLUDE_WECHAT"] = str(self.include_wechat).lower()
        print(f"环境变量INCLUDE_WECHAT已设置为: {os.environ['INCLUDE_WECHAT']}")
        
        # 企业微信webhook key
        self.wechat_webhook_key = os.getenv("WECHAT_WEBHOOK_KEY", "8b529e9f-1dc9-4b5c-a60a-1b8d3298acdd")
        os.environ["WECHAT_WEBHOOK_KEY"] = self.wechat_webhook_key
        
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
                "system_message": RESEARCHER_SYSTEM_PROMPT
            }
        )
        
        # 初始化分析师使用的 DeepSeek LLM
        self.analyst_llm = ChatOpenAI(
            model="deepseek/deepseek-chat",
            base_url="https://api.deepseek.com/v1",
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            temperature=0.7,
            model_kwargs={
                "system_message": ANALYST_SYSTEM_PROMPT
            }
        )
    
    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['researcher'], # type: ignore[index]
            tools=[NewsSearchTool(), NewsFilterTool(), DiversityFilterTool()],
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
        # 获取当前日期，用于文件名
        today_str = datetime.now().strftime("%Y%m%d")
        output_file = f"Outputs/raw_news_data_{today_str}.json"
        
        return Task(
            config=self.tasks_config['research_task'], # type: ignore[index]
            output_file=output_file
        )

    @task
    def analysis_task(self) -> Task:
        # 获取当前日期，用于文件名
        today_str = datetime.now().strftime("%Y%m%d")
        output_file = f"Outputs/ai_news_report_{today_str}.md"
        
        return Task(
            config=self.tasks_config['analysis_task'], # type: ignore[index]
            output_file=output_file
        )
    
    @after_kickoff
    def send_to_wechat(self, result):
        """
        在执行完所有任务后，强制将结果发送到企业微信
        
        Args:
            result: Crew执行的结果
        """
        print("\n=== 企业微信发送流程 ===")
        
        # 确保环境变量与.env文件同步
        reload_env_result = load_dotenv(override=True)
        print(f"重新加载.env文件: {'成功' if reload_env_result else '无变化'}")
        
        # 每次执行时重新从环境变量读取INCLUDE_WECHAT设置
        include_wechat_raw = os.getenv("INCLUDE_WECHAT", "false")
        print(f"读取到的INCLUDE_WECHAT原始值: '{include_wechat_raw}'")
        include_wechat = include_wechat_raw.lower() == "true"
        print(f"INCLUDE_WECHAT配置解析结果: {include_wechat}")
        
        # 强制将环境变量设置为.env文件中的值
        os.environ["INCLUDE_WECHAT"] = include_wechat_raw
        print(f"环境变量INCLUDE_WECHAT已设置为: {os.environ['INCLUDE_WECHAT']}")
    
        # 检查是否需要发送到企业微信
        if not include_wechat:
            print("INCLUDE_WECHAT 设置为 false，跳过企业微信发送")
            print("=== 企业微信发送流程结束 ===\n")
            return result

        try:
            # 获取当前日期，用于文件名
            today = datetime.now()
            today_str = today.strftime("%Y%m%d")
            report_path = f"Outputs/ai_news_report_{today_str}.md"
            print(f"尝试读取报告文件: {report_path}")
            
            # 检查文件是否存在
            report_file = pathlib.Path(report_path)
            if not report_file.exists():
                print(f"错误: 无法找到报告文件: {report_path}")
                print(f"绝对路径: {report_file.absolute()}")
                
                # 检查Outputs目录是否存在及其内容
                outputs_dir = pathlib.Path("Outputs")
                if outputs_dir.exists():
                    print(f"Outputs目录存在于: {outputs_dir.absolute()}")
                    files = list(outputs_dir.glob("*"))
                    if files:
                        print(f"Outputs目录中的文件: {[f.name for f in files]}")
                    else:
                        print("Outputs目录为空")
                else:
                    print(f"Outputs目录不存在于: {outputs_dir.absolute()}")
                
                print("=== 企业微信发送流程结束 ===\n")
                return result
            
            # 文件存在，继续处理
            with open(report_path, "r", encoding="utf-8") as f:
                content = f.read()
            print(f"成功读取报告文件，内容长度: {len(content)} 字符")
            
            # 使用企业微信工具发送
            wechat_tool = WechatMessageTool()
            print("正在发送到企业微信...")
            
            # 发送文本内容
            text_result = wechat_tool._run(content=content, webhook_key=self.wechat_webhook_key)
            print(f"企业微信文本发送结果: {text_result}")
            
            # 生成并发送音频文件
            try:
                # 生成音频文件
                from text2voice_BytedanceTTS import BytedanceTTS
                tts = BytedanceTTS()
                audio_file = f"Outputs/ai_news_report_{today_str}.wav"
                output_path = tts.generate(content, output_file=audio_file)
                
                if output_path and os.path.exists(output_path):
                    print(f"成功生成音频文件: {output_path}")
                    # 发送音频文件
                    audio_result = wechat_tool._run(content=content, webhook_key=self.wechat_webhook_key, audio_file=output_path)
                    print(f"企业微信音频发送结果: {audio_result}")
                else:
                    print("音频文件生成失败")
            except Exception as e:
                print(f"生成或发送音频文件时发生错误: {str(e)}")
                import traceback
                print(f"错误详情: {traceback.format_exc()}")
            
        except Exception as e:
            print(f"发送到企业微信时发生错误: {str(e)}")
            import traceback
            print(f"错误详情: {traceback.format_exc()}")
        
        print("=== 企业微信发送流程结束 ===\n")
        # 返回原始结果
        return result

    @crew
    def crew(self) -> Crew:
        """Creates the DeepseekAiNewsCrew crew"""
        # 获取当前日期和时间
        now = datetime.now()
        today = now.date()
        
        # 设置时间范围：从昨天早上9点到当前时间
        yesterday_9am = datetime.combine(today - timedelta(days=1), datetime.min.time().replace(hour=9))
        current_time = now
        
        # 格式化日期字符串
        today_str = today.strftime("%Y-%m-%d")
        yesterday_str = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # 定义AI相关关键词列表，按类别组织
        ai_keywords = {
            "大模型": [
                # 国际大模型公司
                "openai", "chatgpt", "gpt-4", "gpt-5", "sora", "dall-e",
                "anthropic", "claude", "claude 3",
                "google ai", "gemini", "gemini ultra", "gemini pro",
                "xai", "grok", "grok-1",
                "meta ai", "llama", "llama 3",
                "mistral ai", "mixtral",
                # 国内大模型公司
                "百度文心", "文心一言", "ernie",
                "阿里通义", "通义千问", "qwen",
                "讯飞星火", "星火认知",
                "智谱ai", "chatglm",
                "deepseek", "360 ai", "抖音 ai"
            ],
            "AI基础设施": [
                # 国际基础设施
                "nvidia", "nvidia h200", "blackwell", "cuda",
                "amd ai", "intel ai", "tpu", "aws", "azure ai",
                "databricks", "hugging face", "ollama", "replicate",
                # 量子计算
                "quantum ai", "quantum computing", "ibm quantum",
                # 国内基础设施
                "摩尔线程", "沐曦", "燧原科技", "澜起科技",
                "智源研究院", "商汤科技"
            ],
            "AI应用": [
                # 通用领域
                "ai agent", "ai assistant", "ai coding",
                "multimodal ai", "ai vision", "computer vision",
                "speech recognition", "voice ai", "ai translation",
                # 垂直领域
                "autonomous driving", "self-driving", "robotics",
                "ai healthcare", "ai education", "ai gaming",
                "ai security", "ai finance", "generative ai",
                # 新兴应用
                "ai video", "ai music", "ai design",
                "ai writing", "ai analytics"
            ],
            "AI研究": [
                # 研究机构
                "deepmind", "microsoft research", "google research",
                "stanford ai", "mit ai", "berkeley ai",
                "清华ai", "北大ai", "中科院ai",
                # 研究领域
                "machine learning", "deep learning", "neural networks",
                "reinforcement learning", "nlp", "computer vision",
                "ai ethics", "ai safety", "ai alignment",
                "multimodal learning", "few-shot learning",
                "ai research", "ai paper", "ai breakthrough"
            ]
        }

        # 定义屏蔽关键词列表
        block_keywords = [
            "色情", "成人", "裸体", "性", "政治", "政府", "选举", "抗议", 
            "违法", "毒品", "赌博", "邪教", "宗教", "恐怖主义", "暴力", 
            "战争", "谣言", "虚假信息"
        ]

        # 获取配置
        news_config = get_news_config()

        # 新闻评分标准
        news_scoring = {
            "importance_weight": 0.35,    # 重要性权重
            "relevance_weight": 0.35,     # 相关性权重
            "geo_balance_weight": 0.30,   # 地域平衡权重
            "min_score": news_config["min_news_score"],  # 最低分数要求（满分10分）
            "international_ratio": 0.55,  # 国际新闻比例要求
            "min_news_count": news_config["min_news_count"],    # 最少新闻条数
            "max_news_count": news_config["max_news_count"],    # 最多新闻条数
            "target_news_count": news_config["target_news_count"],  # 目标新闻条数
            "scoring_criteria": {
                "importance": {
                    "global_breakthrough": 10,  # 全球性突破
                    "regional_breakthrough": 9,  # 区域性突破
                    "major_update": 8,          # 重要更新
                    "product_release": 7,       # 产品发布
                    "general_progress": 6       # 一般进展
                },
                "relevance": {
                    "core_tech": 10,      # 核心技术
                    "commercial": 9,      # 商业落地
                    "tech_innovation": 8, # 技术创新
                    "infrastructure": 7,  # 基础设施
                    "ecosystem": 6        # 生态发展
                },
                "geo_balance": {
                    "international": {
                        "global_leader": 10,    # 全球领先
                        "regional_leader": 9,   # 区域领先
                        "innovative_company": 8, # 创新企业
                        "research_inst": 7      # 研究机构
                    },
                    "domestic": {
                        "industry_leader": 10,  # 行业领军
                        "innovative_company": 9, # 创新企业
                        "research_inst": 8,     # 研究机构
                        "industry_application": 7 # 产业应用
                    }
                }
            }
        }

        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            inputs={
                "ai_keywords": ai_keywords,
                "block_keywords": block_keywords,
                "today_date": today_str,
                "yesterday_date": yesterday_str,
                "time_range_start": yesterday_9am.strftime("%Y-%m-%d %H:%M:%S"),
                "time_range_end": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                "include_source": os.getenv("INCLUDE_SOURCE", "true").lower() == "true",
                "include_link": os.getenv("INCLUDE_LINK", "true").lower() == "true",
                "news_scoring": news_scoring
            }
        )
