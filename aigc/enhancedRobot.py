#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import shutil
import subprocess
import concurrent.futures
import logging
import math
import uuid
import time
from datetime import datetime
from airobot import MultimodalNewsBot

MAX_CHARS_PER_SEGMENT = 42
MAX_WORKERS = 4
TMP_DIR_ROOT = "output/segments"
MAX_SEGMENT_DURATION = 10.0        # 秒
TRANSITION_DURATION = 1.0          # 秒
LOG_FILE = "news_generation.log"
VIDEO_BUFFER_RATIO = 1.3           # 视频生成时长缓冲比例

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


def generate_unique_id():
    """生成唯一标识符"""
    return f"{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}"


def run_cmd(cmd: list[str], cwd=None):
    subprocess.run(cmd, check=True, cwd=cwd)


def get_media_duration(path: str) -> float:
    """ffprobe 读取时长（秒）"""
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ])
    return float(out.strip())


def get_media_info(path: str) -> dict:
    """获取媒体文件的详细信息"""
    try:
        # 获取基本信息
        duration = get_media_duration(path)
        
        # 获取帧率和分辨率（如果是视频）
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-of", "csv=s=x:p=0",
            path
        ], capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split('x')
            if len(parts) >= 3:
                width, height, fps = parts[0], parts[1], parts[2]
                return {
                    "duration": duration,
                    "width": int(width) if width.isdigit() else None,
                    "height": int(height) if height.isdigit() else None,
                    "fps": fps
                }
        
        return {"duration": duration}
    except Exception as e:
        logging.warning(f"Failed to get media info for {path}: {e}")
        return {"duration": 0}


def extend_video_to_duration(video_path: str, target_duration: float, output_path: str):
    """将视频扩展到目标时长"""
    current_duration = get_media_duration(video_path)
    
    if current_duration >= target_duration:
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-t", f"{target_duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-an", output_path
        ]
        logging.info(f"[Video] Trim {current_duration:.2f}s → {target_duration:.2f}s")
        run_cmd(cmd)
    else:
        loops_needed = math.ceil(target_duration / current_duration)
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", str(loops_needed - 1),
            "-i", video_path,
            "-t", f"{target_duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-an", output_path
        ]
        logging.info(f"[Video] Loop {current_duration:.2f}s × {loops_needed} → {target_duration:.2f}s")
        run_cmd(cmd)


def create_aligned_video(silent_video: str, audio_duration: float, output: str):
    """根据音频时长调整视频"""
    video_duration = get_media_duration(silent_video)
    
    if abs(video_duration - audio_duration) < 0.1:
        shutil.copy(silent_video, output)
        logging.info(f"[Video] Duration match {video_duration:.2f}s ≈ {audio_duration:.2f}s")
    elif video_duration > audio_duration:
        cmd = [
            "ffmpeg", "-y", "-i", silent_video,
            "-t", f"{audio_duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-an", output
        ]
        logging.info(f"[Video] Trim {video_duration:.2f}s → {audio_duration:.2f}s")
        run_cmd(cmd)
    else:
        loops_needed = math.ceil(audio_duration / video_duration)
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", str(loops_needed - 1),
            "-i", silent_video,
            "-t", f"{audio_duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
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
    video_path = os.path.abspath(video_path)
    srt_path = os.path.abspath(srt_path)
    output_path = os.path.abspath(output_path)
    
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if not os.path.exists(srt_path):
        raise FileNotFoundError(f"Subtitle file not found: {srt_path}")
    
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles='{srt_path}':force_style='FontSize=24,PrimaryColour=&Hffffff,OutlineColour=&H000000,Outline=2'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "copy",
        output_path
    ]
    
    logging.info(f"[Subtitle] Add subtitles → {output_path}")
    run_cmd(cmd)


def merge_audio_video_precise(video_path: str, audio_path: str, output_path: str):
    """精确合并音视频"""
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    video_duration = get_media_duration(video_path)
    audio_duration = get_media_duration(audio_path)
    
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest",
        "-avoid_negative_ts", "make_zero",
        "-vsync", "cfr",
        output_path
    ]
    logging.info(f"[Merge] Sync A({audio_duration:.2f}s)+V({video_duration:.2f}s) → {output_path}")
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
    
    num_parts = math.ceil(duration / max_duration)
    part_duration = duration / num_parts
    
    parts = []
    for i in range(num_parts):
        start_time = i * part_duration
        unique_id = generate_unique_id()
        part_path = os.path.join(tmp_dir, f"{base_name}_part{i+1}_{unique_id}.mp4")
        
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


def create_debug_info_file(tmp_dir: str, idx: int, unique_id: str, info: dict):
    """创建调试信息文件"""
    debug_file = os.path.join(tmp_dir, f"seg_{idx:02d}_debug_{unique_id}.txt")
    with open(debug_file, "w", encoding="utf-8") as f:
        f.write(f"=== Segment {idx} Debug Info ===\n")
        f.write(f"Unique ID: {unique_id}\n")
        f.write(f"Text: {info.get('text', '')}\n")
        f.write(f"Timestamp: {datetime.now()}\n\n")
        
        for stage, data in info.get('stages', {}).items():
            f.write(f"--- {stage} ---\n")
            for key, value in data.items():
                f.write(f"{key}: {value}\n")
            f.write("\n")


def generate_single_segment(args):
    idx, seg_text, ts, tmp = args
    unique_id = generate_unique_id()
    bot = MultimodalNewsBot()
    
    # 创建调试信息字典
    debug_info = {
        'text': seg_text,
        'stages': {}
    }
    
    logging.info(f"[Seg {idx}] Processing: {seg_text[:50]}...")
    
    try:
        # 1) 生成音频
        audio_path = bot.generate_voice(seg_text, f"{ts}_{idx:02d}_{unique_id}")
        audio_duration = bot.get_audio_duration(audio_path)
        audio_info = get_media_info(audio_path)
        
        debug_info['stages']['01_audio'] = {
            'path': audio_path,
            'duration': audio_duration,
            'info': audio_info
        }
        
        logging.info(f"[Seg {idx}] Audio generated: {audio_duration:.2f}s → {audio_path}")
        
        # 2) 生成视频（静默）
        res = bot.generate_news_report(seg_text)
        if res.get("status") != "success":
            raise RuntimeError(res.get("error", "unknown"))
        original_video = res["video_path"]
        
        if not os.path.exists(original_video):
            raise FileNotFoundError(f"Generated video not found: {original_video}")
        
        original_duration = get_media_duration(original_video)
        original_info = get_media_info(original_video)
        
        debug_info['stages']['02_original_video'] = {
            'path': original_video,
            'duration': original_duration,
            'info': original_info
        }
        
        logging.info(f"[Seg {idx}] Original video: {original_duration:.2f}s → {original_video}")
        
        # 3) 扩展视频（如果需要）
        target_video_duration = max(audio_duration * VIDEO_BUFFER_RATIO, audio_duration + 1.0)
        
        if original_duration < target_video_duration:
            extended_video = os.path.join(tmp, f"seg_{idx:02d}_extended_{unique_id}.mp4")
            extend_video_to_duration(original_video, target_video_duration, extended_video)
            working_video = extended_video
            
            extended_info = get_media_info(extended_video)
            debug_info['stages']['03_extended_video'] = {
                'path': extended_video,
                'duration': get_media_duration(extended_video),
                'target_duration': target_video_duration,
                'info': extended_info
            }
            
            logging.info(f"[Seg {idx}] Video extended: {original_duration:.2f}s → {target_video_duration:.2f}s")
        else:
            working_video = original_video
            debug_info['stages']['03_extended_video'] = {
                'note': 'No extension needed',
                'original_sufficient': True
            }
            logging.info(f"[Seg {idx}] Video duration sufficient: {original_duration:.2f}s")
        
        # 4) 对齐视频到音频时长
        aligned_video = os.path.join(tmp, f"seg_{idx:02d}_aligned_{unique_id}.mp4")
        create_aligned_video(working_video, audio_duration, aligned_video)
        
        if not os.path.exists(aligned_video):
            raise FileNotFoundError(f"Aligned video not created: {aligned_video}")
        
        aligned_info = get_media_info(aligned_video)
        debug_info['stages']['04_aligned_video'] = {
            'path': aligned_video,
            'duration': get_media_duration(aligned_video),
            'target_duration': audio_duration,
            'info': aligned_info
        }
        
        logging.info(f"[Seg {idx}] Video aligned to audio: {audio_duration:.2f}s → {aligned_video}")
        
        # 5) 生成字幕文件
        srt_path = os.path.join(tmp, f"seg_{idx:02d}_{unique_id}.srt")
        create_subtitle_file(seg_text, audio_duration, srt_path)
        
        debug_info['stages']['05_subtitle'] = {
            'path': srt_path,
            'duration': audio_duration,
            'text': seg_text
        }
        
        # 6) 添加字幕到视频
        video_with_subs = os.path.join(tmp, f"seg_{idx:02d}_subtitled_{unique_id}.mp4")
        add_subtitles_to_video(aligned_video, srt_path, video_with_subs)
        
        if not os.path.exists(video_with_subs):
            raise FileNotFoundError(f"Subtitled video not created: {video_with_subs}")
        
        subtitled_info = get_media_info(video_with_subs)
        debug_info['stages']['06_subtitled_video'] = {
            'path': video_with_subs,
            'duration': get_media_duration(video_with_subs),
            'info': subtitled_info
        }
        
        logging.info(f"[Seg {idx}] Subtitles added → {video_with_subs}")
        
        # 7) 合并音视频
        final_segment = os.path.join(tmp, f"seg_{idx:02d}_final_{unique_id}.mp4")
        merge_audio_video_precise(video_with_subs, audio_path, final_segment)
        
        if not os.path.exists(final_segment):
            raise FileNotFoundError(f"Final segment not created: {final_segment}")
        
        final_duration = get_media_duration(final_segment)
        final_info = get_media_info(final_segment)
        
        debug_info['stages']['07_final_segment'] = {
            'path': final_segment,
            'duration': final_duration,
            'audio_duration': audio_duration,
            'duration_diff': abs(final_duration - audio_duration),
            'info': final_info
        }
        
        # 8) 创建调试信息文件
        create_debug_info_file(tmp, idx, unique_id, debug_info)
        
        # 9) 验证时长同步
        if abs(final_duration - audio_duration) > 0.5:
            logging.warning(f"[Seg {idx}] ⚠️  Duration mismatch: final={final_duration:.2f}s, audio={audio_duration:.2f}s")
        else:
            logging.info(f"[Seg {idx}] ✅ Duration sync OK: {final_duration:.2f}s ≈ {audio_duration:.2f}s")
        
        # 10) 拆分长片段（如果需要）
        parts = split_long_segment(
            final_segment, audio_duration, MAX_SEGMENT_DURATION, 
            tmp, f"seg_{idx:02d}_{unique_id}"
        )
        
        logging.info(f"[Seg {idx}] ✅ Completed: {len(parts)} part(s), total {audio_duration:.2f}s")
        logging.info(f"[Seg {idx}] 📁 All files preserved in: {tmp}")
        logging.info(f"[Seg {idx}] 🐛 Debug info: seg_{idx:02d}_debug_{unique_id}.txt")
        
        return idx, parts
        
    except Exception as e:
        logging.error(f"[Seg {idx}] ❌ Failed: {e}")
        import traceback
        logging.error(f"[Seg {idx}] Traceback: {traceback.format_exc()}")
        
        # 即使失败也创建调试信息
        debug_info['error'] = str(e)
        debug_info['traceback'] = traceback.format_exc()
        create_debug_info_file(tmp, idx, unique_id, debug_info)
        
        return idx, []


def concat_videos_with_transition(videos: list[str],
                                  durations: list[float],
                                  out: str,
                                  tdur: float = TRANSITION_DURATION):
    """拼接视频，支持平滑的交叉淡入淡出转场"""
    n = len(videos)
    if n == 0:
        raise RuntimeError("No clips to concat")
    
    if n == 1:
        shutil.copy(videos[0], out)
        logging.info(f"Single clip copied → {out}")
        return

    for video in videos:
        if not os.path.exists(video):
            raise FileNotFoundError(f"Video file not found: {video}")

    cmd = ["ffmpeg", "-y"]
    for v in videos:
        cmd += ["-i", v]

    filters = []
    
    prev = "0:v"
    for i in range(1, n):
        curr = f"{i}:v"
        label = f"v{i}"
        offset = sum(durations[:i]) - tdur * (i-1)
        filters.append(
            f"[{prev}][{curr}]xfade=transition=smoothleft:"
            f"duration={tdur:.3f}:offset={offset:.3f}[{label}]"
        )
        prev = label

    audio_filters = []
    for i in range(n):
        if i == 0:
            audio_filters.append(f"[{i}:a]afade=t=out:st={durations[i]-tdur:.3f}:d={tdur:.3f}[a{i}]")
        elif i == n-1:
            audio_filters.append(f"[{i}:a]afade=t=in:st=0:d={tdur:.3f}[a{i}]")
        else:
            audio_filters.append(f"[{i}:a]afade=t=in:st=0:d={tdur:.3f},afade=t=out:st={durations[i]-tdur:.3f}:d={tdur:.3f}[a{i}]")
    
    filters.extend(audio_filters)
    
    ain = "".join(f"[a{i}]" for i in range(n))
    filters.append(f"{ain}concat=n={n}:v=0:a=1[aout]")

    fc = ";".join(filters)
    vmap = f"[{prev}]"
    amap = "[aout]"

    cmd += [
        "-filter_complex", fc,
        "-map", vmap, "-map", amap,
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-movflags", "+faststart",
        out
    ]

    logging.info(f"Concatenating {n} clips with smooth transitions → {out}")
    run_cmd(cmd)


def generate_full_news_parallel(text: str) -> str:
    segs = smart_chunk_text(text)
    logging.info(f"Text split into {len(segs)} segments")
    for i, s in enumerate(segs, 1):
        logging.info(f" [{i}] {s[:50]}{'...' if len(s)>50 else ''}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_session = generate_unique_id()
    tmp = f"{TMP_DIR_ROOT}_{ts}_{unique_session}"
    os.makedirs(tmp, exist_ok=True)
    
    logging.info(f"📁 Working directory: {tmp}")
    logging.info(f"🔧 All intermediate files will be preserved for debugging")

    tasks = [(i+1, segs[i], ts, tmp) for i in range(len(segs))]
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(generate_single_segment, task): task[0] for task in tasks}
        
        for future in concurrent.futures.as_completed(futures):
            try:
                idx, parts = future.result()
                if parts:
                    results.append((idx, parts))
                    logging.info(f"✅ Segment {idx} completed successfully")
                else:
                    logging.warning(f"❌ Segment {idx} failed to generate")
            except Exception as e:
                logging.error(f"❌ Segment processing error: {e}")

    if not results:
        raise RuntimeError("All segments failed to generate")

    results.sort(key=lambda x: x[0])
    all_videos = []
    all_durations = []
    
    for seg_idx, parts in results:
        for video_path, duration in parts:
            all_videos.append(video_path)
            all_durations.append(duration)

    total_duration = sum(all_durations)
    success_count = len([r for r in results if r[1]])
    total_count = len(segs)
    
    logging.info(f"✅ Successfully generated {success_count}/{total_count} segments")
    logging.info(f"📹 Total: {len(all_videos)} clips, {total_duration:.2f}s")
    logging.info(f"📁 All intermediate files preserved in: {tmp}")

    os.makedirs("output", exist_ok=True)
    final_output = f"output/full_news_{ts}_{unique_session}.mp4"
    concat_videos_with_transition(all_videos, all_durations, final_output)
    
    logging.info(f"🎉 Final video generated → {final_output}")
    logging.info(f"🔍 For debugging, check files in: {tmp}")
    logging.info(f"📝 Debug info files: seg_XX_debug_*.txt")
    
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