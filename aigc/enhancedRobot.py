#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import subprocess
from datetime import datetime
from airobot import MultimodalNewsBot

MAX_VIDEO_SEC = 10  # 视频接口支持的最长时长
DEFAULT_MAX_CHARS = 200  # 初步切分时的字符上限，可调整
TMP_DIR_ROOT = "output/segments"

# —— 文本初步切分  —— 
def chunk_text(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    """
    按句号/问号/感叹号切分，并累计句子直至达到 max_chars，再开启新片段。
    """
    sentences = re.split(r'(?<=[。！？])', text.strip())
    chunks, buf = [], ""
    for s in sentences:
        if not s.strip():
            continue
        if len(buf) + len(s) <= max_chars or not buf:
            buf += s
        else:
            chunks.append(buf.strip())
            buf = s
    if buf:
        chunks.append(buf.strip())
    return chunks

# —— 文本二分拆分 —— 
def bisect_chunk(text: str) -> tuple[str, str]:
    """
    在文本中点附近寻找最近标点处拆分。
    如果找不到标点，则按字符中点一分为二。
    """
    n = len(text)
    mid = n // 2

    # 左侧（0..mid）最近标点位置
    left_positions = [text.rfind(p, 0, mid) for p in ("。", "？", "！")]
    left = max(left_positions)  # 若都未找到则为 -1

    # 右侧（mid..end）最近标点位置
    right_positions = [idx for p in ("。", "？", "！") for idx in [text.find(p, mid)] if idx != -1]
    right = min(right_positions) if right_positions else -1

    # 选拆分点
    if left != -1:
        split_pos = left
    elif right != -1:
        split_pos = right
    else:
        split_pos = mid

    # 拆分两段
    t1 = text[: split_pos + 1].strip()
    t2 = text[split_pos + 1 :].strip()

    # 极端情况退化
    if not t1 or not t2:
        t1 = text[:mid].strip()
        t2 = text[mid:].strip()

    return t1, t2

# —— ffmpeg 工具 —— 
def merge_audio_video(audio_path: str, video_path: str, out_path: str):
    """
    用 ffmpeg 将静默视频和音频合成为带声视频
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-strict", "experimental",
        out_path
    ]
    subprocess.run(cmd, check=True)

def concat_videos(video_list: list[str], out_path: str):
    """
    用 ffmpeg concat 方式无缝拼接多段视频
    """
    list_file = "concat_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for vp in video_list:
            f.write(f"file '{os.path.abspath(vp)}'\n")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        out_path
    ]
    subprocess.run(cmd, check=True)
    os.remove(list_file)

# —— 主生成流程 —— 
def generate_full_news(text: str) -> str:
    bot = MultimodalNewsBot()

    # 初步切分
    queue = chunk_text(text)
    print(f"初步切分为 {len(queue)} 段。")

    # 创建临时目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_dir = os.path.join(TMP_DIR_ROOT + "_" + timestamp)
    os.makedirs(tmp_dir, exist_ok=True)

    finalized = []  # 存放 (seg_text, voice_path, duration)

    # —— 按时长拆分循环 —— 
    i = 0
    while i < len(queue):
        seg = queue[i]
        print(f"\n[拆分阶段] 处理段 {i+1}/{len(queue)}，长度 {len(seg)} 字")
        voice_path = bot.generate_voice(seg, timestamp + f"_{i}")
        duration = bot.get_audio_duration(voice_path)
        print(f"  → 语音时长 {duration:.2f}s")
        if duration > MAX_VIDEO_SEC:
            # 删除分段语音，二分文本，插回队列
            print("  → 时长超限，进行二分拆分")
            try:
                os.remove(voice_path)
            except:
                pass
            first, second = bisect_chunk(seg)
            queue[i:i+1] = [first, second]
            # 不移动 i，继续处理新分段
        else:
            finalized.append((seg, voice_path, duration))
            i += 1

    print(f"\n拆分完成，共 {len(finalized)} 段，均 ≤ {MAX_VIDEO_SEC}s")

    merged_segments = []

    # —— 正式生成：图像→视频→合并 —— 
    for idx, (seg, voice, dur) in enumerate(finalized, start=1):
        print(f"\n=== 生成第 {idx}/{len(finalized)} 段 ===")
        res = bot.generate_news_report(seg)
        if res.get("status") != "success":
            raise RuntimeError(f"第{idx}段生成失败：{res.get('error')}")
        video_silent = res["video_path"]

        out_seg = os.path.join(tmp_dir, f"seg_{idx:02d}_final.mp4")
        merge_audio_video(voice, video_silent, out_seg)
        print(f"  → 合并音视频：{out_seg}")
        merged_segments.append(out_seg)

    # —— 最终拼接 —— 
    final_out = os.path.join("output", f"full_news_{timestamp}.mp4")
    print(f"\n正在拼接 {len(merged_segments)} 段 → {final_out}")
    concat_videos(merged_segments, final_out)
    print(f"\n✔ 完成：{final_out}")
    return final_out

# —— 脚本入口 —— 
if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            txt = f.read()
    else:
        txt = """
# 【AI日报】2025年05月22日

## 1. Google AI Studio升级开发者体验
Google宣布对其AI Studio平台进行重大升级，引入Gemini 2.5 Pro模型和代理工具，增强了多模态能力。
## 2. Google推出AI Mode搜索功能
Google正式推出AI Mode搜索功能，该功能能够为用户提供更详细和个性化的搜索结果。
## 3. Volvo将率先在汽车中安装Google Gemini
Volvo宣布将成为首家在车辆中集成Google Gemini AI系统的汽车制造商。
"""
    generate_full_news(txt)