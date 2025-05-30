#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import logging
import subprocess
from datetime import datetime
from airobot import MultimodalNewsBot

# 配置参数
TRANSITION_DURATION = 0.5
VIDEO_BUFFER_RATIO = 1.15  # 确保视频比音频长的比例
MAX_VIDEO_DURATION = 10.0  # 视频模型的最大时间参数
RETRY_COUNT = 3

# 设置日志 - 减少输出
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s'
)

def run_cmd(cmd: list[str], cwd=None):
    """执行命令"""
    subprocess.run(cmd, check=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def safe_get_media_duration(path: str, max_retries: int = 3) -> float:
    """安全获取媒体文件时长"""
    for attempt in range(max_retries):
        try:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Media file not found: {path}")
            time.sleep(0.5)
            result = subprocess.run([
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path
            ], capture_output=True, text=True, check=True)
            duration = float(result.stdout.strip())
            if duration > 0:
                return duration
            else:
                raise ValueError(f"Invalid duration: {duration}")
        except Exception as e:
            logging.warning(f"Attempt {attempt + 1} failed to get duration for {path}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                raise Exception(f"Could not determine duration for {path} after {max_retries} attempts")

def create_aligned_video(video_path: str, audio_duration: float, output_path: str):
    """将视频时长精确对齐到音频时长"""
    current_duration = safe_get_media_duration(video_path)
    target_duration = audio_duration + 0.3  # 添加0.3秒缓冲
    
    # 确保视频始终比音频长，然后再裁剪
    if current_duration >= target_duration:
        # 视频够长，裁剪到目标时长
        cmd = [
            "ffmpeg", "-y",
            "-ss", "0",
            "-i", video_path,
            "-t", f"{target_duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-avoid_negative_ts", "make_zero",
            "-fflags", "+genpts",
            "-an",
            output_path
        ]
        logging.info(f"[Video] Trim {current_duration:.1f}s → {target_duration:.1f}s")
    else:
        # 视频太短，循环播放
        loops_needed = int(target_duration / current_duration) + 1
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", str(loops_needed - 1),
            "-i", video_path,
            "-t", f"{target_duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-avoid_negative_ts", "make_zero",
            "-fflags", "+genpts",
            "-an", output_path
        ]
        logging.info(f"[Video] Extend {current_duration:.1f}s → {target_duration:.1f}s")
    
    run_cmd(cmd)

def format_timestamp(sec: float) -> str:
    """格式化时间戳为SRT格式"""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def split_subtitle_text(text: str, max_chars_per_line: int = 18) -> str:
    """智能分割字幕文本为多行"""
    if len(text) <= max_chars_per_line:
        return text
    
    # 尝试在标点符号处分割
    for i in range(max_chars_per_line, max(1, len(text)//3), -1):
        if text[i] in "，。！？；：、":
            line1 = text[:i+1].strip()
            line2 = text[i+1:].strip()
            if len(line2) <= max_chars_per_line * 1.2:
                return f"{line1}\\N{line2}"
    
    # 如果没有合适的标点，在中间位置分割
    mid = len(text) // 2
    for i in range(mid - 3, mid + 4):
        if i < len(text) and (text[i] in " ，、：；" or i == mid):
            line1 = text[:i].strip()
            line2 = text[i:].strip()
            return f"{line1}\\N{line2}"
    
    # 强制分割
    line1 = text[:max_chars_per_line]
    line2 = text[max_chars_per_line:]
    return f"{line1}\\N{line2}"

def create_subtitle_file(text: str, duration: float, srt_path: str):
    """创建字幕文件"""
    formatted_text = split_subtitle_text(text)
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("1\n")
        f.write(f"{format_timestamp(0)} --> {format_timestamp(duration)}\n")
        f.write(formatted_text + "\n")

def add_subtitles_to_video(video_path: str, srt_path: str, output_path: str):
    """给视频添加字幕"""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles='{srt_path}':force_style='FontSize=20,PrimaryColour=&Hffffff,OutlineColour=&H000000,Outline=2,Alignment=2,MarginV=50'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "copy",
        output_path
    ]
    logging.info(f"[Subtitle] Adding subtitles")
    run_cmd(cmd)

def merge_audio_video_precise(video_path: str, audio_path: str, output_path: str):
    """精确合并音频和视频"""
    video_duration = safe_get_media_duration(video_path)
    audio_duration = safe_get_media_duration(audio_path)
    
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-map", "0:v:0", "-map", "1:a:0",
        "-t", f"{max(video_duration, audio_duration):.3f}",
        "-avoid_negative_ts", "make_zero",
        "-fflags", "+genpts+igndts",
        "-vsync", "cfr",
        "-async", "1",
        output_path
    ]
    logging.info(f"[Merge] Syncing audio and video")
    run_cmd(cmd)

def wait_for_video_generation(bot, text: str, target_duration: int, max_wait: int = 60):
    """等待视频生成完成，确保视频时长符合要求"""
    for attempt in range(RETRY_COUNT):
        try:
            # 确保视频时长参数为小于等于10的整数，且大于音频时长
            video_duration_param = min(10, max(1, target_duration))
            logging.info(f"[Video] Requesting video with duration: {video_duration_param}s")
            
            res = bot.generate_news_report(text, video_duration=video_duration_param)
            if res.get("status") == "success":
                video_path = res["video_path"]
                for _ in range(max_wait):
                    if os.path.exists(video_path):
                        try:
                            duration = safe_get_media_duration(video_path)
                            if duration > 0:
                                return res
                        except Exception:
                            pass
                    time.sleep(1)
                raise Exception(f"Video file not accessible")
            else:
                raise Exception(res.get("error", "Video generation failed"))
        except Exception as e:
            logging.warning(f"Video generation attempt {attempt + 1} failed")
            if attempt < RETRY_COUNT - 1:
                time.sleep(2)
                continue
            else:
                raise e

def add_fade_in_out_to_segment(video_path: str, output_path: str, duration: float, fade: float = 0.5):
    """给片段添加淡入淡出效果"""
    fade = min(fade, duration / 4)  # 防止fade时长过长
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf",
        f"fade=t=in:st=0:d={fade:.3f},fade=t=out:st={duration-fade:.3f}:d={fade:.3f}",
        "-af",
        f"afade=t=in:st=0:d={fade:.3f},afade=t=out:st={duration-fade:.3f}:d={fade:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-t", f"{duration + 0.2:.3f}",
        "-movflags", "+faststart",
        output_path
    ]
    logging.info(f"[Effect] Adding fade-in/out effects")
    run_cmd(cmd)

def generate_single_segment(text: str, output_dir: str = "test_output"):
    """生成单个片段（音频+视频+字幕）"""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    segment_id = f"test_{timestamp}"
    
    bot = MultimodalNewsBot()
    
    try:
        logging.info(f"Processing text segment")
        
        # 1. 生成音频
        audio_path = bot.generate_voice(text, segment_id)
        audio_duration = bot.get_audio_duration(audio_path)
        logging.info(f"[Audio] Generated: {audio_duration:.1f}s")
        
        # 2. 计算所需视频时长，确保视频比音频长
        required_video_duration = min(10, max(1, int(audio_duration * VIDEO_BUFFER_RATIO)))
        
        # 3. 生成视频，指定时长参数
        res = wait_for_video_generation(bot, text, required_video_duration)
        original_video = res["video_path"]
        original_duration = safe_get_media_duration(original_video)
        logging.info(f"[Video] Generated: {original_duration:.1f}s")
        
        # 4. 对齐视频到音频时长
        aligned_video = os.path.join(output_dir, f"{segment_id}_aligned.mp4")
        create_aligned_video(original_video, audio_duration, aligned_video)
        
        # 5. 创建字幕文件
        srt_path = os.path.join(output_dir, f"{segment_id}.srt")
        create_subtitle_file(text, audio_duration, srt_path)
        
        # 6. 添加字幕到视频
        video_with_subs = os.path.join(output_dir, f"{segment_id}_subtitled.mp4")
        add_subtitles_to_video(aligned_video, srt_path, video_with_subs)
        
        # 7. 合并音频和视频
        final_segment = os.path.join(output_dir, f"{segment_id}_final.mp4")
        merge_audio_video_precise(video_with_subs, audio_path, final_segment)
        final_duration = safe_get_media_duration(final_segment)
        
        # 8. 添加淡入淡出效果
        fade_segment = os.path.join(output_dir, f"{segment_id}_with_fade.mp4")
        add_fade_in_out_to_segment(final_segment, fade_segment, final_duration, fade=TRANSITION_DURATION)
        
        # 验证同步
        sync_error = abs(final_duration - audio_duration)
        if sync_error > 0.05:
            logging.warning(f"Sync error: {sync_error:.3f}s")
        
        logging.info(f"✅ Segment complete")
        return fade_segment
        
    except Exception as e:
        logging.error(f"❌ Failed to generate segment")
        raise e

if __name__ == "__main__":
    # 测试文本
    test_text = "DeepSeek即将发布的R2大模型参数规模达到1.2万亿，相比前代R1的6710亿参数几乎翻倍。"
    
    try:
        output_file = generate_single_segment(test_text)
        print(f"✅ 测试完成！输出文件: {output_file}")
    except Exception as e:
        print(f"❌ 测试失败: {e}")