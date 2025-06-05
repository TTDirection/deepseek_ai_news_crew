import os
import re
import random
import subprocess
from datetime import datetime
from typing import List, Tuple
import json
from .MultimodalRobot import MultimodalNewsBot, TTSModule#! .
from langchain_openai import ChatOpenAI
import multiprocessing as mp
import time

# 全局函数，用于多进程处理
def estimate_audio_duration_global(text: str, estimated_chars_per_second: float) -> float:
	"""全局版本的音频时长估算函数"""
	effective_chars = len(re.sub(r'[^\w]', '', text))
	estimated_duration = effective_chars / estimated_chars_per_second
	return estimated_duration

def merge_audio_video_global(audio_path: str, video_path: str, output_path: str) -> str:
	"""全局版本的音视频合并函数"""
	try:
		# 检查音频时长是否超过5秒  #
		try:  #
			cmd_probe = [  #
				'ffprobe', '-v', 'error',  #
				'-show_entries', 'format=duration',  #
				'-of', 'default=noprint_wrappers=1:nokey=1',  #
				audio_path  #
			]  #
			audio_duration = float(subprocess.check_output(cmd_probe).decode('utf-8').strip())  #
			
			# 如果音频超过5秒，进行时间拉伸处理  #
			if audio_duration > 5.0:  #
				# 计算需要的时间比率  #
				time_ratio = 4.95 / audio_duration  # 预留0.05秒余量  #
				temp_audio_path = f"{audio_path}_temp.mp3"  #
				
				# 使用rubberband滤镜，更好地保持音色  #
				cmd_speed = [  #
					'ffmpeg', '-y',  #
					'-i', audio_path,  #
					'-filter:a', f"rubberband=tempo={1/time_ratio}:pitch=1",  #
					'-vn', temp_audio_path  #
				]  #
				
				print(f"[进程 {os.getpid()}] 音频时长为 {audio_duration:.2f}秒，超过5秒，使用rubberband时间拉伸到4.95秒")  #
				subprocess.run(cmd_speed, capture_output=True, text=True)  #
				
				# 使用调整后的音频  #
				if os.path.exists(temp_audio_path):  #
					audio_path = temp_audio_path  #
			else:  #
				print(f"[进程 {os.getpid()}] 音频时长为 {audio_duration:.2f}秒，无需调整时长")  #
		except Exception as e:  #
			print(f"[进程 {os.getpid()}] 检查音频时长出错，跳过时间调整: {e}")  #
		
		cmd = [
			'ffmpeg', '-y',
			'-i', video_path,
			'-i', audio_path,
			'-c:v', 'copy',
			'-c:a', 'aac',
			'-shortest',
			output_path
		]
		
		print(f"[进程 {os.getpid()}] 正在合并音频和视频: {output_path}")
		result = subprocess.run(cmd, capture_output=True, text=True)
		
		# 清理临时文件  #
		temp_audio_path = f"{audio_path}_temp.mp3"  #
		if os.path.exists(temp_audio_path):  #
			os.remove(temp_audio_path)  #
		
		if result.returncode == 0:
			print(f"[进程 {os.getpid()}] 音视频合并成功: {output_path}")
			return output_path
		else:
			print(f"[进程 {os.getpid()}] 音视频合并失败: {result.stderr}")
			return None
			
	except Exception as e:
		print(f"[进程 {os.getpid()}] 音视频合并出错: {e}")
		return None

def split_text_for_subtitles_global(text: str, max_chars_per_line: int) -> List[str]:
	"""全局版本的字幕分行函数"""
	if len(text) <= max_chars_per_line:
		return [text]
	
	segments = []
	sentences = re.split(r'([。！？；])', text)
	
	current_line = ""
	for i in range(0, len(sentences), 2):
		if i < len(sentences):
			part = sentences[i]
			
			if i + 1 < len(sentences):
				part += sentences[i + 1]
			
			if len(current_line + part) <= max_chars_per_line:
				current_line += part
			else:
				if current_line:
					segments.append(current_line)
				
				if len(part) > max_chars_per_line:
					for j in range(0, len(part), max_chars_per_line):
						segments.append(part[j:j+max_chars_per_line])
					current_line = ""
				else:
					current_line = part
	
	if current_line:
		segments.append(current_line)
	
	return segments

def create_subtitle_file_global(text: str, audio_duration: float, output_path: str) -> str:
	"""全局版本的字幕文件创建函数 (只支持SRT格式)"""
	return create_srt_subtitle_global(text, audio_duration, output_path)

def create_srt_subtitle_global(text: str, audio_duration: float, output_path: str) -> str:
	"""全局版本的SRT字幕创建函数"""
	subtitle_path = f"{output_path}.srt"

	def format_time(seconds):
		hours = int(seconds // 3600)
		minutes = int((seconds % 3600) // 60)
		secs = int(seconds % 60)
		millisecs = int((seconds % 1) * 1000)
		return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

	start_time = 0.0
	end_time = audio_duration

	max_chars_per_line = 20
	lines = split_text_for_subtitles_global(text, max_chars_per_line)

	with open(subtitle_path, 'w', encoding='utf-8') as f:
		f.write("1\n")
		f.write(f"{format_time(start_time)} --> {format_time(end_time)}\n")
		for line in lines:
			f.write(line.strip() + "\n")
		f.write("\n")

	print(f"[进程 {os.getpid()}] SRT字幕文件已创建: {subtitle_path}")
	return subtitle_path

def add_subtitles_to_video_global(video_path: str, subtitle_path: str, output_path: str, subtitle_style: dict = None) -> str:
	"""全局版本的字幕添加函数"""
	try:
		if not os.path.exists(subtitle_path):
			print(f"[进程 {os.getpid()}] 字幕文件不存在: {subtitle_path}")
			return None
		
		default_style = {
			'fontsize': 20,
			'fontcolor': 'white',
			'fontfile': None,
			'box': 1,
			'boxcolor': 'black@0.5',
			'boxborderw': 5,
			'x': '(w-text_w)/2',
			'y': 'h-text_h-10'
		}
		
		if subtitle_style:
			default_style.update(subtitle_style)
		
		abs_subtitle_path = os.path.abspath(subtitle_path)
		
		# 处理路径转义
		if os.name == 'nt':
			escaped_path = abs_subtitle_path.replace('\\', '\\\\').replace(':', '\\:')
		else:
			escaped_path = abs_subtitle_path.replace(':', '\\:')
		
		subtitle_filter = f"subtitles='{escaped_path}'"
		
		if default_style.get('fontsize'):
			subtitle_filter += f":force_style='Fontsize={default_style['fontsize']}'"
		
		cmd = [
			'ffmpeg', '-y',
			'-i', video_path,
			'-vf', subtitle_filter,
			'-c:a', 'copy',
			'-c:v', 'libx264',
			output_path
		]
		
		print(f"[进程 {os.getpid()}] 正在添加字幕到视频: {output_path}")
		result = subprocess.run(cmd, capture_output=True, text=True)
		
		if result.returncode == 0:
			print(f"[进程 {os.getpid()}] 字幕添加成功: {output_path}")
			return output_path
		else:
			print(f"[进程 {os.getpid()}] 字幕添加失败: {result.stderr}")
			return None
			
	except Exception as e:
		print(f"[进程 {os.getpid()}] 添加字幕时出错: {e}")
		return None

def process_single_segment_worker(segment_data):
	"""
	处理单个片段的全局函数（用于多进程）
	这是一个独立的函数，不依赖类实例，可以被pickle序列化
	
	Args:
		segment_data: 包含片段信息和配置的字典
		
	Returns:
		dict: 处理结果
	"""
	segment = segment_data['text']
	segment_index = segment_data['index']
	project_name = segment_data['project_name']
	add_subtitles = segment_data['add_subtitles']
	subtitle_style = segment_data['subtitle_style']
	max_audio_duration = segment_data['max_audio_duration']
	final_videos_dir = segment_data['final_videos_dir']
	subtitles_dir = segment_data['subtitles_dir']
	estimated_chars_per_second = segment_data['estimated_chars_per_second']
	
	segment_id = f"{project_name}_segment_{segment_index:03d}"
	
	print(f"[进程 {os.getpid()}] 开始处理片段 {segment_index}: {segment_id}")
	print(f"[进程 {os.getpid()}] 片段内容: {segment}")
	
	try:
		# 为每个进程创建独立的模块实例
		news_bot = MultimodalNewsBot()
		tts_module = TTSModule()
		
		# 生成随机种子
		seed = random.randint(1, 10000)
		print(f"[进程 {os.getpid()}] 使用随机种子: {seed}")
		
		# 生成语音
		print(f"[进程 {os.getpid()}] 生成语音...")
		voice_path, audio_duration = tts_module.generate_voice(
			segment, f"{segment_id}_voice"
		)
		
		# 检查实际时长是否超限
		if audio_duration > max_audio_duration:
			print(f"[进程 {os.getpid()}] 警告: 实际音频时长 {audio_duration:.2f}秒 超过限制 {max_audio_duration}秒")
		
		# 生成图片
		print(f"[进程 {os.getpid()}] 生成图片...")
		image_paths = news_bot.image_module.generate_image(
			segment, f"{segment_id}_image",
			ratio="16:9", seed=seed
		)
		
		# 生成视频（固定5秒）
		print(f"[进程 {os.getpid()}] 生成视频...")
		video_path = news_bot.video_module.generate_video(
			segment, 5.0, image_paths, f"{segment_id}_video",
			resolution="720p", ratio="16:9"
		)
		
		# 合并音频和视频
		print(f"[进程 {os.getpid()}] 合并音视频...")
		temp_video_path = os.path.join(
			final_videos_dir, f"{segment_id}_temp.mp4"
		)
		
		merged_video = merge_audio_video_global(
			voice_path, video_path, temp_video_path
		)
		
		final_video_path = None
		subtitle_path = None
		
		if merged_video and add_subtitles:
			# 创建字幕文件
			print(f"[进程 {os.getpid()}] 创建字幕...")
			subtitle_base_path = os.path.join(subtitles_dir, f"{segment_id}_subtitle")
			subtitle_path = create_subtitle_file_global(
				segment, audio_duration, subtitle_base_path
			)
			
			# 将字幕添加到视频
			print(f"[进程 {os.getpid()}] 添加字幕到视频...")
			final_video_path = os.path.join(
				final_videos_dir, f"{segment_id}_final.mp4"
			)
			
			final_video_with_subtitles = add_subtitles_to_video_global(
				merged_video, subtitle_path, final_video_path, subtitle_style
			)
			
			if final_video_with_subtitles:
				# 删除临时视频文件
				if os.path.exists(temp_video_path):
					os.remove(temp_video_path)
				final_video_path = final_video_with_subtitles
			else:
				# 如果添加字幕失败，使用无字幕版本
				print(f"[进程 {os.getpid()}] 字幕添加失败，使用无字幕版本")
				final_video_path = temp_video_path
		
		elif merged_video:
			# 不添加字幕，直接使用合并后的视频
			final_video_path = os.path.join(
				final_videos_dir, f"{segment_id}_final.mp4"
			)
			
			# 重命名临时文件
			if os.path.exists(temp_video_path):
				os.rename(temp_video_path, final_video_path)
		
		segment_result = {
			"segment_id": segment_id,
			"segment_index": segment_index,
			"text": segment,
			"voice_path": voice_path,
			"image_paths": image_paths,
			"video_path": video_path,
			"final_video_path": final_video_path,
			"subtitle_path": subtitle_path,
			"audio_duration": audio_duration,
			"estimated_duration": estimate_audio_duration_global(segment, estimated_chars_per_second),
			"seed": seed,
			"has_subtitles": add_subtitles and subtitle_path is not None,
			"status": "success" if final_video_path else "failed",
			"process_id": os.getpid()
		}
		
		print(f"[进程 {os.getpid()}] 片段 {segment_id} 处理完成")
		return segment_result
		
	except Exception as e:
		print(f"[进程 {os.getpid()}] 处理片段 {segment_id} 时出错: {e}")
		segment_result = {
			"segment_id": segment_id,
			"segment_index": segment_index,
			"text": segment,
			"status": "failed",
			"error": str(e),
			"process_id": os.getpid()
		}
		return segment_result


# 文本分割优化器类
class TextSegmentOptimizer:
    """文本分割优化器，用于智能分割长文本"""
    
    def __init__(self, estimated_chars_per_second=5.0, max_audio_duration=4.8):
        self.estimated_chars_per_second = estimated_chars_per_second
        self.max_audio_duration = max_audio_duration
        self.recursion_depth = 0  #* 添加递归深度计数器
        self.max_recursion_depth = 3  #* 设置最大递归深度
        
        # 初始化DeepSeek V3 LLM用于分词
        self.llm = ChatOpenAI(
            temperature=0.0,
            model="ep-20250427095319-t4sw8",  # V3:sw8,V1:7q4
            openai_api_key="5cf8e2f7-8465-4ccc-bf84-e32f05be0fb4",
            openai_api_base="https://ark.cn-beijing.volces.com/api/v3"
        )
    
    def estimate_audio_duration(self, text: str) -> float:
        """
        估算文本的音频时长
        
        Args:
            text: 文本内容
            
        Returns:
            float: 估算的音频时长（秒）
        """
        effective_chars = len(re.sub(r'[^\w]', '', text))
        estimated_duration = effective_chars / self.estimated_chars_per_second
        return estimated_duration
    
    def extract_title_and_content(self, text: str) -> List[str]:
        """
        从新闻文本中提取标题和内容
        
        Args:
            text: 完整的新闻文本
            
        Returns:
            List[str]: 包含标题和内容的列表
        """
        # 清理文本
        text = text.strip()
        
        # 尝试提取标题格式
        title_patterns = [
            # 匹配【xxx】格式的标题
            r'^(【[^】]+】[^\n]*)',
            # 匹配标题后跟日期的格式
            r'^([^。！？\n]+(?:日报|快讯|通讯|周报|月报|年报|专题)[^。！？\n]*\d{4}年\d{1,2}月\d{1,2}日)',
            # 匹配数字编号开头的标题
            r'^(\d+[\.\s、]+[^。！？\n]+)',
            # 匹配其他可能的标题格式（一行文字后面跟换行）
            r'^([^。！？\n]{5,50})\n'
        ]
        
        for pattern in title_patterns:
            match = re.match(pattern, text, re.MULTILINE)
            if match:
                title = match.group(1).strip()
                content = text[len(title):].strip()
                
                # 如果标题后跟着日期或其他时间标记，也将其视为标题的一部分
                date_match = re.match(r'^(\s*\d{4}年\d{1,2}月\d{1,2}日)', content)
                if date_match:
                    date_part = date_match.group(1).strip()
                    title = f"{title} {date_part}"
                    content = content[len(date_match.group(0)):].strip()
                
                return [title, content]
        
        # 检查是否有编号的子标题（例如新闻列表）
        subtitle_matches = re.findall(r'(\d+\.\s*[^。！？\n]+)', text)
        if subtitle_matches and len(subtitle_matches) >= 2:
            # 多条新闻的情况，尝试提取主标题
            first_subtitle_pos = text.find(subtitle_matches[0])
            if first_subtitle_pos > 10:  # 有足够的前缀可能是主标题
                title = text[:first_subtitle_pos].strip()
                content = text[first_subtitle_pos:].strip()
                return [title, content]
        
        # 如果没有明确的标题格式，返回完整文本
        return [text]
    
    def detect_list_structure_with_llm(self, text: str) -> List[str]:
        """
        使用LLM检测并提取列表结构
        
        Args:
            text: 文本内容
            
        Returns:
            List[str]: 分割后的列表项
        """
        prompt = f"""
        请分析以下文本，判断它是否包含编号列表（如"1. xxx", "2. xxx"）或其他列表形式。
        如果是列表，请提取每个完整的列表项（包括编号和完整内容），并按以下格式输出：
        
        ```json
        {{
            "is_list": true或false,
            "items": ["列表项1的完整内容", "列表项2的完整内容", ...]
        }}
        ```
        
        如果不是列表，请返回：
        ```json
        {{
            "is_list": false,
            "items": []
        }}
        ```
        
        只返回JSON格式结果，不要有任何其他文字。

        需要分析的文本:
        {text}
        """
        
        try:
            response = self.llm.invoke(prompt)
            response_text = response.content
            
            print("\n"+"-"*15+" LLM列表提取原始响应 "+"-"*15)
            print(response_text)
            print("-"*15+"\n")
            
            # 提取JSON部分
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group(0)
                result = json.loads(json_str)
                
                if result.get("is_list") and result.get("items") and len(result["items"]) >= 1:
                    print(f"LLM检测到列表结构，包含 {len(result['items'])} 个完整项目")
                    for i, item in enumerate(result["items"]):
                        print(f"  列表项 {i+1}: {item[:50]}{'...' if len(item) > 50 else ''}")
                    return result["items"]
            
            # 如果LLM处理失败，尝试使用正则表达式
            return self.detect_list_structure_with_regex(text)
            
        except Exception as e:
            print(f"使用LLM提取列表结构失败: {e}")
            # 失败时回退到正则表达式方法
            return self.detect_list_structure_with_regex(text)
    
    def detect_list_structure_with_regex(self, text: str) -> List[str]:
        """
        使用正则表达式检测列表结构并分割
        
        Args:
            text: 文本内容
            
        Returns:
            List[str]: 分割后的列表项
        """
        print("使用正则表达式提取列表结构...")
        
        # 检查是否包含编号列表（如1. xxx 2. xxx）
        # 尝试匹配完整的列表项模式
        numbered_items_pattern = r'(\d+\.\s*(?:(?!\n\d+\.).)*)'
        numbered_items = re.findall(numbered_items_pattern, text, re.DOTALL)

        if numbered_items and len(numbered_items) >= 2:
            complete_items = [item.strip() for item in numbered_items if item.strip()]
            
            print(f"检测到编号列表结构，包含 {len(complete_items)} 个完整项目")
            return complete_items
        
        # 检查是否包含其他列表标记（如•, -, * 等）
        list_markers = [r'•\s+', r'-\s+', r'\*\s+', r'·\s+']
        for marker in list_markers:
            list_items_pattern = f'({marker}(?:(?!{marker}).)*)'
            list_items = re.findall(list_items_pattern, text, re.DOTALL)
            if list_items and len(list_items) >= 2:
                clean_items = [item.strip() for item in list_items if item.strip()]
                print(f"检测到标记列表结构，包含 {len(clean_items)} 个项目")
                return clean_items
        
        return []
        
    def segment_chinese_text_with_llm(self, text: str, recursion_level=0) -> List[str]:  #* 增加递归级别参数
            """
            使用DeepSeek V3 LLM进行中文文本分词，优化生成更长的片段
            
            Args:
                text: 要分词的文本
                recursion_level: 当前递归级别
                
            Returns:
                List[str]: 分词结果
            """
            try:
                # 检查递归深度  #*
                if recursion_level >= self.max_recursion_depth:  #*
                    print(f"达到最大递归深度({self.max_recursion_depth})，直接使用简单分割")  #*
                    return self.split_at_punctuation(text)  #*
                
                # 首先尝试提取标题
                parts = self.extract_title_and_content(text)
                segments = []
                title = None  #? 明确初始化标题变量
                
                if len(parts) > 1:
                    title = parts[0]  #? 保存标题引用
                    content = parts[1]
                    print(f"检测到标题: {title}")
                    segments.append(title)  # 将标题作为单独的片段
                    text_to_process = content
                else:
                    text_to_process = parts[0]
                
                # 如果文本估计时长已经在合理范围内，不需要进一步处理  #*
                if self.estimate_audio_duration(text_to_process) <= self.max_audio_duration:  #*
                    segments.append(text_to_process)  #*
                    return segments  #*
                
                # 检查是否有列表结构
                list_items = self.detect_list_structure_with_llm(text_to_process)
                if list_items:
                    # 如果有列表结构，将每个列表项作为一个片段
                    final_segments = []  #? 创建新的最终片段列表
                    if title:  #? 确保标题被添加到最终结果中
                        final_segments.append(title)  #?
                    
                    final_segments.extend(list_items)  #? 添加列表项
                    print(f"使用列表结构分割，得到 {len(list_items)} 个片段")
                    
                    # 对较长的列表项进行进一步分割
                    refined_segments = []
                    if title:  #? 确保精细分割结果也包含标题
                        refined_segments.append(title)  #?
                        
                    for item in list_items:
                        if self.estimate_audio_duration(item) > self.max_audio_duration:
                            # 递归调用LLM分割，增加递归级别  #*
                            sub_segments = self.segment_chinese_text_with_llm(item, recursion_level + 1)  #*
                            refined_segments.extend(sub_segments)
                        else:
                            refined_segments.append(item)
                    
                    if len(refined_segments) > (len(list_items) + (1 if title else 0)):  #? 比较考虑标题
                        print(f"列表项内容较长，进一步分割得到 {len(refined_segments)} 个片段")
                        return refined_segments
                        
                    return final_segments  #? 返回包含标题的最终列表
                
                # 计算整个文本的估计时长
                total_estimated_duration = self.estimate_audio_duration(text_to_process)
                min_segments_needed = max(1, int(total_estimated_duration / self.max_audio_duration))
                
                # 构建提示词，要求LLM将文本分割成尽可能长的短句
                prompt = f"""
                请将以下中文文本分割成片段，遵循以下严格优先级规则：

                分割要求（按优先级排序）：
                1. 每个片段必须严格控制在22个字符以内，这是绝对限制
                2. 必须在自然语义停顿处断开，包括：
                - 句号、问号、感叹号等句末标点
                - 逗号、分号、冒号等句内标点
                - 明显的语义单元边界（如短语之间）
                3. 在满足上述两点的前提下，片段应尽可能接近22字上限
                4. 严禁在词组内部或破坏语义完整性的位置分割
                5. 保留原始新闻序号

                示例说明：
                ✓ "北电数智积极参与AI行业相关标准制定，" (正确：在逗号处分割，接近字数上限)
                ✗ "要素流通与安全体系建" (错误：在词组中间断开)
                ✓ "要素流通与安全体系建设、" (正确：在顿号处分割)
                ✗ "其o3模型在该标准上表现优于Claude 3.7 Sonnet和Gemini 2.5 Pro。"(错误：过长，不满足字数上限)
                ✓ "其o3模型在该标准上表现优于","Claude 3.7 Sonnet和Gemini 2.5 Pro。"(正确：在语义停顿处分割)
                返回格式要求：
                - 只返回JSON数组，格式为: ["片段1", "片段2", ...]
                - 不要返回任何其他文本或解释
                - 返回前检查每个片段是否都在自然语义边界处断开

                需要分割的文本：
                {text_to_process}
                """
                
                # 添加更明确的任务描述
                if self.max_audio_duration:
                    prompt += f"\n注意，每个句子的播报时长应控制在{self.max_audio_duration}秒以内，约{int(self.max_audio_duration * self.estimated_chars_per_second)}个字符。"
                
                # 调用LLM获取分词结果
                response = self.llm.invoke(prompt)
                response_text = response.content
                
                print("\n"+"-"*15+" LLM分词原始响应 "+"-"*15)
                print(response_text)
                print("-"*15+"\n")
                
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
                            processed_segments = self.optimize_segments(tokens)  #? 存储处理后的片段
                            final_result = []  #? 创建最终结果列表
                            if title:  #? 确保标题包含在最终结果中
                                final_result.append(title)  #?
                            final_result.extend(processed_segments)  #?
                            
                            # 打印所有分词结果
                            print("\n--------- LLM分词最终结果 ---------")
                            for i, token in enumerate(final_result):  #? 打印最终结果
                                print(f"片段 {i+1}: {token}")
                            print("----------------------------------\n")
                            return final_result  #? 返回包含标题的最终结果
                            
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
                            processed_segments = self.optimize_segments(tokens)  #? 存储处理后的片段
                            final_result = []  #? 创建最终结果列表
                            if title:  #? 确保标题包含在最终结果中
                                final_result.append(title)  #?
                            final_result.extend(processed_segments)  #?
                            
                            # 打印所有分词结果
                            print("\n--- LLM分词结果 ---")
                            for i, token in enumerate(final_result):  #? 打印最终结果
                                print(f"片段 {i+1}: {token}")
                            print("---------------------\n")
                            return final_result  #? 返回包含标题的最终结果
                    except json.JSONDecodeError:
                        print("JSON解析错误，尝试替代提取方式...")
                
                # 提取引号内的内容作为token
                tokens = []
                for match in re.finditer(r'"([^"]*)"', response_text):
                    token = match.group(1).strip()
                    if token:
                        tokens.append(token)
                
                if tokens:
                    processed_segments = self.optimize_segments(tokens)  #? 存储处理后的片段
                    final_result = []  #? 创建最终结果列表
                    if title:  #? 确保标题包含在最终结果中
                        final_result.append(title)  #?
                    final_result.extend(processed_segments)  #?
                    
                    # 打印所有分词结果
                    print("\n--- LLM分词结果(引号提取) ---")
                    for i, token in enumerate(final_result):  #? 打印最终结果
                        print(f"片段 {i+1}: {token}")
                    print("--------------------------\n")
                    return final_result  #? 返回包含标题的最终结果
                
                # 所有方法都失败，使用split_at_punctuation方法  #*
                print("LLM分词提取失败，使用标点符号分割")  #*
                additional_segments = self.split_at_punctuation(text_to_process)  #*
                
                final_result = []  #? 创建最终结果列表
                if title:  #? 确保标题包含在最终结果中
                    final_result.append(title)  #?
                final_result.extend(additional_segments)  #?
                
                return final_result  #? 返回包含标题的最终结果
                
            except Exception as e:
                print(f"LLM分词出错: {e}")
                # 出错时使用标点分割方法  #*
                final_result = []  #? 创建最终结果列表
                
                if len(parts) > 1 and parts[0]:  #? 如果有标题，确保包含在结果中
                    final_result.append(parts[0])  #?
                
                if text.strip():  #*
                    final_result.extend(self.split_at_punctuation(text.strip()))  #? 添加分割结果
                    return final_result  #? 返回包含标题的最终结果
                else:
                    return []

	
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
        IDEAL_MIN_LENGTH = 18
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
                # 如果段落过长，按照标点符号分割
                sub_segments = self.split_at_punctuation(segment)
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
        
        return result
    
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
        
        # 避免递归导致的栈溢出  #*
        return segments  #* 直接返回分割结果，不再调用optimize_segments
    
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
        
        # 重置递归深度计数器  #*
        self.recursion_depth = 0  #*
        
        # 使用LLM进行分词
        print("使用DeepSeek V3 LLM进行文本分词...")
        segments = self.segment_chinese_text_with_llm(text, 0)  #* 初始递归级别为0
        print(f"LLM分词完成，得到 {len(segments)} 个片段")
        
        return segments		
# 长新闻处理器类
class LongNewsProcessor:
	"""长新闻处理器，支持分段播报和多进程处理"""
	
	def __init__(self, max_chars_per_segment=20, max_audio_duration=4.8, max_workers=None):
		"""
		初始化长新闻处理器
		
		Args:
			max_chars_per_segment: 每段最大字符数
			max_audio_duration: 最大音频时长（秒）
			max_workers: 最大并行进程数，默认为CPU核心数
		"""
		self.max_chars_per_segment = max_chars_per_segment
		self.max_audio_duration = max_audio_duration
		
		# 设置最大并行进程数
		if max_workers is None:
			self.max_workers = min(mp.cpu_count(), 6)  # 限制最大4个进程，避免资源过度消耗
		else:
			self.max_workers = max_workers
		
		print(f"初始化多进程处理器，最大并行数: {self.max_workers}")
		
		# 初始化组件
		self.news_bot = MultimodalNewsBot()
		self.tts_module = TTSModule()
		self.text_optimizer = TextSegmentOptimizer(
			estimated_chars_per_second=5.0,  # 初始估算值
			max_audio_duration=max_audio_duration
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
		return estimate_audio_duration_global(text, self.estimated_chars_per_second)
	
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
			# 更新文本优化器的估算参数
			self.text_optimizer.estimated_chars_per_second = self.estimated_chars_per_second
			
			print(f"更新后的估算参数: {self.estimated_chars_per_second:.2f} 字符/秒")
			
			return self.estimated_chars_per_second
			
		except Exception as e:
			print(f"语速校准失败，使用默认值: {e}")
			return self.estimated_chars_per_second
	
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
		try:  #
			# 检查音频时长是否超过5秒  #
			try:  #
				cmd_probe = [  #
					'ffprobe', '-v', 'error',  #
					'-show_entries', 'format=duration',  #
					'-of', 'default=noprint_wrappers=1:nokey=1',  #
					audio_path  #
				]  #
				audio_duration = float(subprocess.check_output(cmd_probe).decode('utf-8').strip())  #
				
				# 如果音频超过5秒，进行时间拉伸处理  #
				if audio_duration > 5.0:  #
					# 计算需要的时间比率  #
					time_ratio = 4.95 / audio_duration  # 预留0.05秒余量  #
					temp_audio_path = f"{audio_path}_temp.mp3"  #
					
					# 使用rubberband滤镜，更好地保持音色  #
					cmd_speed = [  #
						'ffmpeg', '-y',  #
						'-i', audio_path,  #
						'-filter:a', f"rubberband=tempo={1/time_ratio}:pitch=1",  #
						'-vn', temp_audio_path  #
					]  #
					
					print(f"音频时长为 {audio_duration:.2f}秒，超过5秒，使用rubberband时间拉伸到4.95秒")  #
					subprocess.run(cmd_speed, capture_output=True, text=True)  #
					
					# 使用调整后的音频  #
					if os.path.exists(temp_audio_path):  #
						audio_path = temp_audio_path  #
				else:  #
					print(f"音频时长为 {audio_duration:.2f}秒，无需调整时长")  #
			except Exception as e:  #
				print(f"检查音频时长出错，跳过时间调整: {e}")  #
				
			# 使用ffmpeg合并音频和视频，并裁剪视频长度  #
			cmd = [  #
				'ffmpeg', '-y',  #
				'-i', video_path,  #
				'-i', audio_path,  #
				'-c:v', 'copy',  #
				'-c:a', 'aac',  #
				'-shortest',  # 使用最短的流作为输出长度  #
				output_path  #
			]  #
			
			print(f"正在合并音频和视频: {output_path}")  #
			result = subprocess.run(cmd, capture_output=True, text=True)  #
			
			# 清理临时文件  #
			temp_audio_path = f"{audio_path}_temp.mp3"  #
			if os.path.exists(temp_audio_path):  #
				os.remove(temp_audio_path)  #
			
			if result.returncode == 0:  #
				print(f"音视频合并成功: {output_path}")  #
				return output_path  #
			else:  #
				print(f"音视频合并失败: {result.stderr}")  #
				return None  #
					
		except Exception as e:  #
			print(f"音视频合并出错: {e}")  #
			return None  #
	
	def process_long_news(self, news_text: str, project_name: str = None, calibrate: bool = True,
						 add_subtitles: bool = True, subtitle_style: dict = None, use_multiprocessing: bool = True) -> dict:
		"""
		处理长新闻，生成分段播报（支持多进程）
		
		Args:
			news_text: 长新闻文本
			project_name: 项目名称（可选）
			calibrate: 是否进行语速校准
			add_subtitles: 是否添加字幕
			subtitle_style: 字幕样式设置
			use_multiprocessing: 是否使用多进程处理
			
		Returns:
			dict: 处理结果
		"""
		if project_name is None:
			project_name = f"long_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
		
		print(f"开始处理长新闻项目: {project_name}")
		print(f"原始新闻长度: {len(news_text)} 字符")
		print(f"字幕设置: {'启用' if add_subtitles else '禁用'}")
		print(f"多进程模式: {'启用' if use_multiprocessing else '禁用'}")
		
		# 步骤0: 语速校准（可选）
		if calibrate:
			print("\n=== 步骤0: 语速校准 ===")
			self.calibrate_speech_rate()
		
		# 步骤1: 智能分割文本
		print("\n=== 步骤1: 智能分割文本 ===")
		segments = self.text_optimizer.smart_split_text(news_text)
		print(f"分割得到 {len(segments)} 个片段")
		
		# 打印分割结果预览
		for i, segment in enumerate(segments):
			estimated_duration = self.estimate_audio_duration(segment)
			print(f"片段 {i+1}: {len(segment)} 字符, 估算 {estimated_duration:.2f}秒")
			print(f"  内容: {segment}")
		
		# 步骤2: 准备片段数据
		print(f"\n=== 步骤2: 生成多模态内容{'（含字幕）' if add_subtitles else ''} ===")
		
		segment_data_list = []
		for i, segment in enumerate(segments):
			segment_data = {
				'text': segment,
				'index': i + 1,
				'project_name': project_name,
				'add_subtitles': add_subtitles,
				'subtitle_style': subtitle_style,
				'max_audio_duration': self.max_audio_duration,
				'final_videos_dir': self.final_videos_dir,
				'subtitles_dir': self.subtitles_dir,
				'estimated_chars_per_second': self.estimated_chars_per_second
			}
			segment_data_list.append(segment_data)
		
		# 处理片段
		start_time = time.time()
		
		if use_multiprocessing and len(segments) > 1:
			print(f"使用多进程模式处理 {len(segments)} 个片段，最大并行数: {self.max_workers}")
			
			# 使用进程池处理
			with mp.Pool(processes=self.max_workers) as pool:
				results = pool.map(process_single_segment_worker, segment_data_list)
			
		else:
			print("使用单进程模式处理片段")
			results = []
			for segment_data in segment_data_list:
				result = process_single_segment_worker(segment_data)
				results.append(result)
		
		end_time = time.time()
		processing_time = end_time - start_time
		
		print(f"\n所有片段处理完成，耗时: {processing_time:.2f} 秒")
		
		# 按索引排序结果（多进程可能导致顺序混乱）
		results.sort(key=lambda x: x['segment_index'])
		
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
			"subtitle_format": "srt",
			"multiprocessing_used": use_multiprocessing,
			"max_workers": self.max_workers if use_multiprocessing else 1,
			"processing_time_seconds": processing_time,
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
		print(f"处理模式: {'多进程' if use_multiprocessing else '单进程'}")
		print(f"处理时间: {processing_time:.2f} 秒")
		print(f"字幕状态: {'已添加' if add_subtitles else '未添加'}")
		print(f"输出目录: {self.final_videos_dir}")
		print(f"字幕目录: {self.subtitles_dir}")
		print(f"结果文件: {result_file}")
		
		return final_result


def main():
	"""主函数"""
	# 带标题的AI新闻示例
	long_ai_news = """【AI日报】2025年06月04日
5. 可信数据空间等AI领域标准参编，探索北电数智的创新实践
北电数智积极参与AI行业相关标准制定，在数据要素流通与安全体系建设、算力与模型国产化技术突破及AIDC智算中心建设方面取得显著成果。这些实践为中国AI基础设施的自主可控发展提供了重要参考。
6. 水利标准AI大模型正式发布
由水利部国科司组织中国水科院自主研发的基于多源语料的"水利标准AI大模型"正式发布，标志着我国在水利标准化工具方面迈出了重要的一步。该模型将显著提升水利行业标准制定的效率和准确性。
7. 魏桥创业集团"智铝大模型"入选攻关项目
魏桥创业集团"智铝大模型"入选山东省工业领域行业大模型"揭榜挂帅"攻关项目名单。该项目将推动AI技术在铝业生产中的深度应用，提升生产效率和产品质量。
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
		"ai_daily_report_2025_06_04",
		calibrate=True,
		add_subtitles=True,          # 启用字幕
		subtitle_style=custom_subtitle_style,  # 自定义样式
		use_multiprocessing=True     # 启用多进程
	)
	
	# 打印结果摘要
	print("\n" + "="*60)
	print("处理结果摘要:")
	print(f"项目名称: {result['project_name']}")
	print(f"原始文本长度: {result['original_length']} 字符")
	print(f"分割片段数: {result['total_segments']}")
	print(f"成功处理: {result['successful_segments']}")
	print(f"字幕状态: {'已启用' if result['subtitles_enabled'] else '未启用'}")
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