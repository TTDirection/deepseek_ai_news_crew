# -*- coding: utf-8 -*-
"""
llm_client.py

封装 ChatOpenAI 的调用逻辑，提供统一的 invoke(prompt: str) -> Response
"""
from langchain_openai import ChatOpenAI
import json
import re

class LLMClient:
    def __init__(self,
                 model: str = "ep-20250427095319-t4sw8",
                 api_key: str = "YOUR_API_KEY",
                 api_base: str = "https://ark.cn-beijing.volces.com/api/v3",
                 temperature: float = 0.0):
        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            openai_api_key=api_key,
            openai_api_base=api_base
        )

    def invoke(self, prompt: str) -> list:
        """
        调用 LLM，返回解析后的 JSON 数组
        """
        resp = self.llm.invoke(prompt)
        text = resp.content.strip()

        # 尝试提取最外层 JSON 数组
        if not text.startswith("["):
            start = text.find("[")
            end = text.rfind("]") + 1
            text = text[start:end]

        try:
            arr = json.loads(text)
            if isinstance(arr, list):
                return arr
        except json.JSONDecodeError:
            # 退回到正则再抽取
            m = re.search(r'\[\s*"[^"]*"(?:\s*,\s*"[^"]*")*\s*\]', text)
            if m:
                return json.loads(m.group(0))
        # 如果实在失败，抛异常或返回空
        raise ValueError("无法解析 LLM 输出为 JSON 数组")