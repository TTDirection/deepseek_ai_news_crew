import os
import re
import requests
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field

class WechatMessageInput(BaseModel):
    """Input schema for WechatMessageTool."""
    content: str = Field(..., description="要发送的内容")
    webhook_key: str = Field(None, description="企业微信webhook的key，默认使用环境变量中的值")

class WechatMessageTool(BaseTool):
    name: str = "企业微信消息发送工具"
    description: str = (
        "使用此工具将内容发送到企业微信机器人。"
    )
    args_schema: Type[BaseModel] = WechatMessageInput

    def _run(self, content: str, webhook_key: str = None) -> str:
        try:
            # 如果没有提供webhook_key，则使用环境变量中的值
            if not webhook_key:
                webhook_key = os.getenv("WECHAT_WEBHOOK_KEY", "8b529e9f-1dc9-4b5c-a60a-1b8d3298acdd")
            
            # 构建webhook完整URL
            webhook_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={webhook_key}"
            
            # 移除markdown格式符号（如果存在）
            if content.startswith("```markdown") and content.endswith("```"):
                content = content[12:-3].strip()
            elif content.startswith("```") and content.endswith("```"):
                content = content[3:-3].strip()
            
            # 准备消息内容，确保格式适合企业微信
            # 1. 提取标题和内容
            lines = content.split("\n")
            title = ""
            processed_content = content
            
            # 尝试提取第一行作为标题
            if lines and lines[0].startswith("# "):
                title = lines[0].replace("# ", "")
                processed_content = "\n".join(lines[1:]).strip()
            elif lines and lines[0].startswith("【AI日报】"):
                title = lines[0]
                processed_content = "\n".join(lines[1:]).strip()
            
            # 2. 截断过长内容（企业微信消息有长度限制）
            # 企业微信markdown内容限制约为4096个字符
            max_length = 4000
            if len(processed_content) > max_length:
                # 分批发送或截断
                # 这里选择截断，可以根据需要改为分批发送
                processed_content = processed_content[:max_length] + "...\n\n*[内容过长，已截断]*"
            
            # 3. 格式化最终消息
            final_content = ""
            if title:
                final_content = f"## {title}\n\n{processed_content}"
            else:
                final_content = processed_content
            
            # 确保格式正确
            # 企业微信markdown不支持某些Github风格的markdown格式
            # 替换一些可能不支持的格式
            final_content = final_content.replace("####", "###")
            
            # 构建payload
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": final_content
                }
            }
            
            # 发送请求
            response = requests.post(
                webhook_url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=10
            )
            
            # 返回结果
            result = response.json()
            if result.get("errcode") == 0:
                return f"消息发送成功: {result}"
            else:
                return f"消息发送失败: {result}"
                
        except Exception as e:
            return f"发送企业微信消息时发生错误: {str(e)}"

class MarkdownCleanerInput(BaseModel):
    """Input schema for MarkdownCleanerTool."""
    content: str = Field(..., description="需要清理的Markdown内容")

class MarkdownCleanerTool(BaseTool):
    name: str = "Markdown格式清理工具"
    description: str = (
        "使用此工具清理Markdown内容中的格式标记，比如开头的```markdown和结尾的```。"
    )
    args_schema: Type[BaseModel] = MarkdownCleanerInput

    def _run(self, content: str) -> str:
        try:
            # 移除开头的```markdown和结尾的```
            if content.startswith("```markdown") and content.endswith("```"):
                content = content[12:-3].strip()
            elif content.startswith("```") and content.endswith("```"):
                content = content[3:-3].strip()
            
            return content
                
        except Exception as e:
            return f"清理Markdown格式时发生错误: {str(e)}" 