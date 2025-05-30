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
from aigc.airobot import MultimodalNewsBot

MAX_CHARS_PER_SEGMENT = 42
MAX_WORKERS = 4
TMP_DIR_ROOT = "output/segments"
MAX_SEGMENT_DURATION = 10.0
TRANSITION_DURATION = 0.5          # 单段淡入淡出时长
LOG_FILE = "news_generation.log"
VIDEO_BUFFER_RATIO = 1.15
MAX_VIDEO_DURATION = 5.0
RETRY_COUNT = 3

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
    return f"{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}"


def run_cmd(cmd: list[str], cwd=None):
    subprocess.run(cmd, check=True, cwd=cwd)


def safe_get_media_duration(path: str, max_retries: int = 3) -> float:
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
        except (subprocess.CalledProcessError, ValueError, FileNotFoundError) as e:
            logging.warning(f"Attempt {attempt + 1} failed to get duration for {path}: {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                try:
                    result = subprocess.run([
                        "ffmpeg", "-i", path, "-f", "null", "-"
                    ], capture_output=True, text=True, stderr=subprocess.STDOUT)
                    for line in result.stderr.split('\n'):
                        if 'Duration:' in line:
                            duration_str = line.split('Duration:')[1].split(',')[0].strip()
                            h, m, s = duration_str.split(':')
                            return float(h) * 3600 + float(m) * 60 + float(s)
                except Exception as fallback_e:
                    logging.error(f"Fallback method also failed for {path}: {fallback_e}")
                raise Exception(f"Could not determine duration for {path} after {max_retries} attempts")


def get_media_info(path: str) -> dict:
    try:
        duration = safe_get_media_duration(path)
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


def create_precise_video_segment(video_path: str, start_time: float, duration: float, output_path: str):
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start_time:.3f}",
        "-i", video_path,
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-avoid_negative_ts", "make_zero",
        "-fflags", "+genpts",
        "-an",
        output_path
    ]
    run_cmd(cmd)


def extend_video_smoothly(video_path: str, target_duration: float, output_path: str):
    current_duration = safe_get_media_duration(video_path)
    if current_duration >= target_duration:
        create_precise_video_segment(video_path, 0, target_duration, output_path)
        logging.info(f"[Video] Precise trim {current_duration:.3f}s → {target_duration:.3f}s")
    else:
        loops_needed = math.ceil(target_duration / current_duration)
        if loops_needed <= 3:
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
        else:
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-filter:v", f"setpts={current_duration/target_duration:.3f}*PTS",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-an", output_path
            ]
        logging.info(f"[Video] Smooth extend {current_duration:.3f}s → {target_duration:.3f}s")
        run_cmd(cmd)


def create_aligned_video(video_path: str, audio_duration: float, output_path: str):
    current_duration = safe_get_media_duration(video_path)
    # Add a small buffer to ensure audio completes (0.3s extra)
    target_duration = audio_duration + 0.3
    if current_duration >= target_duration:
        create_precise_video_segment(video_path, 0, target_duration, output_path)
        logging.info(f"[Video] Precise trim {current_duration:.3f}s → {target_duration:.3f}s")
    else:
        # If video is too short, extend it
        extend_video_smoothly(video_path, target_duration, output_path)
        logging.info(f"[Video] Extended {current_duration:.3f}s → {target_duration:.3f}s")


def format_timestamp(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def split_subtitle_text(text: str, max_chars_per_line: int = 18) -> str:
    if len(text) <= max_chars_per_line:
        return text
    for i in range(max_chars_per_line, max(1, len(text)//3), -1):
        if text[i] in "，。！？；：、":
            line1 = text[:i+1].strip()
            line2 = text[i+1:].strip()
            if len(line2) <= max_chars_per_line * 1.2:
                return f"{line1}\\N{line2}"
    mid = len(text) // 2
    for i in range(mid - 3, mid + 4):
        if i < len(text) and (text[i] in " ，、：；" or i == mid):
            line1 = text[:i].strip()
            line2 = text[i:].strip()
            if len(line2) > max_chars_per_line:
                for j in range(max_chars_per_line, max(1, len(line2)//2), -1):
                    if j < len(line2) and line2[j] in "，。！？；：、":
                        line2_1 = line2[:j+1].strip()
                        line2_2 = line2[j+1:].strip()
                        return f"{line1}\\N{line2_1}\\N{line2_2}"
                line2_1 = line2[:max_chars_per_line]
                line2_2 = line2[max_chars_per_line:]
                return f"{line1}\\N{line2_1}\\N{line2_2}"
            return f"{line1}\\N{line2}"
    line1 = text[:max_chars_per_line]
    line2 = text[max_chars_per_line:]
    return f"{line1}\\N{line2}"


def create_subtitle_file(text: str, duration: float, srt_path: str):
    formatted_text = split_subtitle_text(text)
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("1\n")
        f.write(f"{format_timestamp(0)} --> {format_timestamp(duration)}\n")
        f.write(formatted_text + "\n")


def add_subtitles_to_video(video_path: str, srt_path: str, output_path: str):
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
        "-vf", f"subtitles='{srt_path}':force_style='FontSize=20,PrimaryColour=&Hffffff,OutlineColour=&H000000,Outline=2,Alignment=2,MarginV=50'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "copy",
        output_path
    ]
    logging.info(f"[Subtitle] Add subtitles → {output_path}")
    run_cmd(cmd)


def merge_audio_video_precise(video_path: str, audio_path: str, output_path: str):
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    video_duration = safe_get_media_duration(video_path)
    audio_duration = safe_get_media_duration(audio_path)
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-map", "0:v:0", "-map", "1:a:0",
        # Remove the -shortest flag to prevent audio cutoff
        "-t", f"{max(video_duration, audio_duration):.3f}",
        "-avoid_negative_ts", "make_zero",
        "-fflags", "+genpts+igndts",
        "-vsync", "cfr",
        "-async", "1",
        output_path
    ]
    logging.info(f"[Merge] Precise sync A({audio_duration:.3f}s)+V({video_duration:.3f}s) → {output_path}")
    run_cmd(cmd)


def wait_for_video_generation(bot, text: str, max_wait: int = 60):
    for attempt in range(RETRY_COUNT):
        try:
            res = bot.generate_news_report(text)
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
                raise Exception(f"Video file not accessible: {video_path}")
            else:
                raise Exception(res.get("error", "Video generation failed"))
        except Exception as e:
            logging.warning(f"Video generation attempt {attempt + 1} failed: {e}")
            if attempt < RETRY_COUNT - 1:
                time.sleep(2)
                continue
            else:
                raise e


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


def create_debug_info_file(tmp_dir: str, idx: int, unique_id: str, info: dict):
    debug_file = os.path.join(tmp_dir, f"seg_{idx:02d}_debug_{unique_id}.txt")
    with open(debug_file, "w", encoding="utf-8") as f:
        f.write(f"=== Segment {idx} Debug Info ===\n")
        f.write(f"Unique ID: {unique_id}\n")
        f.write(f"Text: {info.get('text', '')}\n")
        f.write(f"Timestamp: {datetime.now()}\n\n")
        f.write("Processing Order:\n")
        f.write("1. original_video (原始生成)\n")
        f.write("2. extended_video (扩展时长，如需要)\n") 
        f.write("3. aligned_video (精确对齐到音频)\n")
        f.write("4. subtitled_video (添加字幕)\n")
        f.write("5. final_segment (合并音频)\n\n")
        for stage, data in info.get('stages', {}).items():
            f.write(f"--- {stage} ---\n")
            for key, value in data.items():
                f.write(f"{key}: {value}\n")
            f.write("\n")

def add_fade_in_out_to_segment(video_path: str, output_path: str, duration: float, fade: float = 0.5):
    """
    给单个片段加淡入淡出效果（视频和音频），默认各0.5秒
    """
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
        # Add a slightly longer duration to ensure audio completes
        "-t", f"{duration + 0.2:.3f}",
        "-movflags", "+faststart",
        output_path
    ]
    logging.info(f"Add fade-in/out: {fade:.2f}s for {video_path} → {output_path}")
    run_cmd(cmd)

def generate_single_segment(args):
    idx, seg_text, ts, tmp = args
    unique_id = generate_unique_id()
    bot = MultimodalNewsBot()
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
        logging.info(f"[Seg {idx}] Audio: {audio_duration:.3f}s → {audio_path}")

        # 2) 生成视频（带重试机制）
        res = wait_for_video_generation(bot, seg_text)
        original_video = res["video_path"]
        original_duration = safe_get_media_duration(original_video)
        original_info = get_media_info(original_video)
        debug_info['stages']['02_original_video'] = {
            'path': original_video,
            'duration': original_duration,
            'info': original_info
        }
        logging.info(f"[Seg {idx}] Original: {original_duration:.3f}s → {original_video}")

        # 3) 确定是否需要扩展
        target_video_duration = max(audio_duration * VIDEO_BUFFER_RATIO, audio_duration + 0.3)
        target_video_duration = min(target_video_duration, MAX_VIDEO_DURATION)
        if original_duration < target_video_duration:
            extended_video = os.path.join(tmp, f"seg_{idx:02d}_extended_{unique_id}.mp4")
            extend_video_smoothly(original_video, target_video_duration, extended_video)
            working_video = extended_video
            extended_info = get_media_info(extended_video)
            debug_info['stages']['03_extended_video'] = {
                'path': extended_video,
                'duration': safe_get_media_duration(extended_video),
                'target_duration': target_video_duration,
                'info': extended_info
            }
            logging.info(f"[Seg {idx}] Extended: {original_duration:.3f}s → {target_video_duration:.3f}s")
        else:
            working_video = original_video
            debug_info['stages']['03_extended_video'] = {
                'note': 'No extension needed',
                'original_sufficient': True
            }
            logging.info(f"[Seg {idx}] No extension needed: {original_duration:.3f}s")

        # 4) 精确对齐到音频时长
        aligned_video = os.path.join(tmp, f"seg_{idx:02d}_aligned_{unique_id}.mp4")
        create_aligned_video(working_video, audio_duration, aligned_video)
        aligned_duration = safe_get_media_duration(aligned_video)
        aligned_info = get_media_info(aligned_video)
        debug_info['stages']['04_aligned_video'] = {
            'path': aligned_video,
            'duration': aligned_duration,
            'target_duration': audio_duration,
            'precision_error': abs(aligned_duration - audio_duration),
            'info': aligned_info
        }
        logging.info(f"[Seg {idx}] Aligned: {aligned_duration:.3f}s (target: {audio_duration:.3f}s)")

        # 5) 生成字幕文件
        srt_path = os.path.join(tmp, f"seg_{idx:02d}_{unique_id}.srt")
        create_subtitle_file(seg_text, audio_duration, srt_path)
        debug_info['stages']['05_subtitle'] = {
            'path': srt_path,
            'duration': audio_duration,
            'text': seg_text,
            'formatted_text': split_subtitle_text(seg_text)
        }

        # 6) 添加字幕
        video_with_subs = os.path.join(tmp, f"seg_{idx:02d}_subtitled_{unique_id}.mp4")
        add_subtitles_to_video(aligned_video, srt_path, video_with_subs)
        subtitled_duration = safe_get_media_duration(video_with_subs)
        subtitled_info = get_media_info(video_with_subs)
        debug_info['stages']['06_subtitled_video'] = {
            'path': video_with_subs,
            'duration': subtitled_duration,
            'info': subtitled_info
        }
        logging.info(f"[Seg {idx}] Subtitled: {subtitled_duration:.3f}s")

        # 7) 合并音视频
        final_segment = os.path.join(tmp, f"seg_{idx:02d}_final_{unique_id}.mp4")
        merge_audio_video_precise(video_with_subs, audio_path, final_segment)
        final_duration = safe_get_media_duration(final_segment)
        final_info = get_media_info(final_segment)
        debug_info['stages']['07_final_segment'] = {
            'path': final_segment,
            'duration': final_duration,
            'audio_duration': audio_duration,
            'sync_error': abs(final_duration - audio_duration),
            'info': final_info
        }

        # 7.5) 给单段加淡入淡出效果
        fade_segment = os.path.join(tmp, f"seg_{idx:02d}_fade_{unique_id}.mp4")
        add_fade_in_out_to_segment(final_segment, fade_segment, final_duration, fade=TRANSITION_DURATION)

        # 8) 创建调试信息文件
        create_debug_info_file(tmp, idx, unique_id, debug_info)

        # 9) 验证同步
        sync_error = abs(final_duration - audio_duration)
        if sync_error > 0.05:
            logging.warning(f"[Seg {idx}] ⚠️  Sync error: {sync_error:.3f}s (final={final_duration:.3f}s, audio={audio_duration:.3f}s)")
        else:
            logging.info(f"[Seg {idx}] ✅ Perfect sync: error={sync_error:.3f}s")

        logging.info(f"[Seg {idx}] ✅ Complete: {final_duration:.3f}s")
        return idx, [(fade_segment, final_duration)]

    except Exception as e:
        logging.error(f"[Seg {idx}] ❌ Failed: {e}")
        import traceback
        logging.error(f"[Seg {idx}] Traceback: {traceback.format_exc()}")
        debug_info['error'] = str(e)
        debug_info['traceback'] = traceback.format_exc()
        create_debug_info_file(tmp, idx, unique_id, debug_info)
        return idx, []

def concat_videos_with_simple_transitions(videos: list[str],
                                          durations: list[float],
                                          out: str,
                                          tdur: float = TRANSITION_DURATION):
    """
    简单拼接所有视频片段，无转场，无音频重叠，单段自带淡入淡出。
    """
    n = len(videos)
    if n == 0:
        raise RuntimeError("No clips to concat")
    if n == 1:
        shutil.copy(videos[0], out)
        logging.info(f"Single clip copied → {out}")
        return

    # 验证所有文件
    for video in videos:
        if not os.path.exists(video):
            raise FileNotFoundError(f"Video file not found: {video}")

    # 使用concat demuxer直接拼接所有片段
    concat_list = []
    for video in videos:
        concat_list.append(f"file '{os.path.abspath(video)}'")

    concat_file = os.path.join(os.path.dirname(out), "concat_list.txt")
    with open(concat_file, "w", encoding="utf-8") as f:
        f.write("\n".join(concat_list))

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        out
    ]
    logging.info(f"Direct concatenation of {n} clips → {out}")
    run_cmd(cmd)

    if os.path.exists(concat_file):
        os.remove(concat_file)

def add_gentle_intro_outro(video_path: str, output_path: str, total_duration: float):
    fade_duration = min(1.0, total_duration / 20)
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", 
        f"fade=t=in:st=0:d={fade_duration:.3f},"
        f"fade=t=out:st={total_duration-fade_duration:.3f}:d={fade_duration:.3f}",
        "-af",
        f"afade=t=in:st=0:d={fade_duration:.3f},"
        f"afade=t=out:st={total_duration-fade_duration:.3f}:d={fade_duration:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        output_path
    ]
    logging.info(f"Adding gentle intro/outro (fade: {fade_duration:.2f}s) → {output_path}")
    run_cmd(cmd)

def generate_full_news_parallel(text: str, output_path: str = None) -> str:
    segs = smart_chunk_text(text)
    logging.info(f"Text split into {len(segs)} segments")
    for i, s in enumerate(segs, 1):
        logging.info(f" [{i}] {s[:50]}{'...' if len(s)>50 else ''}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_session = generate_unique_id()
    tmp = f"{TMP_DIR_ROOT}_{ts}_{unique_session}"
    os.makedirs(tmp, exist_ok=True)
    logging.info(f"📁 Working directory: {tmp}")

    tasks = [(i+1, segs[i], ts, tmp) for i in range(len(segs))]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(generate_single_segment, task): task[0] for task in tasks}
        for future in concurrent.futures.as_completed(futures):
            try:
                idx, parts = future.result()
                if parts:
                    results.append((idx, parts))
                    logging.info(f"✅ Segment {idx} completed")
                else:
                    logging.warning(f"❌ Segment {idx} failed")
            except Exception as e:
                logging.error(f"❌ Segment error: {e}")

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
    success_count = len(results)
    total_count = len(segs)

    logging.info(f"✅ Generated {success_count}/{total_count} segments")
    logging.info(f"📹 Total: {len(all_videos)} clips, {total_duration:.2f}s")

    os.makedirs("output", exist_ok=True)

    # 拼接
    intermediate_output = f"output/news_with_transitions_{ts}_{unique_session}.mp4"
    concat_videos_with_simple_transitions(all_videos, all_durations, intermediate_output)

    # 总体intro/outro
    if output_path is None:
        final_output = f"output/full_news_{ts}_{unique_session}.mp4"
    else:
        final_output = output_path
        # 确保输出目录存在
        output_dir = os.path.dirname(final_output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
    add_gentle_intro_outro(intermediate_output, final_output, total_duration)

    # 清理中间文件
    if os.path.exists(intermediate_output):
        os.remove(intermediate_output)

    logging.info(f"🎉 Final video with gentle transitions → {final_output}")
    logging.info(f"🔍 Debug files in: {tmp}")

    return final_output

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        txt = open(sys.argv[1], encoding="utf-8").read()
    else:
        txt = """
# 【AI日报】2025年05月29日

## 1. DeepSeek即将发布1.2万亿参数R2大模型
DeepSeek即将发布的R2大模型参数规模达到1.2万亿，相比前代R1的6710亿参数几乎翻倍。这一参数规模已接近国际顶尖模型如GPT-4的水平，标志着中国在大模型研发领域取得重要突破。该模型预计将在推理能力和多任务处理方面有显著提升。

## 2. 多模态模型物理推理能力评估：GPT-4o表现最佳
最新研究对多模态大语言模型的物理推理能力进行了系统评估。结果显示，GPT-4o、Claude3.7和DeepSeek等最新模型在数学奥赛类题目上表现优异，但在涉及真实物理场景的推理任务中仍有提升空间。研究提出了新的评估基准，为多模态模型发展提供了重要参考。

## 3. 华为盘古Pro MoE模型首次打榜即登顶
华为盘古Pro MoE模型在最新一期SuperCLUE大模型榜单中表现优异，实现了综合能力领先。该模型采用混合专家架构，在参数规模小于部分竞品的情况下，通过架构创新实现了性能突破，展示了中国企业在AI基础模型研发上的实力。

## 4. 开源AI助手解决方案集成多平台大模型
GeekAI发布了一套基于大语言模型的开源AI助手解决方案，集成了OpenAI、Claude、通义千问、Kimi和DeepSeek等多个平台的大模型。该方案自带运营管理后台，支持开箱即用，为开发者提供了便捷的多模型集成和部署方案。

## 5. AI一体机热潮引发产业方向讨论
近期科技公司和创业企业纷纷推出"模型+硬件+私有化部署"的AI一体机解决方案，主打安全可控和本地化部署优势。文章探讨了这一趋势是否偏离了大模型技术发展的核心方向，以及商业化路径的合理性问题。

## 6. 大模型智友库提升开发效率
大模型智友库是为提升大模型开发效率而设计的专用库，其API和文档专门针对大模型使用场景进行了优化。该工具可帮助开发者更高效地构建和调试基于大语言模型的应用，支持多种主流模型框架。

## 7. 金融机构加速AI人才招聘
上海农商银行正在招聘熟悉Llama、Qwen、ChatGLM等大模型技术的AI工程师，要求具备大模型应用开发和部署经验。这反映了金融机构加速AI技术落地的趋势，特别是在零售业务智能化转型方面的人才需求。
"""
    generate_full_news_parallel(txt)