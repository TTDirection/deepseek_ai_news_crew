import os
import re
import subprocess

class SubtitleManager:
    """Handles subtitle creation and integration with videos"""
    
    def __init__(self, output_dir="output/subtitles"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def create_subtitle_file(self, text, audio_duration, output_path, subtitle_format="srt"):
        """
        Create subtitle file in specified format
        
        Args:
            text: Subtitle text
            audio_duration: Audio duration in seconds
            output_path: Output file path (without extension)
            subtitle_format: Subtitle format ("srt", "ass", "vtt")
            
        Returns:
            str: Subtitle file path
        """
        if subtitle_format.lower() == "srt":
            return self.create_srt_subtitle(text, audio_duration, output_path)
        elif subtitle_format.lower() == "ass":
            return self.create_ass_subtitle(text, audio_duration, output_path)
        elif subtitle_format.lower() == "vtt":
            return self.create_vtt_subtitle(text, audio_duration, output_path)
        else:
            raise ValueError(f"Unsupported subtitle format: {subtitle_format}")
    
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
    
    def create_ass_subtitle(self, text, audio_duration, output_path):
        """Create ASS format subtitle file"""
        # Implementation details...
        # This would be the same as in your original code
        # Omitted for brevity
    
    def create_vtt_subtitle(self, text, audio_duration, output_path):
        """Create VTT format subtitle file"""
        # Implementation details...
        # This would be the same as in your original code
        # Omitted for brevity
    
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
    
