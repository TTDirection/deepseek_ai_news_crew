import os
import re
import random
import subprocess
from datetime import datetime
from typing import List, Tuple
import json
from MultimodalRobot import MultimodalNewsBot, TTSModule
from langchain_openai import ChatOpenAI

class LongNewsProcessor:
    """长新闻处理器，支持分段播报"""
    
    def __init__(self, max_chars_per_segment=20, max_audio_duration=4.8):
        """
        初始化长新闻处理器
        
        Args:
            max_chars_per_segment: 每段最大字符数
            max_audio_duration: 最大音频时长（秒）
        """
        self.max_chars_per_segment = max_chars_per_segment
        self.max_audio_duration = max_audio_duration
        self.news_bot = MultimodalNewsBot()
        self.tts_module = TTSModule()
        
        # 初始化DeepSeek V3 LLM用于分词
        self.llm = ChatOpenAI(
            temperature=0.0,
            model="ep-20250427095319-t4sw8",  # V3:sw8,V1:7q4
            openai_api_key="5cf8e2f7-8465-4ccc-bf84-e32f05be0fb4",
            openai_api_base="https://ark.cn-beijing.volces.com/api/v3"
        )
        
        # 语速估算参数（字符/秒），根据实际情况调整
        self.estimated_chars_per_second = 5.0  # 保守估计，可以根据实际测试调整
        
        # 创建输出目录
        self.output_dir = os.path.join("output", "long_news")
        self.segments_dir = os.path.join(self.output_dir, "segments")
        self.final_videos_dir = os.path.join(self.output_dir, "final_videos")
        self.subtitles_dir = os.path.join(self.output_dir, "subtitles")
        
        for dir_path in [self.output_dir, self.segments_dir, self.final_videos_dir, self.subtitles_dir]:
            os.makedirs(dir_path, exist_ok=True)
    
    def estimate_audio_duration(self, text: str) -> float:
        """
        估算文本的音频时长
        
        Args:
            text: 文本内容
            
        Returns:
            float: 估算的音频时长（秒）
        """
        # 移除标点符号和空格来计算有效字符数
        effective_chars = len(re.sub(r'[^\w]', '', text))
        estimated_duration = effective_chars / self.estimated_chars_per_second
        return estimated_duration
    
    def segment_chinese_text_with_llm(self, text: str) -> List[str]:
        """
        使用DeepSeek V3 LLM进行中文文本分词，优化生成更长的片段
        
        Args:
            text: 要分词的文本
            
        Returns:
            List[str]: 分词结果
        """
        try:
            # 计算整个文本的估计时长
            total_estimated_duration = self.estimate_audio_duration(text)
            min_segments_needed = max(1, int(total_estimated_duration / self.max_audio_duration))
            
            # 构建提示词，要求LLM将文本分割成尽可能长的短句
            prompt = f"""
            请将以下中文文本分割成语义完整的句子，每个句子应尽可能长，但仍保持在合理的播报长度内。
            
            分割要求：
            1. 句子必须保持语义完整和连贯性
            2. 每个句子应包含25-30个字符，不要太短
            3. 尽量按照自然的语言停顿和语义单元进行分割
            4. 整个文本大约需要分成{min_segments_needed}个句子左右
            5. 最短的句子也应至少包含10个字符
            
            返回格式要求：
            - 只返回JSON数组，格式为: ["句子1", "句子2", ...]
            - 不要返回任何其他文本或解释
            
            需要分割的文本：
            {text}
            """
            
            # 添加更明确的任务描述
            if self.max_audio_duration:
                prompt += f"\n每个句子的播报时长应控制在{self.max_audio_duration}秒以内，约{int(self.max_audio_duration * self.estimated_chars_per_second)}个字符。"
            
            # 调用LLM获取分词结果
            response = self.llm.invoke(prompt)
            response_text = response.content
            
            # 更强大的JSON提取
            # 先尝试整个文本作为JSON解析
            try:
                # 清理可能的额外文本
                cleaned_text = response_text.strip()
                # 如果文本不是以[开头，尝试找到第一个[
                if not cleaned_text.startswith('['):
                    start_idx = cleaned_text.find('[')
                    if start_idx != -1:
                        cleaned_text = cleaned_text[start_idx:]
                # 如果文本不是以]结尾，尝试找到最后一个]
                if not cleaned_text.endswith(']'):
                    end_idx = cleaned_text.rfind(']')
                    if end_idx != -1:
                        cleaned_text = cleaned_text[:end_idx+1]
                
                tokens = json.loads(cleaned_text)
                if isinstance(tokens, list) and all(isinstance(item, str) for item in tokens):
                    # 验证结果是否合理
                    if len(tokens) >= min(2, min_segments_needed) and all(len(token) > 0 for token in tokens):
                        print(f"成功使用LLM分割文本，得到{len(tokens)}个片段")
                        return self.optimize_segments(tokens)
            except json.JSONDecodeError:
                pass
            
            # 如果整体解析失败，尝试正则表达式提取
            json_match = re.search(r'\[\s*"[^"]*"(?:\s*,\s*"[^"]*")*\s*\]', response_text)
            if json_match:
                json_str = json_match.group(0)
                try:
                    tokens = json.loads(json_str)
                    # 优化分段
                    if isinstance(tokens, list) and all(isinstance(item, str) for item in tokens):
                        return self.optimize_segments(tokens)
                except json.JSONDecodeError:
                    print("JSON解析错误，尝试替代提取方式...")
            
            # 提取引号内的内容作为token
            tokens = []
            for match in re.finditer(r'"([^"]*)"', response_text):
                token = match.group(1).strip()
                if token:
                    tokens.append(token)
            
            if tokens:
                return self.optimize_segments(tokens)
            
            # 所有方法都失败，尝试简单的分割方式
            print("LLM分词提取失败，使用简单规则分词作为后备方案")
            segments = self.segment_chinese_text_alternative(text)
            return self.optimize_segments(segments)
            
        except Exception as e:
            print(f"LLM分词出错: {e}")
            # 出错时使用替代分词方法
            segments = self.segment_chinese_text_alternative(text)
            return self.optimize_segments(segments)

    def optimize_segments(self, segments: List[str]) -> List[str]:
        """
        优化分段结果，合并过短的片段，拆分过长的片段
        
        Args:
            segments: 原始分段列表
            
        Returns:
            List[str]: 优化后的分段列表
        """
        # 定义最小段落长度（字符数）
        MIN_SEGMENT_LENGTH = 10
        # 定义理想段落长度范围
        IDEAL_MIN_LENGTH = 15
        IDEAL_MAX_LENGTH = int(self.max_audio_duration * self.estimated_chars_per_second * 0.9)  # 留10%余量
        
        # 第一步：标记过短的段落
        segments_with_flags = []
        for segment in segments:
            is_short = len(segment) < MIN_SEGMENT_LENGTH
            segments_with_flags.append({
                "text": segment,
                "is_short": is_short,
                "length": len(segment),
                "duration": self.estimate_audio_duration(segment)
            })
        
        # 第二步：合并过短的段落与相邻段落
        optimized = []
        i = 0
        while i < len(segments_with_flags):
            current = segments_with_flags[i]
            
            # 如果当前段落不是过短的，或者是最后一个段落
            if not current["is_short"] or i == len(segments_with_flags) - 1:
                optimized.append(current["text"])
                i += 1
                continue
            
            # 尝试向后合并
            if i + 1 < len(segments_with_flags):
                next_segment = segments_with_flags[i + 1]
                combined_text = current["text"] + next_segment["text"]
                combined_duration = self.estimate_audio_duration(combined_text)
                
                # 如果合并后不超过时长限制
                if combined_duration <= self.max_audio_duration:
                    optimized.append(combined_text)
                    i += 2  # 跳过下一个段落
                    continue
            
            # 如果无法向后合并，尝试向前合并（如果不是第一个段落）
            if i > 0 and optimized:
                last_segment = optimized[-1]
                combined_text = last_segment + current["text"]
                combined_duration = self.estimate_audio_duration(combined_text)
                
                # 如果合并后不超过时长限制
                if combined_duration <= self.max_audio_duration:
                    optimized[-1] = combined_text  # 替换前一个段落
                    i += 1
                    continue
            
            # 如果无法合并，仍然保留这个短段落
            optimized.append(current["text"])
            i += 1
        
        # 第三步：处理仍然过长的段落
        final_segments = []
        for segment in optimized:
            segment_duration = self.estimate_audio_duration(segment)
            if segment_duration > self.max_audio_duration:
                # 使用力分割长段落
                sub_segments = self.force_split_long_token(segment)
                final_segments.extend(sub_segments)
            else:
                final_segments.append(segment)
        
        # 第四步：再次检查并优化
        # 合并相邻的短段落（即使不是"过短"）
        result = []
        i = 0
        while i < len(final_segments):
            current = final_segments[i]
            current_len = len(current)
            
            # 如果当前段落长度小于理想最小长度，并且不是最后一个
            if current_len < IDEAL_MIN_LENGTH and i < len(final_segments) - 1:
                next_segment = final_segments[i + 1]
                combined_text = current + next_segment
                combined_duration = self.estimate_audio_duration(combined_text)
                
                # 如果合并后不超过时长限制
                if combined_duration <= self.max_audio_duration:
                    result.append(combined_text)
                    i += 2  # 跳过下一个段落
                    continue
            
            result.append(current)
            i += 1
        
        # 打印优化结果
        print(f"分段优化: {len(segments)} 个原始片段 -> {len(result)} 个优化片段")
        for i, segment in enumerate(result):
            print(f"  片段 {i+1}: {len(segment)} 字符, 估计 {self.estimate_audio_duration(segment):.2f} 秒")
        
        return result

    def force_split_long_token(self, token: str) -> List[str]:
        """
        智能分割过长的token，优先在自然断句处分割
        
        Args:
            token: 要分割的token
            
        Returns:
            List[str]: 分割后的片段
        """
        # 尝试使用LLM进一步分割
        try:
            prompt = f"""
            请将以下长句子分割成几个较短的片段，每个片段应保持语义完整，且长度大约为15-20个字符。

            分割要求：
            1. 在自然的语义断点处分割
            2. 每个片段必须是完整且有意义的
            3. 避免产生过短（少于10个字符）的片段
            4. 如果有连接词，应该放在下一个片段的开头

            只返回JSON数组格式的结果，不要包含任何解释或附加文本。

            需要分割的句子：
            {token}
            """
            
            response = self.llm.invoke(prompt)
            response_text = response.content
            
            # 提取JSON部分
            cleaned_text = response_text.strip()
            # 如果文本不是以[开头，尝试找到第一个[
            if not cleaned_text.startswith('['):
                start_idx = cleaned_text.find('[')
                if start_idx != -1:
                    cleaned_text = cleaned_text[start_idx:]
            # 如果文本不是以]结尾，尝试找到最后一个]
            if not cleaned_text.endswith(']'):
                end_idx = cleaned_text.rfind(']')
                if end_idx != -1:
                    cleaned_text = cleaned_text[:end_idx+1]
            
            try:
                sub_segments = json.loads(cleaned_text)
                # 验证并优化子片段
                if isinstance(sub_segments, list) and all(isinstance(item, str) for item in sub_segments):
                    # 确保每个子片段不超过时长限制
                    valid_segments = []
                    for segment in sub_segments:
                        if self.estimate_audio_duration(segment) <= self.max_audio_duration:
                            valid_segments.append(segment)
                        else:
                            # 如果某个子片段仍然过长，使用规则分割
                            valid_segments.extend(self.split_at_punctuation(segment))
                    
                    # 合并过短的子片段
                    optimized = self.optimize_segments(valid_segments)
                    if optimized:
                        return optimized
            except:
                pass
            
            # 如果LLM分割失败，使用标点符号分割
            return self.split_at_punctuation(token)
            
        except Exception as e:
            print(f"LLM强制分割失败: {e}")
            return self.split_at_punctuation(token)

    def split_at_punctuation(self, text: str) -> List[str]:
        """
        在标点符号处分割文本
        
        Args:
            text: 要分割的文本
            
        Returns:
            List[str]: 分割后的片段
        """
        # 主要分隔点（句号、感叹号、问号、分号）
        major_breaks_positions = [m.start() for m in re.finditer(r'[。！？；]', text)]
        
        # 次要分隔点（逗号、顿号）
        minor_breaks_positions = [m.start() for m in re.finditer(r'[，、,]', text)]
        
        # 合并所有分隔点并排序
        all_breaks = sorted(major_breaks_positions + minor_breaks_positions)
        
        if not all_breaks:
            # 如果没有标点，按固定长度分割（大约每15个字符）
            chars_per_segment = min(15, int(self.max_audio_duration * self.estimated_chars_per_second * 0.8))
            segments = []
            for i in range(0, len(text), chars_per_segment):
                segments.append(text[i:min(i + chars_per_segment, len(text))])
            return segments
        
        # 使用分隔点分割文本，保持在时长限制内
        segments = []
        start = 0
        current_segment = ""
        
        # 遍历所有分隔点
        for pos in all_breaks:
            # 包含分隔符在内的文本片段
            segment = text[start:pos+1]
            
            # 测试添加这个片段后是否超过时长限制
            test_segment = current_segment + segment
            if self.estimate_audio_duration(test_segment) <= self.max_audio_duration:
                current_segment = test_segment
            else:
                # 如果超过限制，保存当前累积的片段，并开始新片段
                if current_segment:
                    segments.append(current_segment)
                current_segment = segment
            
            # 更新起始位置
            start = pos + 1
        
        # 添加最后一个片段
        if start < len(text):
            last_segment = text[start:]
            if current_segment and self.estimate_audio_duration(current_segment + last_segment) <= self.max_audio_duration:
                current_segment += last_segment
            else:
                if current_segment:
                    segments.append(current_segment)
                current_segment = last_segment
        
        if current_segment:
            segments.append(current_segment)
        
        # 检查是否有过短的片段，并尝试合并
        return self.optimize_segments(segments)

    def segment_chinese_text_alternative(self, text: str) -> List[str]:
        """
        替代分词方法，尝试生成更长的片段
        
        Args:
            text: 要分词的文本
            
        Returns:
            List[str]: 分词结果
        """
        # 估算整个文本需要分成多少段
        total_duration = self.estimate_audio_duration(text)
        estimated_segments = max(1, int(total_duration / self.max_audio_duration))
        
        # 主要分隔点（句号、感叹号、问号、分号）
        major_breaks = [m.start() for m in re.finditer(r'[。！？；]', text)]
        
        # 次要分隔点（逗号、顿号）
        minor_breaks = [m.start() for m in re.finditer(r'[，、,]', text)]
        
        # 如果分隔点太少，增加一些空格或其他字符作为潜在分隔点
        all_breaks = sorted(major_breaks + minor_breaks)
        
        if not all_breaks:
            # 如果没有标点，按固定长度分割
            avg_len = len(text) / estimated_segments
            segments = []
            for i in range(0, len(text), int(avg_len)):
                end = min(i + int(avg_len), len(text))
                segments.append(text[i:end])
            return segments
        
        # 如果分隔点太多，选择均匀分布的点
        if len(all_breaks) > estimated_segments * 2:
            ideal_indices = []
            segment_size = len(text) / estimated_segments
            for i in range(1, estimated_segments):
                ideal_pos = int(i * segment_size)
                # 找到最接近理想位置的分隔点
                closest_break = min(all_breaks, key=lambda x: abs(x - ideal_pos))
                ideal_indices.append(closest_break)
            
            segments = []
            start = 0
            for idx in sorted(ideal_indices):
                segments.append(text[start:idx+1])
                start = idx+1
            
            # 添加最后一段
            if start < len(text):
                segments.append(text[start:])
                
            return segments
        
        # 默认情况：尽量在主要分隔点处分割
        segments = []
        start = 0
        current_duration = 0
        
        for i, idx in enumerate(all_breaks):
            segment = text[start:idx+1]
            segment_duration = self.estimate_audio_duration(segment)
            
            if current_duration + segment_duration <= self.max_audio_duration:
                current_duration += segment_duration
            else:
                if start < idx:
                    segments.append(text[start:idx+1])
                start = idx+1
                current_duration = 0
        
        # 添加最后一段
        if start < len(text):
            segments.append(text[start:])
        
        # 如果分段结果太少，可能是标点太少，尝试进一步分割
        if len(segments) < estimated_segments / 2:
            refined_segments = []
            for segment in segments:
                if self.estimate_audio_duration(segment) > self.max_audio_duration:
                    # 按照一定长度分割
                    chars_per_segment = int(self.max_audio_duration * self.estimated_chars_per_second)
                    for i in range(0, len(segment), chars_per_segment):
                        refined_segments.append(segment[i:i+chars_per_segment])
                else:
                    refined_segments.append(segment)
            segments = refined_segments
        
        return segments

    def smart_split_text(self, text: str) -> List[str]:
        """
        智能分割文本，使用LLM进行分词并基于估算时长控制段落长度
        
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
        print("使用DeepSeek V3 LLM进行文本分词...")
        tokens = self.segment_chinese_text_with_llm(text)
        print(f"LLM分词完成，得到 {len(tokens)} 个语义单元")
        
        # 进一步优化分词结果
        segments = []
        
        for token in tokens:
            token_duration = self.estimate_audio_duration(token)
            
            # 如果单个token超过时长限制，需要进一步分割
            if token_duration > self.max_audio_duration:
                sub_segments = self.force_split_long_token(token)
                segments.extend(sub_segments)
            else:
                segments.append(token)
        
        return segments
    
    def segment_chinese_text_fallback(self, text: str) -> List[str]:
        """
        简单规则分词作为后备方案
        
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
    
    def smart_split_text(self, text: str) -> List[str]:
        """
        智能分割文本，使用LLM进行分词并基于估算时长控制段落长度
        
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
        print("使用DeepSeek V3 LLM进行文本分词...")
        tokens = self.segment_chinese_text_with_llm(text)
        print(f"LLM分词完成，得到 {len(tokens)} 个语义单元")
        
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
        
        return segments
    
    def force_split_long_token(self, token: str) -> List[str]:
        """
        强制分割过长的token
        
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
        """
        字符级别的分割方法（最后的后备方案）
        
        Args:
            token: 要分割的token
            
        Returns:
            List[str]: 分割后的片段
        """
        segments = []
        current_segment = ""
        
        # 按字符逐个添加
        for char in token:
            test_segment = current_segment + char
            
            if self.estimate_audio_duration(test_segment) <= self.max_audio_duration:
                current_segment = test_segment
            else:
                if current_segment:
                    segments.append(current_segment)
                current_segment = char
        
        if current_segment:
            segments.append(current_segment)
        
        return segments
    
    def split_text_for_subtitles(self, text: str, max_chars_per_line: int) -> List[str]:
        """
        为字幕分割文本，使用LLM保持更好的语义完整性
        
        Args:
            text: 要分割的文本
            max_chars_per_line: 每行最大字符数
            
        Returns:
            List[str]: 分割后的文本行
        """
        if len(text) <= max_chars_per_line:
            return [text]
        
        try:
            # 使用LLM进行分行
            prompt = f"""
            请将以下文本分割成多行字幕，每行不超过{max_chars_per_line}个字符，并保持语义完整性。
            返回格式：JSON数组，只包含分割后的行，不要有其他文本。
            
            文本：
            {text}
            """
            
            response = self.llm.invoke(prompt)
            response_text = response.content
            
            # 提取JSON部分
            json_match = re.search(r'\[\s*"[^"]*"(?:\s*,\s*"[^"]*")*\s*\]', response_text)
            if json_match:
                json_str = json_match.group(0)
                try:
                    lines = json.loads(json_str)
                    # 验证每行长度
                    valid_lines = []
                    for line in lines:
                        if len(line) <= max_chars_per_line:
                            valid_lines.append(line)
                        else:
                            # 超长行进一步分割
                            for i in range(0, len(line), max_chars_per_line):
                                valid_lines.append(line[i:i+max_chars_per_line])
                    
                    return valid_lines
                except:
                    pass
        
            # 如果LLM分割失败，使用简单的字符计数分割
            return self.split_text_for_subtitles_fallback(text, max_chars_per_line)
            
        except Exception as e:
            print(f"LLM字幕分行失败: {e}")
            return self.split_text_for_subtitles_fallback(text, max_chars_per_line)
    
    def split_text_for_subtitles_fallback(self, text: str, max_chars_per_line: int) -> List[str]:
        """
        简单字幕分行后备方案
        """
        segments = []
        
        # 首先按句号、问号等分割
        sentences = re.split(r'([。！？；])', text)
        
        current_line = ""
        for i in range(0, len(sentences), 2):
            if i < len(sentences):
                part = sentences[i]
                
                # 添加标点符号（如果有）
                if i + 1 < len(sentences):
                    part += sentences[i + 1]
                
                if len(current_line + part) <= max_chars_per_line:
                    current_line += part
                else:
                    if current_line:
                        segments.append(current_line)
                    
                    # 如果单个部分超过最大长度，进一步分割
                    if len(part) > max_chars_per_line:
                        for j in range(0, len(part), max_chars_per_line):
                            segments.append(part[j:j+max_chars_per_line])
                        current_line = ""
                    else:
                        current_line = part
        
        if current_line:
            segments.append(current_line)
        
        return segments
    
    def calibrate_speech_rate(self, sample_text: str = "这是一个用于测试语速的示例文本，包含了中文和English单词。") -> float:
        """
        校准语速参数
        
        Args:
            sample_text: 用于测试的示例文本
            
        Returns:
            float: 校准后的字符/秒速率
        """
        print("正在校准语速参数...")
        try:
            voice_path, duration = self.tts_module.generate_voice(
                sample_text, f"calibration_{random.randint(1000, 9999)}"
            )
            
            effective_chars = len(re.sub(r'[^\w]', '', sample_text))
            chars_per_second = effective_chars / duration
            
            print(f"校准结果: {effective_chars} 字符 / {duration:.2f} 秒 = {chars_per_second:.2f} 字符/秒")
            
            # 删除临时文件
            if os.path.exists(voice_path):
                os.remove(voice_path)
            
            # 更新估算参数，并增加10%的安全边际
            self.estimated_chars_per_second = chars_per_second * 0.9
            print(f"更新后的估算参数: {self.estimated_chars_per_second:.2f} 字符/秒")
            
            return self.estimated_chars_per_second
            
        except Exception as e:
            print(f"语速校准失败，使用默认值: {e}")
            return self.estimated_chars_per_second
    
    def create_subtitle_file(self, text: str, audio_duration: float, output_path: str, 
                           subtitle_format: str = "srt") -> str:
        """
        创建字幕文件
        
        Args:
            text: 字幕文本
            audio_duration: 音频时长
            output_path: 输出文件路径（不含扩展名）
            subtitle_format: 字幕格式 ("srt", "ass", "vtt")
            
        Returns:
            str: 字幕文件路径
        """
        if subtitle_format.lower() == "srt":
            return self.create_srt_subtitle(text, audio_duration, output_path)
        elif subtitle_format.lower() == "ass":
            return self.create_ass_subtitle(text, audio_duration, output_path)
        elif subtitle_format.lower() == "vtt":
            return self.create_vtt_subtitle(text, audio_duration, output_path)
        else:
            raise ValueError(f"不支持的字幕格式: {subtitle_format}")
    
    def create_srt_subtitle(self, text: str, audio_duration: float, output_path: str) -> str:
        """
        创建SRT格式字幕文件（多行但一次性显示，时间覆盖全段）
        """
        subtitle_path = f"{output_path}.srt"

        def format_time(seconds):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            millisecs = int((seconds % 1) * 1000)
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

        start_time = 0.0
        end_time = audio_duration

        # 分行（比如每20字一行）
        max_chars_per_line = 20
        lines = self.split_text_for_subtitles(text, max_chars_per_line)

        with open(subtitle_path, 'w', encoding='utf-8') as f:
            f.write("1\n")
            f.write(f"{format_time(start_time)} --> {format_time(end_time)}\n")
            # 多行写入
            for line in lines:
                f.write(line.strip() + "\n")
            f.write("\n")

        print(f"SRT字幕文件已创建: {subtitle_path}")
        return subtitle_path
    
    def create_ass_subtitle(self, text: str, audio_duration: float, output_path: str) -> str:
        """
        创建ASS格式字幕文件（支持更丰富的样式）
        
        Args:
            text: 字幕文本
            audio_duration: 音频时长
            output_path: 输出文件路径（不含扩展名）
            
        Returns:
            str: 字幕文件路径
        """
        subtitle_path = f"{output_path}.ass"
        
        def format_time(seconds):
            """格式化时间为ASS格式 H:MM:SS.cc"""
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            centisecs = int((seconds % 1) * 100)
            return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"
        
        # ASS文件头部
        ass_header = """[Script Info]
Title: AI News Subtitle
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        # 计算字幕显示时间
        start_time = 0.0
        end_time = audio_duration
        
        with open(subtitle_path, 'w', encoding='utf-8') as f:
            f.write(ass_header)
            
            # 如果文本较长，分段显示
            max_chars_per_line = 20
            if len(text) > max_chars_per_line:
                segments = self.split_text_for_subtitles(text, max_chars_per_line)
                segment_duration = audio_duration / len(segments)
                
                for i, segment in enumerate(segments):
                    segment_start = i * segment_duration
                    segment_end = (i + 1) * segment_duration
                    
                    f.write(f"Dialogue: 0,{format_time(segment_start)},{format_time(segment_end)},Default,,0,0,0,,{segment}\n")
            else:
                f.write(f"Dialogue: 0,{format_time(start_time)},{format_time(end_time)},Default,,0,0,0,,{text}\n")
        
        print(f"ASS字幕文件已创建: {subtitle_path}")
        return subtitle_path
    
    def create_vtt_subtitle(self, text: str, audio_duration: float, output_path: str) -> str:
        """
        创建VTT格式字幕文件
        
        Args:
            text: 字幕文本
            audio_duration: 音频时长
            output_path: 输出文件路径（不含扩展名）
            
        Returns:
            str: 字幕文件路径
        """
        subtitle_path = f"{output_path}.vtt"
        
        def format_time(seconds):
            """格式化时间为VTT格式 HH:MM:SS.mmm"""
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            millisecs = int((seconds % 1) * 1000)
            return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millisecs:03d}"
        
        with open(subtitle_path, 'w', encoding='utf-8') as f:
            f.write("WEBVTT\n\n")
            
            # 如果文本较长，分段显示
            max_chars_per_line = 20
            if len(text) > max_chars_per_line:
                segments = self.split_text_for_subtitles(text, max_chars_per_line)
                segment_duration = audio_duration / len(segments)
                
                for i, segment in enumerate(segments):
                    segment_start = i * segment_duration
                    segment_end = (i + 1) * segment_duration
                    
                    f.write(f"{i + 1}\n")
                    f.write(f"{format_time(segment_start)} --> {format_time(segment_end)}\n")
                    f.write(f"{segment}\n\n")
            else:
                f.write("1\n")
                f.write(f"{format_time(0.0)} --> {format_time(audio_duration)}\n")
                f.write(f"{text}\n\n")
        
        print(f"VTT字幕文件已创建: {subtitle_path}")
        return subtitle_path
    
    def add_subtitles_to_video(self, video_path: str, subtitle_path: str, output_path: str, 
                             subtitle_style: dict = None) -> str:
        """
        将字幕添加到视频中（修复路径问题）
        
        Args:
            video_path: 视频文件路径
            subtitle_path: 字幕文件路径
            output_path: 输出视频路径
            subtitle_style: 字幕样式设置
            
        Returns:
            str: 带字幕的视频文件路径
        """
        try:
            # 检查字幕文件是否存在
            if not os.path.exists(subtitle_path):
                print(f"字幕文件不存在: {subtitle_path}")
                return None
            
            # 默认字幕样式
            default_style = {
                'fontsize': 20,
                'fontcolor': 'white',
                'fontfile': None,  # 字体文件路径，可选
                'box': 1,
                'boxcolor': 'black@0.5',
                'boxborderw': 5,
                'x': '(w-text_w)/2',  # 水平居中
                'y': 'h-text_h-10'   # 底部对齐，距离底部10像素
            }
            
            if subtitle_style:
                default_style.update(subtitle_style)
            
            # 获取绝对路径并正确转义
            abs_subtitle_path = os.path.abspath(subtitle_path)
            
            # 构建字幕滤镜参数
            if subtitle_path.endswith('.srt') or subtitle_path.endswith('.vtt'):
                # 对Windows路径进行特殊处理
                if os.name == 'nt':  # Windows
                    # Windows路径需要转义反斜杠和冒号
                    escaped_path = abs_subtitle_path.replace('\\', '\\\\').replace(':', '\\:')
                else:  # Unix/Linux
                    # Unix路径只需要转义冒号
                    escaped_path = abs_subtitle_path.replace(':', '\\:')
                
                # 使用subtitles滤镜
                subtitle_filter = f"subtitles='{escaped_path}'"
                
                # 添加样式参数（仅对支持的参数）
                if default_style.get('fontsize'):
                    subtitle_filter += f":force_style='Fontsize={default_style['fontsize']}'"
                    
            elif subtitle_path.endswith('.ass'):
                # 使用ass滤镜
                if os.name == 'nt':
                    escaped_path = abs_subtitle_path.replace('\\', '\\\\').replace(':', '\\:')
                else:
                    escaped_path = abs_subtitle_path.replace(':', '\\:')
                
                subtitle_filter = f"ass='{escaped_path}'"
            else:
                print(f"不支持的字幕格式: {subtitle_path}")
                return None
            
            # 构建ffmpeg命令
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', subtitle_filter,
                '-c:a', 'copy',  # 音频流复制
                '-c:v', 'libx264',  # 视频重新编码以嵌入字幕
                output_path
            ]
            
            print(f"正在添加字幕到视频: {output_path}")
            print(f"字幕文件: {abs_subtitle_path}")
            print(f"字幕滤镜: {subtitle_filter}")
            
            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"字幕添加成功: {output_path}")
                return output_path
            else:
                print(f"字幕添加失败:")
                print(f"错误信息: {result.stderr}")
                
                # 尝试简化的方法
                print("尝试使用简化的字幕方法...")
                return self.add_subtitles_simple(video_path, subtitle_path, output_path, default_style)
                
        except Exception as e:
            print(f"添加字幕时出错: {e}")
            return None
    
    def add_subtitles_simple(self, video_path: str, subtitle_path: str, output_path: str, 
                           subtitle_style: dict) -> str:
        """
        使用简化方法添加字幕（fallback方法）
        
        Args:
            video_path: 视频文件路径
            subtitle_path: 字幕文件路径
            output_path: 输出视频路径
            subtitle_style: 字幕样式设置
            
        Returns:
            str: 带字幕的视频文件路径
        """
        try:
            # 读取字幕文件内容
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                subtitle_content = f.read()
            
            # 从SRT内容中提取文本
            if subtitle_path.endswith('.srt'):
                # 简单的SRT解析
                lines = subtitle_content.split('\n')
                subtitle_text = ""
                for line in lines:
                    line = line.strip()
                    if line and not line.isdigit() and '-->' not in line:
                        if subtitle_text:
                            subtitle_text += " "
                        subtitle_text += line
            else:
                subtitle_text = subtitle_content
            
            # 使用drawtext滤镜
            # 转义特殊字符
            escaped_text = subtitle_text.replace("'", "\\'").replace(":", "\\:")
            
            subtitle_filter = f"drawtext=text='{escaped_text}'"
            subtitle_filter += f":fontsize={subtitle_style.get('fontsize', 20)}"
            subtitle_filter += f":fontcolor={subtitle_style.get('fontcolor', 'white')}"
            subtitle_filter += f":x={subtitle_style.get('x', '(w-text_w)/2')}"
            subtitle_filter += f":y={subtitle_style.get('y', 'h-text_h-10')}"
            
            if subtitle_style.get('box'):
                subtitle_filter += f":box=1"
                subtitle_filter += f":boxcolor={subtitle_style.get('boxcolor', 'black@0.5')}"
                subtitle_filter += f":boxborderw={subtitle_style.get('boxborderw', 5)}"
            
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', subtitle_filter,
                '-c:a', 'copy',
                '-c:v', 'libx264',
                output_path
            ]
            
            print(f"使用简化方法添加字幕...")
            print(f"字幕滤镜: {subtitle_filter}")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"简化方法字幕添加成功: {output_path}")
                return output_path
            else:
                print(f"简化方法也失败: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"简化字幕方法出错: {e}")
            return None
    
    def generate_random_seed(self) -> int:
        """生成随机种子"""
        return random.randint(1, 10000)
    
    def merge_audio_video(self, audio_path: str, video_path: str, output_path: str) -> str:
        """
        合并音频和视频，裁剪视频时长与音频一致
        
        Args:
            audio_path: 音频文件路径
            video_path: 视频文件路径
            output_path: 输出文件路径
            
        Returns:
            str: 合并后的视频文件路径
        """
        try:
            # 使用ffmpeg合并音频和视频，并裁剪视频长度
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-shortest',  # 使用最短的流作为输出长度
                output_path
            ]
            
            print(f"正在合并音频和视频: {output_path}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"音视频合并成功: {output_path}")
                return output_path
            else:
                print(f"音视频合并失败: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"音视频合并出错: {e}")
            return None
    
    def process_long_news(self, news_text: str, project_name: str = None, calibrate: bool = True,
                         add_subtitles: bool = True, subtitle_format: str = "srt",
                         subtitle_style: dict = None) -> dict:
        """
        处理长新闻，生成分段播报
        
        Args:
            news_text: 长新闻文本
            project_name: 项目名称（可选）
            calibrate: 是否进行语速校准
            add_subtitles: 是否添加字幕
            subtitle_format: 字幕格式 ("srt", "ass", "vtt")
            subtitle_style: 字幕样式设置
            
        Returns:
            dict: 处理结果
        """
        if project_name is None:
            project_name = f"long_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        print(f"开始处理长新闻项目: {project_name}")
        print(f"原始新闻长度: {len(news_text)} 字符")
        print(f"字幕设置: {'启用' if add_subtitles else '禁用'} ({subtitle_format})")
        
        # 步骤0: 语速校准（可选）
        if calibrate:
            print("\n=== 步骤0: 语速校准 ===")
            self.calibrate_speech_rate()
        
        # 步骤1: 智能分割文本
        print("\n=== 步骤1: 智能分割文本 ===")
        segments = self.smart_split_text(news_text)
        print(f"分割得到 {len(segments)} 个片段")
        
        # 打印分割结果预览
        for i, segment in enumerate(segments):
            estimated_duration = self.estimate_audio_duration(segment)
            print(f"片段 {i+1}: {len(segment)} 字符, 估算 {estimated_duration:.2f}秒")
            print(f"  内容: {segment}")
        
        # 步骤2: 为每个片段生成多模态内容
        print(f"\n=== 步骤2: 生成多模态内容{'（含字幕）' if add_subtitles else ''} ===")
        results = []
        
        for i, segment in enumerate(segments):
            segment_id = f"{project_name}_segment_{i+1:03d}"
            print(f"\n处理片段 {i+1}/{len(segments)}: {segment_id}")
            print(f"片段内容: {segment}")
            
            try:
                # 生成随机种子
                seed = self.generate_random_seed()
                print(f"使用随机种子: {seed}")
                
                # 生成语音
                print("生成语音...")
                voice_path, audio_duration = self.tts_module.generate_voice(
                    segment, f"{segment_id}_voice"
                )
                
                # 检查实际时长是否超限
                if audio_duration > self.max_audio_duration:
                    print(f"警告: 实际音频时长 {audio_duration:.2f}秒 超过限制 {self.max_audio_duration}秒")
                
                # 生成图片
                print("生成图片...")
                image_paths = self.news_bot.image_module.generate_image(
                    segment, f"{segment_id}_image",
                    ratio="16:9", seed=seed
                )
                
                # 生成视频（固定5秒）
                print("生成视频...")
                video_path = self.news_bot.video_module.generate_video(
                    segment, 5.0, image_paths, f"{segment_id}_video",
                    resolution="720p", ratio="16:9"
                )
                
                # 合并音频和视频
                print("合并音视频...")
                temp_video_path = os.path.join(
                    self.final_videos_dir, f"{segment_id}_temp.mp4"
                )
                
                merged_video = self.merge_audio_video(
                    voice_path, video_path, temp_video_path
                )
                
                final_video_path = None
                subtitle_path = None
                
                if merged_video and add_subtitles:
                    # 创建字幕文件
                    print("创建字幕...")
                    subtitle_base_path = os.path.join(self.subtitles_dir, f"{segment_id}_subtitle")
                    subtitle_path = self.create_subtitle_file(
                        segment, audio_duration, subtitle_base_path, subtitle_format
                    )
                    
                    # 将字幕添加到视频
                    print("添加字幕到视频...")
                    final_video_path = os.path.join(
                        self.final_videos_dir, f"{segment_id}_final.mp4"
                    )
                    
                    final_video_with_subtitles = self.add_subtitles_to_video(
                        merged_video, subtitle_path, final_video_path, subtitle_style
                    )
                    
                    if final_video_with_subtitles:
                        # 删除临时视频文件
                        if os.path.exists(temp_video_path):
                            os.remove(temp_video_path)
                        final_video_path = final_video_with_subtitles
                    else:
                        # 如果添加字幕失败，使用无字幕版本
                        print("字幕添加失败，使用无字幕版本")
                        final_video_path = temp_video_path
                
                elif merged_video:
                    # 不添加字幕，直接使用合并后的视频
                    final_video_path = os.path.join(
                        self.final_videos_dir, f"{segment_id}_final.mp4"
                    )
                    
                    # 重命名临时文件
                    if os.path.exists(temp_video_path):
                        os.rename(temp_video_path, final_video_path)
                
                segment_result = {
                    "segment_id": segment_id,
                    "segment_index": i + 1,
                    "text": segment,
                    "voice_path": voice_path,
                    "image_paths": image_paths,
                    "video_path": video_path,
                    "final_video_path": final_video_path,
                    "subtitle_path": subtitle_path,
                    "audio_duration": audio_duration,
                    "estimated_duration": self.estimate_audio_duration(segment),
                    "seed": seed,
                    "has_subtitles": add_subtitles and subtitle_path is not None,
                    "subtitle_format": subtitle_format if add_subtitles else None,
                    "status": "success" if final_video_path else "failed"
                }
                
                results.append(segment_result)
                print(f"片段 {segment_id} 处理完成")
                
            except Exception as e:
                print(f"处理片段 {segment_id} 时出错: {e}")
                segment_result = {
                    "segment_id": segment_id,
                    "segment_index": i + 1,
                    "text": segment,
                    "status": "failed",
                    "error": str(e)
                }
                results.append(segment_result)
        
        # 汇总结果
        total_segments = len(segments)
        successful_segments = len([r for r in results if r["status"] == "success"])
        
        final_result = {
            "project_name": project_name,
            "original_text": news_text,
            "original_length": len(news_text),
            "total_segments": total_segments,
            "successful_segments": successful_segments,
            "estimated_chars_per_second": self.estimated_chars_per_second,
            "max_audio_duration": self.max_audio_duration,
            "subtitles_enabled": add_subtitles,
            "subtitle_format": subtitle_format,
            "segments": results,
            "output_directory": self.final_videos_dir,
            "subtitles_directory": self.subtitles_dir,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 保存结果到JSON文件
        result_file = os.path.join(self.output_dir, f"{project_name}_result.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, ensure_ascii=False, indent=2)
        
        print(f"\n=== 处理完成 ===")
        print(f"项目名称: {project_name}")
        print(f"总片段数: {total_segments}")
        print(f"成功片段数: {successful_segments}")
        print(f"字幕状态: {'已添加' if add_subtitles else '未添加'}")
        print(f"输出目录: {self.final_videos_dir}")
        print(f"字幕目录: {self.subtitles_dir}")
        print(f"结果文件: {result_file}")
        
        return final_result

def main():
    """主函数"""
    # 长AI新闻示例
    long_ai_news = """
    OpenAI最新发布的GPT-4 Turbo模型在多个维度实现了重大突破，不仅在语言理解和生成能力上有显著提升，还在代码编写、数学推理和创意写作等专业领域展现出前所未有的性能。该模型支持128K上下文长度，能够处理相当于300页文本的信息量，为复杂的文档分析和长篇内容创作提供了强大支持。
    """
    
    # 创建处理器
    processor = LongNewsProcessor(
        max_chars_per_segment=25,  # 每段最多25字符
        max_audio_duration=4.8    # 音频最长4.8秒，确保视频为5秒
    )
    
    # 自定义字幕样式
    custom_subtitle_style = {
        'fontsize': 24,
        'fontcolor': 'yellow',
        'box': 1,
        'boxcolor': 'black@0.7',
        'boxborderw': 3
    }
    
    # 处理长新闻（启用字幕）
    result = processor.process_long_news(
        long_ai_news, 
        "ai_industry_report_2024_with_subtitles_v2",
        calibrate=True,
        add_subtitles=True,          # 启用字幕
        subtitle_format="srt",       # 使用SRT格式
        subtitle_style=custom_subtitle_style  # 自定义样式
    )
    
    # 打印结果摘要
    print("\n" + "="*60)
    print("处理结果摘要:")
    print(f"项目名称: {result['project_name']}")
    print(f"原始文本长度: {result['original_length']} 字符")
    print(f"分割片段数: {result['total_segments']}")
    print(f"成功处理: {result['successful_segments']}")
    print(f"字幕状态: {'已启用' if result['subtitles_enabled'] else '未启用'}")
    print(f"字幕格式: {result.get('subtitle_format', '无')}")
    print(f"语速参数: {result['estimated_chars_per_second']:.2f} 字符/秒")
    print(f"输出目录: {result['output_directory']}")
    print(f"字幕目录: {result['subtitles_directory']}")
    
    # 列出生成的视频文件
    print("\n生成的视频文件:")
    for i, segment in enumerate(result['segments']):
        if segment['status'] == 'success':
            subtitle_status = "有字幕" if segment.get('has_subtitles') else "无字幕"
            print(f"{i+1:2d}. {segment['segment_id']}: {segment['final_video_path']} ({subtitle_status})")
            print(f"    内容: {segment['text']}")
            print(f"    估算时长: {segment['estimated_duration']:.2f}秒, 实际时长: {segment['audio_duration']:.2f}秒")
            if segment.get('subtitle_path'):
                print(f"    字幕文件: {segment['subtitle_path']}")
        else:
            print(f"{i+1:2d}. {segment['segment_id']}: 处理失败")

if __name__ == "__main__":
    main()