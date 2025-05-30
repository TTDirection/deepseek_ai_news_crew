import os
import re
import json
import subprocess
from typing import List, Dict, Any, Optional

class SubtitleProcessor:
    """字幕处理器，负责生成和处理字幕"""
    
    def __init__(self, output_dir: str = "output/subtitles"):
        """初始化字幕处理器
        
        Args:
            output_dir: 字幕输出目录
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def split_text_for_subtitles(self, text: str, max_chars_per_line: int) -> List[str]:
        """为字幕分割文本
        
        Args:
            text: 要分割的文本
            max_chars_per_line: 每行最大字符数
            
        Returns:
            List[str]: 分割后的文本行
        """
        if len(text) <= max_chars_per_line:
            return [text]
        
        # 简单字幕分行方案
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
    
    def create_subtitle_file(self, text: str, audio_duration: float, output_path: str, 
                           subtitle_format: str = "srt") -> str:
        """创建字幕文件
        
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
        """创建SRT格式字幕文件
        
        Args:
            text: 字幕文本
            audio_duration: 音频时长
            output_path: 输出文件路径（不含扩展名）
            
        Returns:
            str: 字幕文件路径
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
        """创建ASS格式字幕文件（支持更丰富的样式）
        
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
        """创建VTT格式字幕文件
        
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
        """将字幕添加到视频中
        
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
        """使用简化方法添加字幕（fallback方法）
        
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