import re
import json
from typing import List, Dict, Any, Optional, Tuple
from langchain_openai import ChatOpenAI

class TextSegmenter:
    """文本分割器，负责将长文本分割成适合语音合成的片段"""
    
    def __init__(self, max_chars_per_segment: int = 25, max_audio_duration: float = 4.8,
                 estimated_chars_per_second: float = 5.0, llm_config: Dict[str, Any] = None):
        """初始化文本分割器
        
        Args:
            max_chars_per_segment: 每个片段的最大字符数
            max_audio_duration: 每个片段的最大音频时长（秒）
            estimated_chars_per_second: 估计的每秒字符数
            llm_config: LLM配置
        """
        self.max_chars_per_segment = max_chars_per_segment
        self.max_audio_duration = max_audio_duration
        self.estimated_chars_per_second = estimated_chars_per_second
        
        # 初始化LLM
        default_llm_config = {
            "temperature": 0.0,
            "model": "deepseek-chat",
            "openai_api_key": "YOUR_API_KEY",
            "openai_api_base": "https://api.deepseek.com/v1"
        }
        
        if llm_config:
            default_llm_config.update(llm_config)
        
        self.llm = ChatOpenAI(**default_llm_config)
    
    def estimate_audio_duration(self, text: str) -> float:
        """估算文本的音频时长
        
        Args:
            text: 要估算的文本
            
        Returns:
            float: 估算的音频时长（秒）
        """
        # 移除空白字符
        cleaned_text = re.sub(r'\s+', '', text)
        char_count = len(cleaned_text)
        
        # 估算时长
        estimated_duration = char_count / self.estimated_chars_per_second
        return estimated_duration
    
    def segment_chinese_text_with_llm(self, text: str) -> List[str]:
        """使用LLM将中文文本分割成语义完整的片段
        
        Args:
            text: 要分割的文本
            
        Returns:
            List[str]: 分割后的文本片段
        """
        try:
            prompt = f"""
            请将以下中文文本分割成语义完整的片段，每个片段应该是一个完整的语义单元。
            返回格式：JSON数组，只包含分割后的片段，不要有其他文本。
            
            需要分割的文本：
            {text}
            """
            
            response = self.llm.invoke(prompt)
            response_text = response.content
            
            # 提取JSON部分
            json_match = re.search(r'\[\s*"[^"]*"(?:\s*,\s*"[^"]*")*\s*\]', response_text)
            if json_match:
                json_str = json_match.group(0)
                try:
                    segments = json.loads(json_str)
                    return segments
                except json.JSONDecodeError:
                    pass
            
            # 尝试直接解析整个响应
            try:
                segments = json.loads(response_text)
                if isinstance(segments, list):
                    return segments
            except json.JSONDecodeError:
                pass
            
            # 如果无法解析JSON，使用备选方法
            return self.segment_chinese_text_fallback(text)
            
        except Exception as e:
            print(f"LLM分词失败: {e}")
            return self.segment_chinese_text_fallback(text)
    
    def segment_chinese_text_fallback(self, text: str) -> List[str]:
        """简单规则分词作为后备方案
        
        Args:
            text: 要分词的文本
            
        Returns:
            List[str]: 分词结果
        """
        # 首先按标点符号分割
        major_punctuation = r'[。！？；]'
        sentences = re.split(f'({major_punctuation})', text)
        
        tokens = []
        for i in range(0, len(sentences), 2):
            if i < len(sentences):
                sentence = sentences[i].strip()
                if not sentence:
                    continue
                
                # 添加标点符号（如果有）
                if i + 1 < len(sentences):
                    sentence += sentences[i + 1]
                
                tokens.append(sentence)
        
        # 如果句子太长，进一步分割
        result = []
        for token in tokens:
            if len(token) > self.max_chars_per_segment:
                # 按次要标点符号分割
                minor_splits = re.split(r'([，、,])', token)
                
                current_segment = ""
                for j in range(0, len(minor_splits), 2):
                    if j < len(minor_splits):
                        part = minor_splits[j].strip()
                        if not part:
                            continue
                        
                        # 添加标点符号（如果有）
                        if j + 1 < len(minor_splits):
                            part += minor_splits[j + 1]
                        
                        if len(current_segment + part) <= self.max_chars_per_segment:
                            current_segment += part
                        else:
                            if current_segment:
                                result.append(current_segment)
                            current_segment = part
                
                if current_segment:
                    result.append(current_segment)
            else:
                result.append(token)
        
        return result
    
    def force_split_long_token(self, token: str) -> List[str]:
        """强制分割过长的token
        
        Args:
            token: 要分割的token
            
        Returns:
            List[str]: 分割后的片段
        """
        # 尝试使用LLM进一步分割
        try:
            prompt = f"""
            请将以下语句分割成更短的片段，每个片段保持语义完整，但要尽可能短。
            返回格式：JSON数组，只包含分割后的片段，不要有其他文本。
            
            需要分割的语句：
            {token}
            """
            
            response = self.llm.invoke(prompt)
            response_text = response.content
            
            # 提取JSON部分
            json_match = re.search(r'\[\s*"[^"]*"(?:\s*,\s*"[^"]*")*\s*\]', response_text)
            if json_match:
                json_str = json_match.group(0)
                try:
                    sub_segments = json.loads(json_str)
                    # 检查每个子片段是否仍然过长
                    result = []
                    for segment in sub_segments:
                        if self.estimate_audio_duration(segment) <= self.max_audio_duration:
                            result.append(segment)
                        else:
                            # 如果仍然过长，使用字符级分割
                            result.extend(self.character_level_split(segment))
                    return result
                except:
                    pass
            
            # 如果LLM分割失败，回退到字符级分割
            return self.character_level_split(token)
            
        except Exception as e:
            print(f"LLM强制分割失败: {e}")
            return self.character_level_split(token)
    
    def character_level_split(self, token: str) -> List[str]:
        """字符级别的分割方法（最后的后备方案）
        
        Args:
            token: 要分割的token
            
        Returns:
            List[str]: 分割后的片段
        """
        segments = []
        chars_per_segment = int(self.max_audio_duration * self.estimated_chars_per_second)
        
        # 确保至少有一个字符
        chars_per_segment = max(1, chars_per_segment)
        
        # 按固定字符数分割
        for i in range(0, len(token), chars_per_segment):
            segment = token[i:i + chars_per_segment]
            segments.append(segment)
        
        return segments
    
    def split_at_punctuation(self, text: str, max_length: int) -> List[str]:
        """在标点符号处分割文本
        
        Args:
            text: 要分割的文本
            max_length: 最大长度
            
        Returns:
            List[str]: 分割后的片段
        """
        # 主要分隔点（句号、感叹号、问号、分号）
        major_breaks = [m.start() for m in re.finditer(r'[。！？；]', text)]
        
        # 次要分隔点（逗号、顿号）
        minor_breaks = [m.start() for m in re.finditer(r'[，、,]', text)]
        
        # 所有分隔点
        all_breaks = sorted(major_breaks + minor_breaks)
        
        if not all_breaks:
            # 如果没有标点，按固定长度分割
            segments = []
            for i in range(0, len(text), max_length):
                segments.append(text[i:i + max_length])
            return segments
        
        segments = []
        start = 0
        
        for i, pos in enumerate(all_breaks):
            if pos - start + 1 > max_length:  # +1 for the punctuation
                # 如果当前段太长，找到最近的分隔点
                suitable_breaks = [b for b in all_breaks if b > start and b - start + 1 <= max_length]
                
                if suitable_breaks:
                    # 使用最后一个合适的分隔点
                    break_pos = suitable_breaks[-1]
                    segments.append(text[start:break_pos + 1])
                    start = break_pos + 1
                else:
                    # 如果没有合适的分隔点，强制分割
                    segments.append(text[start:start + max_length])
                    start += max_length
            
            # 如果到达最后一个分隔点
            if i == len(all_breaks) - 1 and start < len(text):
                segments.append(text[start:])
        
        # 确保处理了所有文本
        if start < len(text):
            segments.append(text[start:])
        
        return segments
    
    def optimize_segments(self, segments: List[str]) -> List[str]:
        """优化分段结果，合并过短的片段
        
        Args:
            segments: 分段列表
            
        Returns:
            List[str]: 优化后的分段列表
        """
        if not segments:
            return []
        
        # 如果只有一个片段，直接返回
        if len(segments) == 1:
            return segments
        
        optimized = []
        i = 0
        
        while i < len(segments):
            current = segments[i]
            current_duration = self.estimate_audio_duration(current)
            
            # 如果当前片段已经接近最大时长，直接添加
            if current_duration > self.max_audio_duration * 0.7:
                optimized.append(current)
                i += 1
                continue
            
            # 尝试合并当前片段和下一个片段
            if i + 1 < len(segments):
                next_segment = segments[i + 1]
                combined = current + next_segment
                combined_duration = self.estimate_audio_duration(combined)
                
                # 如果合并后不超过最大时长，合并它们
                if combined_duration <= self.max_audio_duration:
                    optimized.append(combined)
                    i += 2
                else:
                    optimized.append(current)
                    i += 1
            else:
                # 最后一个片段
                optimized.append(current)
                i += 1
        
        return optimized
    
    def smart_split_text(self, text: str) -> List[str]:
        """智能分割文本，使用LLM进行分词并基于估算时长控制段落长度
        
        Args:
            text: 要分割的文本
            
        Returns:
            List[str]: 分割后的文本段落列表
        """
        # 清理文本
        text = text.strip()
        
        # 如果文本估算时长小于限制，直接返回
        if self.estimate_audio_duration(text) <= self.max_audio_duration:
            return [text]
        
        # 使用LLM进行分词
        print("使用LLM进行文本分词...")
        tokens = self.segment_chinese_text_with_llm(text)
        print(f"LLM分词完成，得到 {len(tokens)} 个语义单元")
        
        # 进一步优化分词结果
        segments = []
        current_segment = ""
        
        for token in tokens:
            test_segment = current_segment + token
            
            # 检查是否超过时长限制
            if self.estimate_audio_duration(test_segment) <= self.max_audio_duration:
                current_segment = test_segment
            else:
                # 如果当前段落不为空，保存它
                if current_segment.strip():
                    segments.append(current_segment.strip())
                
                # 如果单个token就超过限制，需要强制分割
                if self.estimate_audio_duration(token) > self.max_audio_duration:
                    sub_segments = self.force_split_long_token(token)
                    segments.extend(sub_segments)
                    current_segment = ""
                else:
                    current_segment = token
        
        # 添加最后一个段落
        if current_segment.strip():
            segments.append(current_segment.strip())
        
        # 优化分段结果
        return self.optimize_segments(segments)
    
    def split_text_for_subtitles(self, text: str, max_chars_per_line: int = 20) -> List[str]:
        """将文本分割成适合字幕显示的片段
        
        Args:
            text: 要分割的文本
            max_chars_per_line: 每行字幕的最大字符数
            
        Returns:
            List[str]: 分割后的字幕片段
        """
        try:
            # 尝试使用LLM进行分割
            prompt = f"""
            请将以下文本分割成适合字幕显示的短句，每句不超过{max_chars_per_line}个字符，保持语义完整。
            返回格式：JSON数组，只包含分割后的片段，不要有其他文本。
            
            需要分割的文本：
            {text}
            """
            
            response = self.llm.invoke(prompt)
            response_text = response.content
            
            # 提取JSON部分
            json_match = re.search(r'\[\s*"[^"]*"(?:\s*,\s*"[^"]*")*\s*\]', response_text)
            if json_match:
                json_str = json_match.group(0)
                try:
                    segments = json.loads(json_str)
                    # 验证每个片段长度
                    for i, segment in enumerate(segments):
                        if len(segment) > max_chars_per_line:
                            # 如果有过长的片段，使用备选方法
                            return self.split_text_for_subtitles_fallback(text, max_chars_per_line)
                    return segments
                except:
                    pass
            
            # 如果无法解析JSON，使用备选方法
            return self.split_text_for_subtitles_fallback(text, max_chars_per_line)
            
        except Exception as e:
            print(f"LLM字幕分割失败: {e}")
            return self.split_text_for_subtitles_fallback(text, max_chars_per_line)
    
    def split_text_for_subtitles_fallback(self, text: str, max_chars_per_line: int = 20) -> List[str]:
        """备选方法：使用标点符号分割文本为字幕
        
        Args:
            text: 要分割的文本
            max_chars_per_line: 每行字幕的最大字符数
            
        Returns:
            List[str]: 分割后的字幕片段
        """
        return self.split_at_punctuation(text, max_chars_per_line)