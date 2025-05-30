# -*- coding: utf-8 -*-
"""
prompt_builder.py

专门负责构造发送给 LLM 的提示词（prompt），包括：
- 文本分段的提示
- 强制分割过长句子的提示
- 字幕拆行的提示
"""
import re

class PromptBuilder:
    @staticmethod
    def build_segmentation_prompt(text: str, max_audio_duration: float,
                                  estimated_cps: float) -> str:
        """
        构造将中文长文本分割为若干语义单元的提示词
        """
        # 估算字符上限
        char_limit = int(max_audio_duration * estimated_cps)
        prompt = f"""
请将以下中文文本分割成语义完整的句子，每个句子应尽可能长，但仍保持在合理的播报长度内。

分割要求：
1. 句子必须保持语义完整和连贯性
2. 每个句子应包含{char_limit - 5}-{char_limit + 5}个字符，不要太短
3. 尽量按照自然的语言停顿和语义单元进行分割
4. 整个文本大约需要分成若干个句子，每段时长不超过{max_audio_duration}秒
5. 最短的句子也应至少包含10个字符

返回格式要求：
- 只返回 JSON 数组，格式为: ["句子1", "句子2", ...]
- 不要返回任何其他文本或解释

需要分割的文本：
{text}
"""
        return prompt.strip()

    @staticmethod
    def build_force_split_prompt(token: str) -> str:
        """
        构造将过长句子进一步分割的提示词
        """
        prompt = f"""
请将以下长句子分割成几个较短的片段，每个片段应保持语义完整，且长度大约为15-20个字符。

分割要求：
1. 在自然的语义断点处分割
2. 每个片段必须是完整且有意义的
3. 避免产生过短（少于10个字符）的片段
4. 如果有连接词，应该放在下一个片段的开头

只返回 JSON 数组格式的结果，不要包含任何解释或附加文本。

需要分割的句子：
{token}
"""
        return prompt.strip()

    @staticmethod
    def build_subtitle_split_prompt(text: str, max_chars_per_line: int) -> str:
        """
        构造将一段文本分割为多行字幕的提示词
        """
        prompt = f"""
请将以下文本分割成多行字幕，每行不超过{max_chars_per_line}个字符，并保持语义完整性。
返回格式：JSON 数组，只包含分割后的行，不要有其他文本。

文本：
{text}
"""
        return prompt.strip()