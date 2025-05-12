from crewai.tools import BaseTool
from typing import Type, List, Optional
from pydantic import BaseModel, Field
import requests
import os
from datetime import datetime, timedelta
import json
import re
from urllib.parse import urlparse

class WebSearchInput(BaseModel):
    """Input schema for WebSearchTool."""
    query: str = Field(..., description="搜索关键词")
    time_range: Optional[str] = Field(None, description="时间范围，例如：'1d'表示过去一天")
    max_results: Optional[int] = Field(10, description="返回结果的最大数量")

class NewsSearchTool(BaseTool):
    name: str = "网络新闻搜索工具"
    description: str = (
        "使用此工具搜索互联网上与AI相关的新闻。可以指定关键词、时间范围和结果数量。"
        "默认搜索过去24小时的新闻。"
    )
    args_schema: Type[BaseModel] = WebSearchInput

    def _run(self, query: str, time_range: Optional[str] = None, max_results: Optional[int] = 10) -> str:
        try:
            # 从环境变量中读取搜索API配置
            api_key = os.getenv("SEARCH_API_KEY")
            # 尝试从SERPER_API_KEY获取（如果SEARCH_API_KEY不存在且使用的是serper）
            search_api_type = os.getenv("SEARCH_API_TYPE", "google").lower()  # 默认使用Google API
            if not api_key and search_api_type == "serper":
                api_key = os.getenv("SERPER_API_KEY")
            
            cx = os.getenv("SEARCH_ENGINE_ID")
            
            # 根据API类型决定是否需要检查search_engine_id
            if search_api_type == "google":
                if not api_key or not cx:
                    return "搜索API配置不完整，使用Google搜索时请设置SEARCH_API_KEY和SEARCH_ENGINE_ID环境变量。"
            else:
                # Bing和Serper API只需要API_KEY
                if not api_key:
                    return f"搜索API配置不完整，使用{search_api_type}搜索时请设置SEARCH_API_KEY环境变量。"
                             
            # 计算时间范围
            if not time_range:
                # 默认为过去24小时
                yesterday = datetime.now() - timedelta(days=1)
                date_str = yesterday.strftime("%Y-%m-%d")
            else:
                # 解析time_range
                days = int(time_range.replace('d', ''))
                past_date = datetime.now() - timedelta(days=days)
                date_str = past_date.strftime("%Y-%m-%d")
            
            # 根据API类型选择搜索方法
            if search_api_type.lower() == "google":
                results = self._search_with_google(query, api_key, cx, time_range, max_results)
            elif search_api_type.lower() == "bing":
                results = self._search_with_bing(query, api_key, time_range, max_results)
            elif search_api_type.lower() == "serper":
                results = self._search_with_serper(query, api_key, time_range, max_results)
            else:
                return f"不支持的搜索API类型: {search_api_type}"
            
            # 检查是否有结果
            if not results:
                return "没有找到相关的新闻结果。"
                
            return json.dumps(results, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return f"搜索过程中发生错误: {str(e)}"
    
    def _search_with_google(self, query, api_key, cx, time_range, max_results):
        """使用Google Custom Search API进行搜索"""
        url = "https://www.googleapis.com/customsearch/v1"
        
        # 添加news关键词以偏向于新闻结果
        search_query = f"{query} news"
        
        params = {
            "key": api_key,
            "cx": cx,
            "q": search_query,
            "dateRestrict": f"d{time_range.replace('d', '')}" if time_range else "d1",
            "num": min(max_results, 10)  # Google API限制最多10条结果
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            raise Exception(f"搜索请求失败: {response.status_code} - {response.text}")
        
        # 解析结果
        results = response.json()
        items = results.get("items", [])
        
        # 格式化结果
        formatted_results = []
        for item in items:
            title = item.get("title", "无标题")
            link = item.get("link", "")
            snippet = item.get("snippet", "无摘要")
            
            # 提取来源网站
            source = item.get("displayLink", "")
            if not source:
                parsed_url = urlparse(link)
                source = parsed_url.netloc
            
            # 尝试提取发布日期
            pub_date = "未知"
            if "pagemap" in item and "metatags" in item["pagemap"]:
                metatags = item["pagemap"]["metatags"][0]
                for date_tag in ["article:published_time", "date", "og:published_time", "datePublished"]:
                    if date_tag in metatags:
                        pub_date = metatags[date_tag]
                        break
            
            # 验证链接是否有效
            is_valid = self._validate_url(link)
            
            if is_valid:
                formatted_result = {
                    "标题": title,
                    "链接": link,
                    "摘要": snippet,
                    "来源": source,
                    "发布时间": pub_date
                }
                
                formatted_results.append(formatted_result)
        
        return formatted_results
    
    def _search_with_bing(self, query, api_key, time_range, max_results):
        """使用Bing News Search API进行搜索"""
        url = "https://api.bing.microsoft.com/v7.0/news/search"
        
        # 计算时间范围（Bing使用不同的格式）
        if time_range:
            days = int(time_range.replace('d', ''))
            freshness = f"Day-{days}"
        else:
            freshness = "Day-1"
        
        headers = {"Ocp-Apim-Subscription-Key": api_key}
        params = {
            "q": query,
            "count": min(max_results, 50),  # Bing允许最多50条结果
            "freshness": freshness,
            "textFormat": "Raw"
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            raise Exception(f"搜索请求失败: {response.status_code} - {response.text}")
        
        data = response.json()
        items = data.get("value", [])
        
        formatted_results = []
        for item in items:
            title = item.get("name", "无标题")
            link = item.get("url", "")
            snippet = item.get("description", "无摘要")
            source = item.get("provider", [{}])[0].get("name", "未知来源")
            pub_date = item.get("datePublished", "未知")
            
            # 验证链接是否有效
            is_valid = self._validate_url(link)
            
            if is_valid:
                formatted_result = {
                    "标题": title,
                    "链接": link,
                    "摘要": snippet,
                    "来源": source,
                    "发布时间": pub_date
                }
                
                formatted_results.append(formatted_result)
        
        return formatted_results
    
    def _search_with_serper(self, query, api_key, time_range, max_results):
        """使用Serper.dev API进行搜索"""
        url = "https://google.serper.dev/search"
        
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        
        # 添加时间限制参数
        time_limit = "d"
        if time_range:
            days = int(time_range.replace('d', ''))
            time_limit = f"d{days}"
        
        payload = {
            "q": f"{query} news",
            "gl": "cn",  # 地理位置，可选
            "hl": "zh-cn",  # 语言，可选
            "num": min(max_results, 20),  # 结果数量
            "tbs": f"qdr:{time_limit}"  # 时间限制
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"搜索请求失败: {response.status_code} - {response.text}")
        
        data = response.json()
        
        # Serper返回多种结果类型，我们优先使用news结果
        news_items = data.get("news", [])
        organic_items = data.get("organic", [])
        
        all_items = news_items + organic_items
        
        formatted_results = []
        for item in all_items[:max_results]:
            title = item.get("title", "无标题")
            link = item.get("link", "")
            snippet = item.get("snippet", "无摘要")
            source = item.get("source", "")
            
            # 如果没有来源，尝试从链接中提取
            if not source:
                parsed_url = urlparse(link)
                source = parsed_url.netloc
            
            # 尝试获取发布时间
            pub_date = item.get("date", "未知")
            if pub_date == "未知" and "publishedDate" in item:
                pub_date = item["publishedDate"]
            
            # 验证链接是否有效
            is_valid = self._validate_url(link)
            
            if is_valid:
                formatted_result = {
                    "标题": title,
                    "链接": link,
                    "摘要": snippet,
                    "来源": source,
                    "发布时间": pub_date
                }
                
                formatted_results.append(formatted_result)
        
        return formatted_results
    
    def _validate_url(self, url):
        """验证URL是否有效（可访问）"""
        try:
            # 检查URL格式
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                return False
            
            # 检查链接是否是常见的有效域名，避免无效链接
            valid_domains = [
                ".com", ".cn", ".org", ".net", ".edu", ".gov", ".io", 
                ".ai", ".tech", ".news", ".info", ".co", ".me"
            ]
            
            has_valid_domain = any(parsed_url.netloc.endswith(domain) for domain in valid_domains)
            if not has_valid_domain:
                return False
            
            # 可选：发送HEAD请求检查链接是否可访问
            # 但这可能会减慢工具执行速度，可根据需要启用
            if os.getenv("VALIDATE_URLS", "false").lower() == "true":
                head_response = requests.head(url, timeout=3)
                return head_response.status_code < 400
            
            return True
        except:
            return False


class NewsFilterInput(BaseModel):
    """Input schema for NewsFilterTool."""
    news_list: str = Field(..., description="JSON格式的新闻列表")
    block_keywords: List[str] = Field(..., description="需要屏蔽的关键词列表")
    include_source: Optional[bool] = Field(True, description="是否在结果中包含来源信息")
    include_link: Optional[bool] = Field(True, description="是否在结果中包含链接信息")

class NewsFilterTool(BaseTool):
    name: str = "新闻过滤工具"
    description: str = (
        "使用此工具过滤新闻列表，移除包含指定屏蔽关键词的新闻，并可选择是否包含来源和链接信息。"
    )
    args_schema: Type[BaseModel] = NewsFilterInput

    def _run(self, news_list: str, block_keywords: List[str], 
             include_source: Optional[bool] = True, 
             include_link: Optional[bool] = True) -> str:
        try:
            # 从环境变量读取控制参数，如果有设置的话
            env_include_source = os.getenv("INCLUDE_SOURCE")
            env_include_link = os.getenv("INCLUDE_LINK")
            
            # 环境变量优先级高于函数参数
            if env_include_source is not None:
                include_source = env_include_source.lower() == "true"
            
            if env_include_link is not None:
                include_link = env_include_link.lower() == "true"
            
            # 解析新闻列表
            news_items = json.loads(news_list)
            
            # 过滤新闻
            filtered_news = []
            for news in news_items:
                # 检查新闻标题和摘要是否包含屏蔽关键词
                title = news.get("标题", "").lower()
                summary = news.get("摘要", "").lower()
                content = title + " " + summary
                
                should_block = False
                for keyword in block_keywords:
                    if keyword.lower() in content:
                        should_block = True
                        break
                
                if not should_block:
                    # 根据参数决定是否包含来源和链接
                    if not include_source and "来源" in news:
                        # 完全删除来源字段而不是设为空字符串
                        del news["来源"]
                    
                    if not include_link and "链接" in news:
                        # 完全删除链接字段而不是设为空字符串
                        del news["链接"]
                    
                    filtered_news.append(news)
            
            if not filtered_news:
                return "过滤后没有剩余新闻。"
            
            return json.dumps(filtered_news, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return f"过滤过程中发生错误: {str(e)}"


class DiversityFilterInput(BaseModel):
    """Input schema for DiversityFilterTool."""
    news_list: str = Field(..., description="JSON格式的新闻列表")
    max_per_company: int = Field(3, description="每个公司或主题的最大新闻数量")
    
class DiversityFilterTool(BaseTool):
    name: str = "新闻多样性过滤工具"
    description: str = (
        "使用此工具过滤新闻列表，确保每个公司或主题最多只有指定数量的新闻，"
        "提高新闻来源的多样性。"
    )
    args_schema: Type[BaseModel] = DiversityFilterInput
    
    def _run(self, news_list: str, max_per_company: int = 3) -> str:
        try:
            # 解析新闻列表
            news_items = json.loads(news_list)
            
            # 主要公司和技术关键词，用于检测新闻主题
            companies = [
                "openai", "microsoft", "微软", "anthropic", "google", "谷歌", "meta", "facebook", 
                "amazon", "亚马逊", "nvidia", "英伟达", "apple", "苹果", "deepseek", "百度", "阿里", 
                "腾讯", "华为", "讯飞", "智谱", "文心一言", "豆包", "通义千问", "gemini", "gpt", "llama", 
                "claude", "mistral"
            ]
            
            # 用于存储每个关键词对应的新闻
            company_news = {company: [] for company in companies}
            other_news = []  # 存储不属于主要公司的新闻
            
            # 将新闻分类
            for news in news_items:
                title = news.get("标题", "").lower()
                summary = news.get("摘要", "").lower() if "摘要" in news else ""
                content = title + " " + summary
                
                # 检查新闻属于哪个公司/技术
                matched = False
                for company in companies:
                    if company.lower() in content:
                        company_news[company].append(news)
                        matched = True
                        break
                
                # 如果不属于任何主要公司，放入其他新闻列表
                if not matched:
                    other_news.append(news)
            
            # 为每个公司选择最重要/最新的新闻
            diverse_news = []
            
            # 首先加入其他新闻
            diverse_news.extend(other_news)
            
            # 然后按照每个公司添加有限数量的新闻
            for company, news_list in company_news.items():
                # 根据新闻的重要性或日期排序
                sorted_news = sorted(news_list, key=lambda x: x.get("发布时间", "未知"), reverse=True)
                diverse_news.extend(sorted_news[:max_per_company])
            
            # 根据重要性再次排序
            final_news = sorted(diverse_news, key=lambda x: len(x.get("摘要", "")), reverse=True)
            
            if not final_news:
                return "过滤后没有剩余新闻。"
            
            return json.dumps(final_news, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return f"多样性过滤过程中发生错误: {str(e)}"
