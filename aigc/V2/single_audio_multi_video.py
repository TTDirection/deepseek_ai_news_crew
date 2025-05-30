import os
import re
import json
import time
import math
import subprocess
from datetime import datetime
from typing import List, Tuple
from pathlib import Path
import tempfile
import shutil

# 导入现有代码中的模块
from MultimodalRobot import MultimodalNewsBot, TTSModule, VideoGenerationModule, ImageGenerationModule
from video_concatenator import VideoConcatenator

# 可选：如果需要语音识别生成字幕
try:
    from vosk import Model, KaldiRecognizer
    import wave
    import json
    import srt
    from datetime import timedelta
    VOSK_MODEL_PATH = "/home/taotao/Desktop/PythonProject/deepseek_ai_news_crew/aigc/models/vosk-model-small-cn-0.22"
    VOSK_AVAILABLE = True
except ImportError:
    print("警告：未找到Vosk模块，将使用替代方法生成字幕")
    VOSK_AVAILABLE = False

class UnifiedNewsVideoGenerator:
    """
    统一的新闻视频生成器
    基于新需求:
    1. 一次性生成完整音频
    2. 分段生成视频（每段5秒）
    3. 拼接视频并裁剪匹配音频长度
    4. 添加字幕
    """
    
    def __init__(self):
        """初始化生成器"""
        # 创建输出目录
        self.base_dir = "output/unified_news"
        self.audio_dir = f"{self.base_dir}/audio"
        self.video_segments_dir = f"{self.base_dir}/video_segments"
        self.final_dir = f"{self.base_dir}/final"
        
        for dir_path in [self.base_dir, self.audio_dir, self.video_segments_dir, self.final_dir]:
            os.makedirs(dir_path, exist_ok=True)
            
        # 初始化组件
        self.news_bot = MultimodalNewsBot()  # 使用完整的新闻机器人
        self.tts_module = TTSModule()
        self.image_module = ImageGenerationModule()  # 直接初始化图像模块
        self.video_module = VideoGenerationModule()  # 直接初始化视频模块
        self.video_concatenator = VideoConcatenator(output_dir=f"{self.base_dir}/concatenated")
    
    def generate_full_audio(self, news_text: str, project_name: str) -> Tuple[str, float]:
        """
        一次性生成完整音频文件
        
        Args:
            news_text: 新闻文本
            project_name: 项目名称
            
        Returns:
            Tuple[str, float]: (音频文件路径, 音频时长)
        """
        print(f"正在生成完整音频...")
        
        audio_filename = f"{project_name}_full_audio"
        audio_path, audio_duration = self.tts_module.generate_voice(news_text, audio_filename)
        
        print(f"完整音频已生成: {audio_path}")
        print(f"音频时长: {audio_duration:.2f}秒")
        
        return audio_path, audio_duration
    
    def split_text_for_video_segments(self, news_text: str, audio_duration: float) -> List[str]:
        """
        将新闻文本分割为适合生成短视频的片段
        
        Args:
            news_text: 新闻文本
            audio_duration: 完整音频时长
            
        Returns:
            List[str]: 分割后的文本片段列表
        """
        # 计算需要生成多少个5秒视频片段
        num_segments = math.ceil(audio_duration / 5.0)
        
        # 简单分割文本，每段对应一个视频
        # 对于中文文本，尝试按句子分割
        sentences = re.split(r'([。！？；.!?;])', news_text)
        cleaned_sentences = []
        
        # 合并句子和标点
        i = 0
        while i < len(sentences):
            if i + 1 < len(sentences) and re.match(r'[。！？；.!?;]', sentences[i+1]):
                cleaned_sentences.append(sentences[i] + sentences[i+1])
                i += 2
            else:
                if sentences[i].strip():
                    cleaned_sentences.append(sentences[i])
                i += 1
        
        # 将句子组合成大致均等的片段
        segments = []
        chars_per_segment = len(''.join(cleaned_sentences)) / num_segments
        
        current_segment = ""
        current_length = 0
        
        for sentence in cleaned_sentences:
            sentence_length = len(sentence)
            
            # 如果当前片段加上新句子超过了目标长度，并且当前片段不为空，则保存当前片段
            if current_length + sentence_length > chars_per_segment and current_segment:
                segments.append(current_segment)
                current_segment = sentence
                current_length = sentence_length
            else:
                current_segment += sentence
                current_length += sentence_length
        
        # 添加最后一个片段
        if current_segment:
            segments.append(current_segment)
        
        # 确保片段数量足够
        while len(segments) < num_segments:
            # 找到最长的片段分割
            longest_idx = max(range(len(segments)), key=lambda i: len(segments[i]))
            longest = segments[longest_idx]
            
            if len(longest) <= 10:  # 避免分割太短的片段
                # 复制最后一个片段
                segments.append(segments[-1])
            else:
                # 将最长片段分成两半
                mid = len(longest) // 2
                segments[longest_idx] = longest[:mid]
                segments.insert(longest_idx + 1, longest[mid:])
        
        # 确保片段数量不超过所需数量
        while len(segments) > num_segments:
            # 找到最短的相邻片段合并
            min_combined_len = float('inf')
            min_idx = 0
            
            for i in range(len(segments) - 1):
                combined_len = len(segments[i]) + len(segments[i+1])
                if combined_len < min_combined_len:
                    min_combined_len = combined_len
                    min_idx = i
            
            # 合并相邻的最短片段
            segments[min_idx] = segments[min_idx] + segments[min_idx+1]
            segments.pop(min_idx+1)
        
        print(f"已将新闻文本分割为 {len(segments)} 个片段用于生成视频")
        for i, segment in enumerate(segments):
            print(f"片段 {i+1}: {segment[:30]}{'...' if len(segment) > 30 else ''}")
        
        return segments
    
    def generate_video_segments(self, news_text: str, text_segments: List[str], 
                               project_name: str) -> List[str]:
        """
        为每个文本片段生成视频片段
        
        Args:
            news_text: 完整新闻文本（用于生成连贯的视觉效果）
            text_segments: 分割后的文本片段列表
            project_name: 项目名称
            
        Returns:
            List[str]: 生成的视频片段文件路径列表
        """
        print(f"开始生成视频片段...")
        
        video_paths = []
        
        for i, segment_text in enumerate(text_segments):
            segment_id = f"{project_name}_segment_{i+1:03d}"
            print(f"\n处理视频片段 {i+1}/{len(text_segments)}: {segment_id}")
            
            try:
                # 生成该片段的图片（使用项目名和序号作为种子保持一致性）
                seed = int(abs(hash(project_name + str(i))) % 10000)
                print(f"使用种子: {seed}")
                
                # 使用 MultimodalNewsBot 中的方法生成图片
                image_paths = self.image_module.generate_image(
                    segment_text, f"{segment_id}_image",
                    ratio="16:9", seed=seed
                )
                
                # 生成5秒的视频片段
                video_path = self.video_module.generate_video(
                    segment_text, 5.0, image_paths, f"{segment_id}_video",
                    resolution="720p", ratio="16:9"
                )
                
                # 将生成的视频移动到视频片段目录
                video_filename = os.path.basename(video_path)
                new_video_path = os.path.join(self.video_segments_dir, f"{segment_id}_video.mp4")
                
                if video_path != new_video_path:
                    shutil.copy(video_path, new_video_path)
                    print(f"视频片段已保存到: {new_video_path}")
                
                video_paths.append(new_video_path)
                
            except Exception as e:
                print(f"生成视频片段 {segment_id} 时出错: {e}")
                # 出错时，尝试使用NewsBot生成视频
                try:
                    print("尝试使用NewsBot生成视频片段...")
                    result = self.news_bot.generate_news_report(
                        segment_text,
                        image_ratio="16:9",
                        video_ratio="16:9",
                        video_resolution="720p"
                    )
                    
                    if result.get("video_path"):
                        video_path = result["video_path"]
                        new_video_path = os.path.join(self.video_segments_dir, f"{segment_id}_fallback_video.mp4")
                        shutil.copy(video_path, new_video_path)
                        video_paths.append(new_video_path)
                        print(f"备用视频片段已保存到: {new_video_path}")
                    else:
                        raise Exception("备用视频生成失败")
                    
                except Exception as e2:
                    print(f"备用视频生成也失败: {e2}")
                    # 生成一个简单的静态图片视频
                    try:
                        print("尝试生成静态图片视频...")
                        static_video_path = self.create_static_video(segment_text, segment_id)
                        if static_video_path:
                            video_paths.append(static_video_path)
                            print(f"静态视频已保存到: {static_video_path}")
                        else:
                            video_paths.append(None)  # 占位，保持索引一致
                    except Exception as e3:
                        print(f"静态视频生成也失败: {e3}")
                        video_paths.append(None)  # 占位，保持索引一致
        
        # 过滤掉None值
        video_paths = [path for path in video_paths if path]
        
        print(f"已生成 {len(video_paths)} 个视频片段")
        return video_paths
    
    def create_static_video(self, text: str, segment_id: str) -> str:
        """
        创建一个简单的静态图片视频（作为最后的备用方案）
        
        Args:
            text: 文本内容
            segment_id: 片段ID
            
        Returns:
            str: 生成的视频路径
        """
        output_path = os.path.join(self.video_segments_dir, f"{segment_id}_static_video.mp4")
        
        try:
            # 创建一个临时文本文件
            temp_txt = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
            temp_txt.write(text.encode('utf-8'))
            temp_txt.close()
            
            # 使用ffmpeg创建一个带文本的静态视频
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi', 
                '-i', f"color=c=black:s=1280x720:d=5", 
                '-vf', f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:fontsize=30:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:textfile='{temp_txt.name}'",
                '-c:v', 'libx264',
                '-t', '5',
                output_path
            ]
            
            subprocess.run(cmd, capture_output=True, text=True)
            
            # 删除临时文件
            os.unlink(temp_txt.name)
            
            if os.path.exists(output_path):
                return output_path
            return None
            
        except Exception as e:
            print(f"创建静态视频时出错: {e}")
            return None
    
    def concatenate_video_segments(self, video_paths: List[str], project_name: str) -> str:
        """
        拼接视频片段
        
        Args:
            video_paths: 视频片段路径列表
            project_name: 项目名称
            
        Returns:
            str: 拼接后的视频文件路径
        """
        print(f"开始拼接视频片段...")
        
        if not video_paths:
            print("没有有效的视频片段可拼接")
            return None
        
        # 准备拼接用的文件
        temp_dir = os.path.join(self.base_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # 创建文件列表
        filelist_path = os.path.join(temp_dir, "filelist.txt")
        with open(filelist_path, 'w', encoding='utf-8') as f:
            for video_path in video_paths:
                abs_path = os.path.abspath(video_path)
                escaped_path = abs_path.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        
        # 输出路径
        output_path = os.path.join(self.base_dir, f"{project_name}_concatenated.mp4")
        
        # 使用ffmpeg拼接视频
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', filelist_path,
            '-c', 'copy',
            output_path
        ]
        
        print(f"执行拼接命令...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"视频片段拼接完成: {output_path}")
            # 清理临时文件
            try:
                os.remove(filelist_path)
                os.rmdir(temp_dir)
            except:
                pass
            return output_path
        else:
            print(f"视频拼接失败: {result.stderr}")
            
            # 尝试使用另一种方法拼接
            try:
                print("尝试使用VideoConcatenator拼接...")
                # 使用之前的VideoConcatenator拼接视频
                video_files_with_index = [(path, i+1) for i, path in enumerate(video_paths)]
                concatenated_video = self.video_concatenator.concatenate_videos_simple(
                    video_files_with_index, output_path
                )
                
                if concatenated_video and os.path.exists(output_path):
                    print(f"使用VideoConcatenator拼接成功: {output_path}")
                    return output_path
                else:
                    print("VideoConcatenator拼接也失败")
                    return None
            except Exception as e:
                print(f"备用拼接方法也失败: {e}")
                return None
    
    def generate_subtitles_from_audio(self, audio_path: str, news_text: str, project_name: str) -> str:
        """
        从音频生成字幕文件
        
        Args:
            audio_path: 音频文件路径
            news_text: 原始新闻文本（用于修正字幕）
            project_name: 项目名称
            
        Returns:
            str: 生成的字幕文件路径
        """
        print(f"开始从音频生成字幕...")
        subtitle_path = os.path.join(self.base_dir, f"{project_name}_subtitles.srt")
        
        if VOSK_AVAILABLE:
            try:
                # 使用Vosk模型识别音频
                print(f"使用Vosk模型 {VOSK_MODEL_PATH} 进行语音识别...")
                model = Model(VOSK_MODEL_PATH)
                
                # 打开音频文件
                wf = wave.open(audio_path, "rb")
                
                # 检查音频格式
                if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
                    print("音频必须是16位单声道PCM格式")
                    # 转换音频格式
                    print("正在转换音频格式...")
                    converted_path = os.path.join(self.base_dir, f"{project_name}_converted.wav")
                    
                    # 使用ffmpeg转换音频格式
                    cmd = [
                        'ffmpeg', '-y',
                        '-i', audio_path,
                        '-acodec', 'pcm_s16le',
                        '-ac', '1',
                        '-ar', '16000',
                        converted_path
                    ]
                    
                    subprocess.run(cmd, capture_output=True, text=True)
                    wf.close()
                    wf = wave.open(converted_path, "rb")
                
                # 创建识别器
                rec = KaldiRecognizer(model, wf.getframerate())
                rec.SetWords(True)
                
                # 存储识别结果
                results = []
                
                # 分块读取音频并识别
                chunk_size = 4000  # 调整块大小
                while True:
                    data = wf.readframes(chunk_size)
                    if len(data) == 0:
                        break
                    
                    if rec.AcceptWaveform(data):
                        part_result = json.loads(rec.Result())
                        results.append(part_result)
                
                # 添加最后的识别结果
                part_result = json.loads(rec.FinalResult())
                results.append(part_result)
                
                # 关闭音频文件
                wf.close()
                
                # 将识别结果转换为SRT格式
                srt_entries = []
                entry_index = 1
                
                for result in results:
                    if "result" in result:
                        for i, word in enumerate(result["result"]):
                            # 每组5个词创建一个字幕条目
                            if i % 5 == 0:
                                current_words = []
                                current_start = word["start"]
                                if i + 4 < len(result["result"]):
                                    current_end = result["result"][i+4]["end"]
                                else:
                                    current_end = result["result"][-1]["end"]
                                
                            current_words.append(word["word"])
                            
                            if (i % 5 == 4) or (i == len(result["result"]) - 1):
                                # 创建字幕条目
                                entry = srt.Subtitle(
                                    index=entry_index,
                                    start=timedelta(seconds=current_start),
                                    end=timedelta(seconds=current_end),
                                    content=" ".join(current_words)
                                )
                                srt_entries.append(entry)
                                entry_index += 1
                
                # 如果识别结果太少，尝试使用原始文本创建字幕
                if len(srt_entries) <= 3 and len(news_text) > 0:
                    print("语音识别结果太少，使用原始文本创建字幕...")
                    
                    # 估算每个字符的时长
                    audio_info = self.get_audio_info(audio_path)
                    audio_duration = audio_info.get("duration", 0)
                    
                    if audio_duration > 0:
                        # 简单地按字符数分割文本，创建等时长的字幕
                        segments = self.split_text_for_subtitles(news_text)
                        segment_duration = audio_duration / len(segments)
                        
                        srt_entries = []
                        for i, segment in enumerate(segments):
                            start_time = i * segment_duration
                            end_time = (i + 1) * segment_duration
                            
                            entry = srt.Subtitle(
                                index=i+1,
                                start=timedelta(seconds=start_time),
                                end=timedelta(seconds=end_time),
                                content=segment
                            )
                            srt_entries.append(entry)
                
                # 将SRT条目写入文件
                with open(subtitle_path, 'w', encoding='utf-8') as f:
                    f.write(srt.compose(srt_entries))
                
                print(f"字幕文件已生成: {subtitle_path}")
                
            except Exception as e:
                print(f"使用Vosk生成字幕失败: {e}")
                # 使用备用方法
                subtitle_path = self.generate_subtitles_from_text(news_text, audio_path, project_name)
        else:
            # 如果没有Vosk，使用基于文本的方法
            subtitle_path = self.generate_subtitles_from_text(news_text, audio_path, project_name)
        
        return subtitle_path
    
    def generate_subtitles_from_text(self, news_text: str, audio_path: str, project_name: str) -> str:
        """
        使用原始文本生成字幕文件
        
        Args:
            news_text: 原始新闻文本
            audio_path: 音频文件路径（用于确定时长）
            project_name: 项目名称
            
        Returns:
            str: 生成的字幕文件路径
        """
        print("从原始文本生成字幕...")
        subtitle_path = os.path.join(self.base_dir, f"{project_name}_text_subtitles.srt")
        
        try:
            # 获取音频信息
            audio_info = self.get_audio_info(audio_path)
            audio_duration = audio_info.get("duration", 0)
            
            if audio_duration <= 0:
                print(f"无法获取音频时长，使用估计值")
                audio_duration = len(news_text) / 5  # 假设每秒5个字符
            
            # 将文本分割成适合字幕的片段
            subtitle_segments = self.split_text_for_subtitles(news_text)
            
            # 计算每个字幕片段的时长
            segment_duration = audio_duration / len(subtitle_segments)
            
            # 创建SRT文件
            with open(subtitle_path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(subtitle_segments):
                    start_time = i * segment_duration
                    end_time = (i + 1) * segment_duration
                    
                    # 格式化时间为SRT格式 (HH:MM:SS,mmm)
                    start_formatted = self.format_srt_time(start_time)
                    end_formatted = self.format_srt_time(end_time)
                    
                    # 写入SRT条目
                    f.write(f"{i+1}\n")
                    f.write(f"{start_formatted} --> {end_formatted}\n")
                    f.write(f"{segment}\n\n")
            
            print(f"基于文本的字幕文件已生成: {subtitle_path}")
            return subtitle_path
            
        except Exception as e:
            print(f"从文本生成字幕失败: {e}")
            
            # 创建一个简单的整段字幕作为后备
            try:
                with open(subtitle_path, 'w', encoding='utf-8') as f:
                    f.write("1\n")
                    f.write("00:00:00,000 --> 99:00:00,000\n")
                    f.write(news_text[:1000])  # 限制长度避免过长
                
                print(f"已创建备用字幕文件: {subtitle_path}")
                return subtitle_path
            except:
                print("创建备用字幕也失败")
                return None
    
    def get_audio_info(self, audio_path: str) -> dict:
        """
        获取音频文件信息
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            dict: 包含音频信息的字典
        """
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', 
                '-print_format', 'json', 
                '-show_format', '-show_streams',
                audio_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                info = json.loads(result.stdout)
                duration = float(info['format'].get('duration', 0))
                return {
                    "duration": duration,
                    "format": info.get('format', {})
                }
            else:
                print(f"获取音频信息失败: {result.stderr}")
                return {"duration": 0}
                
        except Exception as e:
            print(f"获取音频信息时出错: {e}")
            return {"duration": 0}
    
    def format_srt_time(self, seconds: float) -> str:
        """
        将秒数格式化为SRT时间格式 (HH:MM:SS,mmm)
        
        Args:
            seconds: 秒数
            
        Returns:
            str: SRT格式的时间字符串
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def split_text_for_subtitles(self, text: str, max_chars: int = 40) -> List[str]:
        """
        将文本分割为适合字幕的片段
        
        Args:
            text: 要分割的文本
            max_chars: 每个字幕片段的最大字符数
            
        Returns:
            List[str]: 分割后的字幕片段列表
        """
        segments = []
        
        # 首先按句子分割
        sentences = re.split(r'([。！？；.!?;])', text)
        
        current_segment = ""
        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            
            # 添加标点（如果有）
            if i + 1 < len(sentences):
                sentence += sentences[i+1]
            
            if len(current_segment) + len(sentence) <= max_chars:
                current_segment += sentence
            else:
                # 如果当前句子加上已有内容超过限制
                if current_segment:
                    segments.append(current_segment)
                
                # 如果单个句子超过字符限制，需要进一步分割
                if len(sentence) > max_chars:
                    # 按逗号、顿号等次要标点分割
                    subparts = re.split(r'([，、,:])', sentence)
                    
                    sub_segment = ""
                    for j in range(0, len(subparts), 2):
                        subpart = subparts[j]
                        
                        # 添加标点（如果有）
                        if j + 1 < len(subparts):
                            subpart += subparts[j+1]
                        
                        if len(sub_segment) + len(subpart) <= max_chars:
                            sub_segment += subpart
                        else:
                            if sub_segment:
                                segments.append(sub_segment)
                            
                            # 如果单个子部分仍然太长，按字符切割
                            if len(subpart) > max_chars:
                                for k in range(0, len(subpart), max_chars):
                                    segments.append(subpart[k:k+max_chars])
                                sub_segment = ""
                            else:
                                sub_segment = subpart
                    
                    if sub_segment:
                        segments.append(sub_segment)
                else:
                    current_segment = sentence
        
        if current_segment:
            segments.append(current_segment)
        
        # 如果分割结果太少，强制更细粒度的分割
        if len(segments) <= 3 and len(text) > max_chars * 5:
            new_segments = []
            for segment in segments:
                if len(segment) > max_chars:
                    # 按固定长度分割
                    for i in range(0, len(segment), max_chars):
                        new_segments.append(segment[i:i+max_chars])
                else:
                    new_segments.append(segment)
            segments = new_segments
        
        return segments
    
    def merge_audio_video_with_subtitles(self, audio_path: str, video_path: str, 
                                       subtitle_path: str, project_name: str) -> str:
        """
        合并音频、视频并添加字幕
        
        Args:
            audio_path: 音频文件路径
            video_path: 视频文件路径
            subtitle_path: 字幕文件路径
            project_name: 项目名称
            
        Returns:
            str: 最终视频文件路径
        """
        print(f"开始合并音频、视频并添加字幕...")
        
        # 先将音频合并到视频
        temp_video_path = os.path.join(self.base_dir, f"{project_name}_temp.mp4")
        final_video_path = os.path.join(self.final_dir, f"{project_name}_final.mp4")
        
        try:
            # 获取音频时长
            audio_info = self.get_audio_info(audio_path)
            audio_duration = audio_info.get("duration", 0)
            
            if audio_duration <= 0:
                print("警告：无法获取音频时长")
            
            # 合并音频和视频，并裁剪视频长度匹配音频
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-map', '0:v',
                '-map', '1:a',
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-shortest',  # 使用最短的流长度
                temp_video_path
            ]
            
            print("执行音视频合并...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"音视频合并失败: {result.stderr}")
                return None
            
            print(f"音视频合并成功: {temp_video_path}")
            
            # 添加字幕
            if subtitle_path and os.path.exists(subtitle_path):
                # 字幕文件路径转义
                if os.name == 'nt':  # Windows
                    escaped_subtitle_path = subtitle_path.replace('\\', '\\\\').replace(':', '\\:')
                else:  # Unix/Linux
                    escaped_subtitle_path = subtitle_path.replace(':', '\\:')
                
                subtitle_filter = f"subtitles='{escaped_subtitle_path}'"
                
                # 添加字幕
                cmd = [
                    'ffmpeg', '-y',
                    '-i', temp_video_path,
                    '-vf', subtitle_filter,
                    '-c:a', 'copy',
                    '-c:v', 'libx264',
                    final_video_path
                ]
                
                print("添加字幕到视频...")
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    print(f"添加字幕失败: {result.stderr}")
                    # 使用没有字幕的版本作为最终版本
                    shutil.copy(temp_video_path, final_video_path)
                else:
                    print(f"字幕添加成功: {final_video_path}")
            else:
                print("未找到字幕文件，直接使用合并后的视频")
                shutil.copy(temp_video_path, final_video_path)
            
            # 清理临时文件
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)
            
            return final_video_path
            
        except Exception as e:
            print(f"合并音视频并添加字幕时出错: {e}")
            return None
    
    def generate_news_video(self, news_text: str, project_name: str = None) -> dict:
        """
        生成完整的新闻视频
        
        Args:
            news_text: 新闻文本
            project_name: 可选的项目名称
            
        Returns:
            dict: 包含处理结果的字典
        """
        start_time = time.time()
        
        if not project_name:
            project_name = f"news_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        print(f"开始处理新闻视频项目: {project_name}")
        print(f"新闻文本: {news_text[:100]}...")
        
        try:
            # 步骤1: 生成完整音频
            audio_path, audio_duration = self.generate_full_audio(news_text, project_name)
            
            # 步骤2: 分割文本为视频片段
            text_segments = self.split_text_for_video_segments(news_text, audio_duration)
            
            # 步骤3: 生成视频片段
            video_paths = self.generate_video_segments(news_text, text_segments, project_name)
            
            # 步骤4: 拼接视频片段
            concatenated_video = self.concatenate_video_segments(video_paths, project_name)
            
            # 步骤5: 生成字幕
            subtitle_path = self.generate_subtitles_from_text(news_text, audio_path, project_name)
            
            # 步骤6: 合并音频、视频并添加字幕
            final_video = self.merge_audio_video_with_subtitles(
                audio_path, concatenated_video, subtitle_path, project_name
            )
            
            # 计算处理时间
            processing_time = time.time() - start_time
            
            # 整理结果
            result = {
                "project_name": project_name,
                "status": "success" if final_video else "failed",
                "audio_path": audio_path,
                "audio_duration": audio_duration,
                "video_segments": video_paths,
                "concatenated_video": concatenated_video,
                "subtitle_path": subtitle_path,
                "final_video": final_video,
                "processing_time": processing_time,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # 保存结果到JSON文件
            result_path = os.path.join(self.final_dir, f"{project_name}_result.json")
            with open(result_path, 'w', encoding='utf-8') as f:
                # 过滤掉无法序列化的内容
                serializable_result = {k: (str(v) if not isinstance(v, (str, int, float, bool, list, dict, type(None))) else v) 
                                    for k, v in result.items()}
                json.dump(serializable_result, ensure_ascii=False, indent=2, fp=f)
            
            print(f"\n处理完成! 总用时: {processing_time:.2f}秒")
            print(f"最终视频: {final_video}")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_result = {
                "project_name": project_name,
                "status": "error",
                "error": str(e),
                "processing_time": processing_time,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            print(f"处理过程中出现错误: {e}")
            
            # 保存错误信息
            error_path = os.path.join(self.final_dir, f"{project_name}_error.json")
            with open(error_path, 'w', encoding='utf-8') as f:
                json.dump(error_result, ensure_ascii=False, indent=2, fp=f)
            
            return error_result

def main():
    # 测试新闻文本
    test_news = """
    近日，人工智能领域迎来重大突破，OpenAI发布了最新版本的GPT-4模型，该模型在多模态能力上有了显著提升。
    新版GPT-4不仅能够处理文本，还能理解和分析图像、音频以及视频内容，这标志着AI向真正的通用人工智能又迈进了一步。
    """
    
    # 创建生成器并处理新闻
    generator = UnifiedNewsVideoGenerator()
    result = generator.generate_news_video(test_news, "ai_breakthrough_news")
    
    # 打印结果摘要
    if result["status"] == "success":
        print("\n=== 生成结果摘要 ===")
        print(f"项目名称: {result['project_name']}")
        print(f"音频时长: {result['audio_duration']:.2f}秒")
        print(f"视频片段数: {len(result['video_segments'])}")
        print(f"字幕文件: {result['subtitle_path']}")
        print(f"最终视频: {result['final_video']}")
        print(f"总处理时间: {result['processing_time']:.2f}秒")
    else:
        print("\n=== 处理失败 ===")
        print(f"错误信息: {result.get('error', '未知错误')}")

if __name__ == "__main__":
    main()