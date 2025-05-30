import re
import json
from langchain_openai import ChatOpenAI

class TextSegmenter:
    """Text segmentation module using LLM-based approach for optimal semantic chunking"""
    
    def __init__(self, max_chars_per_segment=25, max_audio_duration=4.8, chars_per_second=5.0):
        """
        Initialize text segmenter
        
        Args:
            max_chars_per_segment: Maximum characters per segment
            max_audio_duration: Maximum audio duration in seconds
            chars_per_second: Estimated characters per second for speech
        """
        self.max_chars_per_segment = max_chars_per_segment
        self.max_audio_duration = max_audio_duration
        self.estimated_chars_per_second = chars_per_second  # Ensure this is initialized with a default value
        
        # Initialize DeepSeek V3 LLM for text segmentation
        self.llm = ChatOpenAI(
            temperature=0.0,
            model="ep-20250427095319-t4sw8",  # V3:sw8,V1:7q4
            openai_api_key="5cf8e2f7-8465-4ccc-bf84-e32f05be0fb4",
            openai_api_base="https://ark.cn-beijing.volces.com/api/v3"
        )
    
    def estimate_audio_duration(self, text):
        """Estimate audio duration based on text length"""
        effective_chars = len(re.sub(r'[^\w]', '', text))
        # Ensure we have a valid value for the division
        if not self.estimated_chars_per_second or self.estimated_chars_per_second <= 0:
            self.estimated_chars_per_second = 5.0  # Default fallback
        return effective_chars / self.estimated_chars_per_second
    
    # Add the segment_text method (this was previously named differently or missing)
    def segment_text(self, text):
        """Main method to segment text using LLM-based approach"""
        if self.estimate_audio_duration(text) <= self.max_audio_duration:
            return [text]
        
        tokens = self.segment_chinese_text_with_llm(text)
        print(f"LLM segmentation complete, obtained {len(tokens)} semantic units")
        
        segments = []
        for token in tokens:
            token_duration = self.estimate_audio_duration(token)
            
            if token_duration > self.max_audio_duration:
                sub_segments = self.force_split_long_token(token)
                segments.extend(sub_segments)
            else:
                segments.append(token)
        
        return segments
        
    # Make sure all the other methods we're using are properly implemented:
    def segment_chinese_text_with_llm(self, text):
        """
        Use DeepSeek V3 LLM for Chinese text segmentation, optimized for longer segments
        """
        try:
            # Calculate estimated duration for the entire text
            total_estimated_duration = self.estimate_audio_duration(text)
            min_segments_needed = max(1, int(total_estimated_duration / self.max_audio_duration))
            
            # Construct prompt for LLM to divide text into semantically complete sentences
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
            
            # Add more explicit task description
            if self.max_audio_duration:
                prompt += f"\n每个句子的播报时长应控制在{self.max_audio_duration}秒以内，约{int(self.max_audio_duration * self.estimated_chars_per_second)}个字符。"
            
            # Call LLM to get segmentation result
            response = self.llm.invoke(prompt)
            response_text = response.content
            
            # Try to parse the entire text as JSON
            try:
                cleaned_text = response_text.strip()
                if not cleaned_text.startswith('['):
                    start_idx = cleaned_text.find('[')
                    if start_idx != -1:
                        cleaned_text = cleaned_text[start_idx:]
                if not cleaned_text.endswith(']'):
                    end_idx = cleaned_text.rfind(']')
                    if end_idx != -1:
                        cleaned_text = cleaned_text[:end_idx+1]
                
                tokens = json.loads(cleaned_text)
                if isinstance(tokens, list) and all(isinstance(item, str) for item in tokens):
                    if len(tokens) >= min(2, min_segments_needed) and all(len(token) > 0 for token in tokens):
                        print(f"Successfully segmented text using LLM, got {len(tokens)} segments")
                        return self.optimize_segments(tokens)
            except json.JSONDecodeError:
                pass
            
            # If full parsing fails, try regex extraction
            json_match = re.search(r'\[\s*"[^"]*"(?:\s*,\s*"[^"]*")*\s*\]', response_text)
            if json_match:
                json_str = json_match.group(0)
                try:
                    tokens = json.loads(json_str)
                    if isinstance(tokens, list) and all(isinstance(item, str) for item in tokens):
                        return self.optimize_segments(tokens)
                except json.JSONDecodeError:
                    print("JSON parsing error, trying alternative extraction...")
            
            # Extract content in quotes as tokens
            tokens = []
            for match in re.finditer(r'"([^"]*)"', response_text):
                token = match.group(1).strip()
                if token:
                    tokens.append(token)
            
            if tokens:
                return self.optimize_segments(tokens)
            
            # All methods failed, try simple segmentation as fallback
            print("LLM segmentation extraction failed, using simple rule-based segmentation as backup")
            segments = self.segment_chinese_text_alternative(text)
            return self.optimize_segments(segments)
            
        except Exception as e:
            print(f"LLM segmentation error: {e}")
            # Use alternative segmentation method on error
            segments = self.segment_chinese_text_alternative(text)
            return self.optimize_segments(segments)
    
    def optimize_segments(self, segments):
        """
        Optimize segmentation results by merging short segments and splitting long ones
        """
        # Define minimum segment length (character count)
        MIN_SEGMENT_LENGTH = 10
        # Define ideal segment length range
        IDEAL_MIN_LENGTH = 15
        IDEAL_MAX_LENGTH = int(self.max_audio_duration * self.estimated_chars_per_second * 0.9)  # leave 10% margin
        
        # Step 1: Flag short segments
        segments_with_flags = []
        for segment in segments:
            is_short = len(segment) < MIN_SEGMENT_LENGTH
            segments_with_flags.append({
                "text": segment,
                "is_short": is_short,
                "length": len(segment),
                "duration": self.estimate_audio_duration(segment)
            })
        
        # Step 2: Merge short segments with adjacent segments
        optimized = []
        i = 0
        while i < len(segments_with_flags):
            current = segments_with_flags[i]
            
            # If current segment is not short, or it's the last segment
            if not current["is_short"] or i == len(segments_with_flags) - 1:
                optimized.append(current["text"])
                i += 1
                continue
            
            # Try to merge with next segment
            if i + 1 < len(segments_with_flags):
                next_segment = segments_with_flags[i + 1]
                combined_text = current["text"] + next_segment["text"]
                combined_duration = self.estimate_audio_duration(combined_text)
                
                # If combined text doesn't exceed duration limit
                if combined_duration <= self.max_audio_duration:
                    optimized.append(combined_text)
                    i += 2  # Skip next segment
                    continue
            
            # If can't merge with next, try with previous (if not first segment)
            if i > 0 and optimized:
                last_segment = optimized[-1]
                combined_text = last_segment + current["text"]
                combined_duration = self.estimate_audio_duration(combined_text)
                
                # If combined text doesn't exceed duration limit
                if combined_duration <= self.max_audio_duration:
                    optimized[-1] = combined_text  # Replace previous segment
                    i += 1
                    continue
            
            # If can't merge, keep this short segment
            optimized.append(current["text"])
            i += 1
        
        # Step 3: Handle segments that are still too long
        final_segments = []
        for segment in optimized:
            segment_duration = self.estimate_audio_duration(segment)
            if segment_duration > self.max_audio_duration:
                # Force split long segment
                sub_segments = self.force_split_long_token(segment)
                final_segments.extend(sub_segments)
            else:
                final_segments.append(segment)
        
        # Step 4: Final check and optimization
        # Merge adjacent short segments (even if not "too short")
        result = []
        i = 0
        while i < len(final_segments):
            current = final_segments[i]
            current_len = len(current)
            
            # If current segment length is less than ideal minimum and not the last one
            if current_len < IDEAL_MIN_LENGTH and i < len(final_segments) - 1:
                next_segment = final_segments[i + 1]
                combined_text = current + next_segment
                combined_duration = self.estimate_audio_duration(combined_text)
                
                # If combined text doesn't exceed duration limit
                if combined_duration <= self.max_audio_duration:
                    result.append(combined_text)
                    i += 2  # Skip next segment
                    continue
            
            result.append(current)
            i += 1
        
        # Print optimization results
        print(f"Segment optimization: {len(segments)} original segments -> {len(result)} optimized segments")
        for i, segment in enumerate(result):
            print(f"  Segment {i+1}: {len(segment)} chars, estimated {self.estimate_audio_duration(segment):.2f} seconds")
        
        return result
    
    def force_split_long_token(self, token):
        """
        Intelligently split tokens that are too long, prioritizing natural breaks
        """
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
            
            # Extract JSON part
            cleaned_text = response_text.strip()
            if not cleaned_text.startswith('['):
                start_idx = cleaned_text.find('[')
                if start_idx != -1:
                    cleaned_text = cleaned_text[start_idx:]
            if not cleaned_text.endswith(']'):
                end_idx = cleaned_text.rfind(']')
                if end_idx != -1:
                    cleaned_text = cleaned_text[:end_idx+1]
            
            try:
                sub_segments = json.loads(cleaned_text)
                if isinstance(sub_segments, list) and all(isinstance(item, str) for item in sub_segments):
                    valid_segments = []
                    for segment in sub_segments:
                        if self.estimate_audio_duration(segment) <= self.max_audio_duration:
                            valid_segments.append(segment)
                        else:
                            valid_segments.extend(self.split_at_punctuation(segment))
                    
                    optimized = self.optimize_segments(valid_segments)
                    if optimized:
                        return optimized
            except:
                pass
            
            return self.split_at_punctuation(token)
            
        except Exception as e:
            print(f"LLM forced split failed: {e}")
            return self.split_at_punctuation(token)
    
    def split_at_punctuation(self, text):
        """
        Split text at punctuation marks
        """
        # Major break points (period, exclamation mark, question mark, semicolon)
        major_breaks_positions = [m.start() for m in re.finditer(r'[。！？；]', text)]
        
        # Minor break points (comma, pause mark)
        minor_breaks_positions = [m.start() for m in re.finditer(r'[，、,]', text)]
        
        # Combine all break points and sort
        all_breaks = sorted(major_breaks_positions + minor_breaks_positions)
        
        if not all_breaks:
            # If no punctuation, split by fixed length (about 15 characters)
            chars_per_segment = min(15, int(self.max_audio_duration * self.estimated_chars_per_second * 0.8))
            segments = []
            for i in range(0, len(text), chars_per_segment):
                segments.append(text[i:min(i + chars_per_segment, len(text))])
            return segments
        
        # Use break points to split text, keeping within duration limit
        segments = []
        start = 0
        current_segment = ""
        
        # Iterate through all break points
        for pos in all_breaks:
            # Text segment including the separator
            segment = text[start:pos+1]
            
            # Test if adding this segment exceeds duration limit
            test_segment = current_segment + segment
            if self.estimate_audio_duration(test_segment) <= self.max_audio_duration:
                current_segment = test_segment
            else:
                # If limit exceeded, save current accumulated segment and start new segment
                if current_segment:
                    segments.append(current_segment)
                current_segment = segment
            
            # Update start position
            start = pos + 1
        
        # Add last segment
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
        
        # Check for segments that are too short and try to merge
        return self.optimize_segments(segments)
    
    def segment_chinese_text_alternative(self, text):
        """
        Alternative segmentation method, trying to generate longer segments
        """
        # Estimate how many segments are needed
        total_duration = self.estimate_audio_duration(text)
        estimated_segments = max(1, int(total_duration / self.max_audio_duration))
        
        # Major break points (period, exclamation mark, question mark, semicolon)
        major_breaks = [m.start() for m in re.finditer(r'[。！？；]', text)]
        
        # Minor break points (comma, pause mark)
        minor_breaks = [m.start() for m in re.finditer(r'[，、,]', text)]
        
        # If too few break points, add spaces or other characters as potential break points
        all_breaks = sorted(major_breaks + minor_breaks)
        
        if not all_breaks:
            # If no punctuation, split by fixed length
            avg_len = len(text) / estimated_segments
            segments = []
            for i in range(0, len(text), int(avg_len)):
                end = min(i + int(avg_len), len(text))
                segments.append(text[i:end])
            return segments
        
        # If too many break points, select evenly distributed points
        if len(all_breaks) > estimated_segments * 2:
            ideal_indices = []
            segment_size = len(text) / estimated_segments
            for i in range(1, estimated_segments):
                ideal_pos = int(i * segment_size)
                # Find closest break point to ideal position
                closest_break = min(all_breaks, key=lambda x: abs(x - ideal_pos))
                ideal_indices.append(closest_break)
            
            segments = []
            start = 0
            for idx in sorted(ideal_indices):
                segments.append(text[start:idx+1])
                start = idx+1
            
            # Add last segment
            if start < len(text):
                segments.append(text[start:])
                
            return segments
        
        # Default case: Try to split at major break points
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
        
        # Add last segment
        if start < len(text):
            segments.append(text[start:])
        
        # If too few segments, may need further splitting
        if len(segments) < estimated_segments / 2:
            refined_segments = []
            for segment in segments:
                if self.estimate_audio_duration(segment) > self.max_audio_duration:
                    # Split by fixed length
                    chars_per_segment = int(self.max_audio_duration * self.estimated_chars_per_second)
                    for i in range(0, len(segment), chars_per_segment):
                        refined_segments.append(segment[i:i+chars_per_segment])
                else:
                    refined_segments.append(segment)
            segments = refined_segments
        
        return segments