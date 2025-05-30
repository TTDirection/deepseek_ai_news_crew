# -*- coding: utf-8 -*-
"""
long_news_processor.py

重构后的长新闻处理器，支持保留标题和序号的新闻分段、
多模态内容生成、音视频合成和字幕添加。
"""
import os
import re
import random
import subprocess
from datetime import datetime
import json

from prompt_builder import PromptBuilder
from llm_client import LLMClient
from MultimodalRobot import MultimodalNewsBot, TTSModule

class LongNewsProcessor:
    """重构后的长新闻处理器"""

    def __init__(self,
                 max_chars_per_segment: int = 20,
                 max_audio_duration: float = 4.8):
        """
        Args:
            max_chars_per_segment: 每段最大字符数（备用）
            max_audio_duration: 每段最大音频时长（秒）
        """
        self.max_chars_per_segment = max_chars_per_segment
        self.max_audio_duration = max_audio_duration
        self.news_bot = MultimodalNewsBot()
        self.tts = TTSModule()
        self.estimated_cps = 5.0  # 默认字符/秒

        # LLM 客户端
        self.llm = LLMClient()

        # 输出目录
        self.output_dir = os.path.join("output", "long_news")
        self.segments_dir = os.path.join(self.output_dir, "segments")
        self.final_videos_dir = os.path.join(self.output_dir, "final_videos")
        self.subtitles_dir = os.path.join(self.output_dir, "subtitles")
        for d in [self.output_dir, self.segments_dir,
                  self.final_videos_dir, self.subtitles_dir]:
            os.makedirs(d, exist_ok=True)

    def estimate_audio_duration(self, text: str) -> float:
        """通过字符数估算音频时长"""
        chars = len(re.sub(r'[^\w]', '', text))
        return chars / self.estimated_cps

    def parse_numbered_sections(self, text: str) -> list:
        """
        将带“## 序号. 标题”格式的新闻拆分成若干段，
        保留每段的序号和标题。
        返回列表，每项为 (header, content)。
        """
        pattern = r'(?:^|\n)(##\s*\d+\.\s*[^\n]+)([\s\S]*?)(?=(?:\n##\s*\d+\.)|\Z)'
        matches = re.findall(pattern, text)
        sections = []
        for header, body in matches:
            # 去掉 body 开头的换行
            body = body.lstrip('\n')
            sections.append((header.strip(), body.strip()))
        return sections

    def smart_split_text(self, text: str) -> list:
        """
        智能分段：先用 LLM 分割，再做长度校正
        """
        if self.estimate_audio_duration(text) <= self.max_audio_duration:
            return [text]
        prompt = PromptBuilder.build_segmentation_prompt(
            text, self.max_audio_duration, self.estimated_cps)
        tokens = self.llm.invoke(prompt)
        return self.optimize_segments(tokens)

    def optimize_segments(self, segments: list) -> list:
        """
        合并过短 & 拆分过长
        """
        MIN_LEN = 10
        IDEAL_MIN = 15
        IDEAL_MAX = int(self.max_audio_duration * self.estimated_cps * 0.9)

        # 标记短段
        tmp = []
        for seg in segments:
            tmp.append({"text": seg, "is_short": len(seg) < MIN_LEN})

        # 合并短段
        merged = []
        i = 0
        while i < len(tmp):
            cur = tmp[i]
            if not cur["is_short"] or i == len(tmp) - 1:
                merged.append(cur["text"])
                i += 1
            else:
                nxt = tmp[i + 1]
                cand = cur["text"] + nxt["text"]
                if self.estimate_audio_duration(cand) <= self.max_audio_duration:
                    merged.append(cand)
                    i += 2
                else:
                    merged.append(cur["text"])
                    i += 1

        # 拆分过长
        final = []
        for seg in merged:
            if self.estimate_audio_duration(seg) > self.max_audio_duration:
                # 先尝试 LLM 强制拆分
                prompt = PromptBuilder.build_force_split_prompt(seg)
                try:
                    sub_tokens = self.llm.invoke(prompt)
                except Exception:
                    sub_tokens = self.split_at_punctuation(seg)
                final.extend(sub_tokens)
            else:
                final.append(seg)

        # 再次合并短段
        result = []
        i = 0
        while i < len(final):
            cur = final[i]
            if len(cur) < IDEAL_MIN and i + 1 < len(final):
                cand = cur + final[i + 1]
                if self.estimate_audio_duration(cand) <= self.max_audio_duration:
                    result.append(cand)
                    i += 2
                    continue
            result.append(cur)
            i += 1

        print(f"分段优化：{len(segments)} → {len(result)}")
        return result

    def split_at_punctuation(self, text: str) -> list:
        """
        标点拆分后备方案
        """
        points = sorted([m.start() for m in re.finditer(r'[。！？；，、,]', text)])
        if not points:
            step = int(self.max_audio_duration * self.estimated_cps * 0.8)
            return [text[i:i + step] for i in range(0, len(text), step)]
        segs = []
        start = 0
        for p in points:
            part = text[start:p + 1]
            if self.estimate_audio_duration(part) <= self.max_audio_duration:
                segs.append(part)
                start = p + 1
            else:
                segs.append(part)
                start = p + 1
        if start < len(text):
            segs.append(text[start:])
        return segs

    def process_long_news(self,
                          news_text: str,
                          project_name: str = None,
                          calibrate: bool = True,
                          add_subtitles: bool = True,
                          subtitle_format: str = "srt",
                          subtitle_style: dict = None) -> dict:
        """
        处理长新闻，保留序号：
        1) 解析编号段落
        2) 对每个段落智能分段，并在首段前加回 header
        3) 多模态生成、合成、字幕
        """
        if project_name is None:
            project_name = f"long_news_{datetime.now():%Y%m%d_%H%M%S}"
        print(f"项目: {project_name}")

        # 校准语速
        if calibrate:
            print("=== 步骤0：校准语速 ===")
            self.calibrate_speech_rate()

        # 解析带序号的段落
        print("=== 步骤1：解析编号段落 ===")
        sections = self.parse_numbered_sections(news_text)
        print(f"共解析到 {len(sections)} 个编号段落")

        # 智能分段，保留 header
        print("=== 步骤2：智能分段 ===")
        segments = []
        for header, body in sections:
            print(f"处理段落：{header}")
            tokens = self.smart_split_text(body)
            # 在首个分段前加回 header
            if tokens:
                tokens[0] = f"{header} {tokens[0]}"
            segments.extend(tokens)
        print(f"总共得到 {len(segments)} 个片段")

        # 生成多模态内容并合成视频
        print("=== 步骤3：生成多模态 & 合成视频 ===")
        results = []
        for idx, segment in enumerate(segments, 1):
            sid = f"{project_name}_segment_{idx:03d}"
            print(f"\n[{idx}/{len(segments)}] {sid}: {segment[:20]}...")
            try:
                seed = self.generate_random_seed()
                # 语音
                vpath, duration = self.tts.generate_voice(segment, f"{sid}_voice")
                # 图片
                imgs = self.news_bot.image_module.generate_image(
                    segment, f"{sid}_img", ratio="16:9", seed=seed)
                # 视频（定长）
                vid = self.news_bot.video_module.generate_video(
                    segment, 5.0, imgs, f"{sid}_vid",
                    resolution="720p", ratio="16:9")
                # 合并
                tmp = os.path.join(self.final_videos_dir, f"{sid}_tmp.mp4")
                merged = self.merge_audio_video(vpath, vid, tmp)

                final_vid = None
                sub_path = None
                if merged and add_subtitles:
                    sub_base = os.path.join(self.subtitles_dir, f"{sid}_sub")
                    sub_path = self.create_subtitle_file(
                        segment, duration, sub_base, subtitle_format)
                    outp = os.path.join(self.final_videos_dir, f"{sid}_final.mp4")
                    final_vid = self.add_subtitles_to_video(
                        merged, sub_path, outp, subtitle_style)
                    if final_vid and os.path.exists(tmp):
                        os.remove(tmp)
                    if not final_vid:
                        final_vid = tmp
                elif merged:
                    final_vid = os.path.join(self.final_videos_dir, f"{sid}_final.mp4")
                    os.rename(tmp, final_vid)

                results.append({
                    "segment_id": sid,
                    "text": segment,
                    "audio_duration": duration,
                    "final_video_path": final_vid,
                    "subtitle_path": sub_path,
                    "status": "success" if final_vid else "failed"
                })
            except Exception as e:
                print(f"段落 {sid} 处理失败: {e}")
                results.append({
                    "segment_id": sid,
                    "text": segment,
                    "status": "failed",
                    "error": str(e)
                })

        # 汇总
        succ = len([r for r in results if r["status"] == "success"])
        final = {
            "project_name": project_name,
            "total_segments": len(segments),
            "successful_segments": succ,
            "segments": results,
            "output_directory": self.final_videos_dir,
            "subtitles_directory": self.subtitles_dir,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        # 保存结果
        rf = os.path.join(self.output_dir, f"{project_name}_result.json")
        with open(rf, 'w', encoding='utf-8') as f:
            json.dump(final, f, ensure_ascii=False, indent=2)
        print(f"\n处理完成，成功 {succ}/{len(segments)} 段，结果保存在 {rf}")
        return final

    def calibrate_speech_rate(self, sample_text: str = "这是一个测试语速的示例文本。") -> float:
        """调用 TTSModule 生成样本，校准 self.estimated_cps"""
        print("校准语速中...")
        vpath, dur = self.tts.generate_voice(sample_text, "calib")
        chars = len(re.sub(r'[^\w]', '', sample_text))
        cps = chars / dur
        self.estimated_cps = cps * 0.9
        if os.path.exists(vpath):
            os.remove(vpath)
        print(f"校准完成：{self.estimated_cps:.2f} 字符/秒")
        return self.estimated_cps

    def generate_random_seed(self) -> int:
        return random.randint(1, 10000)

    # 以下方法 create_subtitle_file、add_subtitles_to_video、merge_audio_video
    # 与原项目中 TotalVideoWithLLM.py 中实现一致，此处略去以保持简洁。
    # 请将原有实现复制到此处，确保功能完整。
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
    
