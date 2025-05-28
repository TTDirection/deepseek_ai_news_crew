#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import shutil
import subprocess
import concurrent.futures
import logging
import math
from datetime import datetime
from airobot import MultimodalNewsBot

MAX_CHARS_PER_SEGMENT = 42
MAX_WORKERS = 4
TMP_DIR_ROOT = "output/segments"
MAX_SEGMENT_DURATION = 10.0        # 秒
TRANSITION_DURATION = 1.0          # 秒
LOG_FILE = "news_generation.log"

# ---- Logging 配置 ---- 
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    filename=LOG_FILE, filemode='w'
)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s %(message)s'))
logging.getLogger().addHandler(ch)


def run_cmd(cmd: list[str]):
    subprocess.run(cmd, check=True)


def get_media_duration(path: str) -> float:
    """ffprobe 读取时长（秒）"""
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ])
    return float(out.strip())


def create_aligned_video(silent_video: str, audio_duration: float, output: str):
    """
    根据音频时长调整视频：
    1) 如果视频长于音频，裁剪到音频长度
    2) 如果视频短于音频，循环播放直到音频长度
    3) 确保输出视频完全匹配音频时长
    """
    video_duration = get_media_duration(silent_video)
    
    if abs(video_duration - audio_duration) < 0.1:
        # 时长基本一致，直接复制
        shutil.copy(silent_video, output)
        logging.info(f"[Video] Duration match {video_duration:.2f}s ≈ {audio_duration:.2f}s")
    elif video_duration > audio_duration:
        # 视频比音频长，裁剪
        cmd = [
            "ffmpeg", "-y", "-i", silent_video,
            "-t", f"{audio_duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast",
            "-an", output
        ]
        logging.info(f"[Video] Trim {video_duration:.2f}s → {audio_duration:.2f}s")
        run_cmd(cmd)
    else:
        # 视频比音频短，循环播放
        loops_needed = math.ceil(audio_duration / video_duration)
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", str(loops_needed - 1),
            "-i", silent_video,
            "-t", f"{audio_duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast",
            "-an", output
        ]
        logging.info(f"[Video] Loop {video_duration:.2f}s × {loops_needed} → {audio_duration:.2f}s")
        run_cmd(cmd)


def format_timestamp(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def create_subtitle_file(text: str, duration: float, srt_path: str):
    """生成SRT字幕文件"""
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("1\n")
        f.write(f"{format_timestamp(0)} --> {format_timestamp(duration)}\n")
        f.write(text.replace("\n", " ") + "\n")


def add_subtitles_to_video(video_path: str, srt_path: str, output_path: str):
    """给视频添加字幕"""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles={os.path.abspath(srt_path)}",
        "-c:v", "libx264", "-preset", "veryfast",
        "-c:a", "copy",
        output_path
    ]
    logging.info(f"[Subtitle] Add subtitles → {output_path}")
    run_cmd(cmd)


def merge_audio_video_precise(video_path: str, audio_path: str, output_path: str):
    """精确合并音视频，确保同步"""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",  # 直接复制视频流，避免重编码
        "-c:a", "aac", "-b:a", "128k",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest",  # 以最短的流为准
        "-avoid_negative_ts", "make_zero",
        output_path
    ]
    logging.info(f"[Merge] Precise A+V → {output_path}")
    run_cmd(cmd)


def smart_chunk_text(text: str, max_chars: int = MAX_CHARS_PER_SEGMENT) -> list[str]:
    paras = [p.strip() for p in text.splitlines() if p.strip()]
    chunks = []
    for p in paras:
        if p.startswith("#"):
            t = p.lstrip("#").strip()
            if len(t) >= 5: 
                chunks.append(t)
            continue
        sents = re.split(r"(?<=[。！？；])", p)
        cur = ""
        for s in sents:
            s = s.strip()
            if not s: 
                continue
            if len(s) > max_chars:
                if cur:
                    chunks.append(cur.strip())
                    cur = ""
                while len(s) > max_chars:
                    cut = max_chars
                    for i in range(max_chars-1, max_chars//2, -1):
                        if s[i] in "，、：；":
                            cut = i+1
                            break
                    chunks.append(s[:cut].strip())
                    s = s[cut:].strip()
                if s: 
                    cur = s
            else:
                if len(cur)+len(s) <= max_chars:
                    cur += s
                else:
                    chunks.append(cur.strip())
                    cur = s
        if cur:
            chunks.append(cur.strip())
    return [c for c in chunks if len(c) >= 5]


def split_long_segment(video_path: str, duration: float, max_duration: float, tmp_dir: str, base_name: str):
    """将超长片段拆分为多个子片段"""
    if duration <= max_duration:
        return [(video_path, duration)]
    
    # 计算需要拆分的段数
    num_parts = math.ceil(duration / max_duration)
    part_duration = duration / num_parts
    
    parts = []
    for i in range(num_parts):
        start_time = i * part_duration
        part_path = os.path.join(tmp_dir, f"{base_name}_part{i+1}.mp4")
        
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-ss", f"{start_time:.3f}",
            "-t", f"{part_duration:.3f}",
            "-c", "copy",
            part_path
        ]
        run_cmd(cmd)
        parts.append((part_path, part_duration))
        logging.info(f"[Split] Part {i+1}/{num_parts}: {part_duration:.2f}s → {part_path}")
    
    return parts


def generate_single_segment(args):
    idx, seg_text, ts, tmp = args
    bot = MultimodalNewsBot()
    logging.info(f"[Seg {idx}] Processing: {seg_text[:50]}...")
    
    try:
        # 1) 生成音频
        audio_path = bot.generate_voice(seg_text, f"{ts}_{idx:02d}")
        audio_duration = bot.get_audio_duration(audio_path)
        logging.info(f"[Seg {idx}] Audio generated: {audio_duration:.2f}s")
        
        # 2) 生成视频（静默）
        res = bot.generate_news_report(seg_text)
        if res.get("status") != "success":
            raise RuntimeError(res.get("error", "unknown"))
        original_video = res["video_path"]
        
        # 3) 调整视频时长匹配音频
        aligned_video = os.path.join(tmp, f"seg_{idx:02d}_aligned.mp4")
        create_aligned_video(original_video, audio_duration, aligned_video)
        
        # 4) 生成字幕文件
        srt_path = os.path.join(tmp, f"seg_{idx:02d}.srt")
        create_subtitle_file(seg_text, audio_duration, srt_path)
        
        # 5) 给视频添加字幕
        video_with_subs = os.path.join(tmp, f"seg_{idx:02d}_subtitled.mp4")
        add_subtitles_to_video(aligned_video, srt_path, video_with_subs)
        
        # 6) 合并音视频
        final_segment = os.path.join(tmp, f"seg_{idx:02d}_final.mp4")
        merge_audio_video_precise(video_with_subs, audio_path, final_segment)
        
        # 7) 检查是否需要拆分长片段
        parts = split_long_segment(
            final_segment, audio_duration, MAX_SEGMENT_DURATION, 
            tmp, f"seg_{idx:02d}"
        )
        
        logging.info(f"[Seg {idx}] Completed: {len(parts)} part(s), total {audio_duration:.2f}s")
        return idx, parts
        
    except Exception as e:
        logging.error(f"[Seg {idx}] Failed: {e}")
        return idx, []


def concat_videos_with_transition(videos: list[str],
                                  durations: list[float],
                                  out: str,
                                  tdur: float = TRANSITION_DURATION):
    """拼接视频，支持交叉淡入淡出转场"""
    n = len(videos)
    if n == 0:
        raise RuntimeError("No clips to concat")
    
    # 只有一段，直接拷贝
    if n == 1:
        shutil.copy(videos[0], out)
        logging.info(f"Single clip copied → {out}")
        return

    # 多段使用 filter_complex 进行转场
    cmd = ["ffmpeg", "-y"]
    for v in videos:
        cmd += ["-i", v]

    filters = []
    
    # 视频 xfade 链
    prev = "0:v"
    for i in range(1, n):
        curr = f"{i}:v"
        label = f"v{i}"
        # 计算偏移量：前面所有片段的累计时长减去已用的转场时长
        offset = sum(durations[:i]) - tdur * i
        filters.append(
            f"[{prev}][{curr}]xfade=transition=fade:"
            f"duration={tdur:.3f}:offset={offset:.3f}[{label}]"
        )
        prev = label

    # 音频 concat（直接拼接，不做交叉淡入淡出）
    ain = "".join(f"[{i}:a]" for i in range(n))
    filters.append(f"{ain}concat=n={n}:v=0:a=1[aout]")

    fc = ";".join(filters)
    vmap = f"[{prev}]"
    amap = "[aout]"

    cmd += [
        "-filter_complex", fc,
        "-map", vmap, "-map", amap,
        "-c:v", "libx264", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        out
    ]

    logging.info(f"Concatenating {n} clips with crossfade → {out}")
    run_cmd(cmd)


def generate_full_news_parallel(text: str) -> str:
    # 1) 分割文本
    segs = smart_chunk_text(text)
    logging.info(f"Text split into {len(segs)} segments")
    for i, s in enumerate(segs, 1):
        logging.info(f" [{i}] {s[:50]}{'...' if len(s)>50 else ''}")

    # 2) 创建临时目录
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp = f"{TMP_DIR_ROOT}_{ts}"
    os.makedirs(tmp, exist_ok=True)

    # 3) 并行生成所有片段
    tasks = [(i+1, segs[i], ts, tmp) for i in range(len(segs))]
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(generate_single_segment, task): task[0] for task in tasks}
        
        for future in concurrent.futures.as_completed(futures):
            idx, parts = future.result()
            if parts:
                results.append((idx, parts))

    if not results:
        raise RuntimeError("All segments failed to generate")

    # 4) 按序号排序并收集所有片段
    results.sort(key=lambda x: x[0])
    all_videos = []
    all_durations = []
    
    for seg_idx, parts in results:
        for video_path, duration in parts:
            all_videos.append(video_path)
            all_durations.append(duration)

    total_duration = sum(all_durations)
    logging.info(f"Total: {len(all_videos)} clips, {total_duration:.2f}s")

    # 5) 最终拼接
    os.makedirs("output", exist_ok=True)
    final_output = f"output/full_news_{ts}.mp4"
    concat_videos_with_transition(all_videos, all_durations, final_output)
    
    logging.info(f"✅ Final video generated → {final_output}")
    return final_output


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        txt = open(sys.argv[1], encoding="utf-8").read()
    else:
        txt = """
# 【AI日报】2025年05月28日

## 1. Anthropic发布Claude Opus 4与Sonnet 4：全球最强AI模型挑战
Anthropic发布了Claude Opus 4和Sonnet 4两款AI模型，在软件工程基准测试中表现超越OpenAI最新模型，并大幅领先Google的实验性产品。此次发布标志着科技巨头间对"最先进AI模型"称号的激烈竞争进入新阶段，展示了Anthropic在大模型架构创新和关键性能提升方面的突破性进展。

## 2. 对标GPT-4o！蚂蚁开源统一多模态大模型Ming-lite-omni
蚂蚁集团开源了统一多模态大模型Ming-lite-omni，该模型真正实现了生成和理解模型的统一架构，支持全模态输入和输出，包括音视频、图文等多种形态。这一技术突破为多模态AI发展提供了新思路，展示了中国企业在核心技术领域的创新能力。
"""
    generate_full_news_parallel(txt)