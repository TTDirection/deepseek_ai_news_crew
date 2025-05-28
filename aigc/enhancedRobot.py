#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import subprocess
import concurrent.futures
from datetime import datetime
from airobot import MultimodalNewsBot

MAX_CHARS_PER_SEGMENT = 52  # 每段最大字符数
MAX_WORKERS = 20  # 并行工作线程数
TMP_DIR_ROOT = "output/segments"

# —— 优化的文本切分  —— 
def smart_chunk_text(text: str, max_chars: int = MAX_CHARS_PER_SEGMENT) -> list[str]:
    """
    按最大52字左右切分，优先在标点处断开
    """
    # 先按段落分割
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    chunks = []
    
    for para in paragraphs:
        # 跳过标题行（以#开头）
        if para.startswith('#'):
            continue
            
        # 按句子切分
        sentences = re.split(r'(?<=[。！？；])', para)
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # 如果当前句子本身就超过限制，需要强制切分
            if len(sentence) > max_chars:
                # 先保存当前累积的内容
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # 对长句子进行切分
                while len(sentence) > max_chars:
                    # 寻找合适的切分点（逗号、顿号等）
                    cut_pos = max_chars
                    for i in range(max_chars-1, max_chars//2, -1):
                        if sentence[i] in '，、：；':
                            cut_pos = i + 1
                            break
                    
                    chunks.append(sentence[:cut_pos].strip())
                    sentence = sentence[cut_pos:].strip()
                
                # 剩余部分
                if sentence:
                    current_chunk = sentence
            else:
                # 检查加入当前句子是否会超限
                if len(current_chunk) + len(sentence) <= max_chars:
                    current_chunk += sentence
                else:
                    # 保存当前chunk，开始新的
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence
        
        # 保存最后的chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
    
    # 过滤掉过短的片段
    chunks = [chunk for chunk in chunks if len(chunk.strip()) >= 5]
    return chunks

# —— 单个片段生成函数 —— 
def generate_single_segment(args):
    """
    生成单个片段的视频，用于并行处理
    """
    idx, seg_text, timestamp, tmp_dir = args
    bot = MultimodalNewsBot()
    
    print(f"[线程] 开始生成第 {idx} 段: {seg_text[:20]}...")
    
    try:
        # 生成语音
        voice_path = bot.generate_voice(seg_text, f"{timestamp}_{idx:02d}")
        
        # 生成视频
        res = bot.generate_news_report(seg_text)
        if res.get("status") != "success":
            raise RuntimeError(f"第{idx}段视频生成失败：{res.get('error')}")
        
        video_silent = res["video_path"]
        
        # 合并音视频
        final_path = os.path.join(tmp_dir, f"seg_{idx:02d}_final.mp4")
        merge_audio_video(voice_path, video_silent, final_path)
        
        # 获取时长用于验证
        duration = bot.get_audio_duration(voice_path)
        
        print(f"[线程] 完成第 {idx} 段，时长: {duration:.2f}s")
        return idx, final_path, duration
        
    except Exception as e:
        print(f"[错误] 第 {idx} 段生成失败: {str(e)}")
        return idx, None, 0

# —— ffmpeg 工具函数保持不变 —— 
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

# —— 主生成流程（并行版本）—— 
def generate_full_news_parallel(text: str) -> str:
    # 智能切分文本
    segments = smart_chunk_text(text)
    print(f"文本切分为 {len(segments)} 段，每段约 {MAX_CHARS_PER_SEGMENT} 字以内")
    
    # 打印切分结果预览
    for i, seg in enumerate(segments, 1):
        print(f"  段{i} ({len(seg)}字): {seg[:30]}{'...' if len(seg) > 30 else ''}")
    
    # 创建临时目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_dir = os.path.join(TMP_DIR_ROOT + "_" + timestamp)
    os.makedirs(tmp_dir, exist_ok=True)
    
    # 准备并行任务参数
    tasks = [(i+1, seg, timestamp, tmp_dir) for i, seg in enumerate(segments)]
    
    # 并行生成所有片段
    print(f"\n开始并行生成 {len(segments)} 段视频（最大 {MAX_WORKERS} 线程）...")
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_idx = {executor.submit(generate_single_segment, task): task[0] 
                        for task in tasks}
        
        for future in concurrent.futures.as_completed(future_to_idx):
            result = future.result()
            if result[1] is not None:  # 成功生成
                results.append(result)
    
    # 按索引排序结果
    results.sort(key=lambda x: x[0])
    successful_videos = [r[1] for r in results]
    
    if not successful_videos:
        raise RuntimeError("所有片段生成都失败了")
    
    print(f"\n成功生成 {len(successful_videos)}/{len(segments)} 段")
    
    # 验证时长
    total_duration = sum(r[2] for r in results)
    print(f"总时长: {total_duration:.2f}s")
    
    # 最终拼接
    final_out = os.path.join("output", f"full_news_{timestamp}.mp4")
    print(f"\n正在拼接视频 → {final_out}")
    concat_videos(successful_videos, final_out)
    
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
Google宣布对其AI Studio平台进行重大升级，引入Gemini 2.5 Pro模型和代理工具，增强了多模态能力。新版本提供更直观的界面和更强大的调试工具。

## 2. Google推出AI Mode搜索功能
Google正式推出AI Mode搜索功能，该功能能够为用户提供更详细和个性化的搜索结果。这标志着搜索体验的重大升级。

## 3. Volvo将率先在汽车中安装Google Gemini
Volvo宣布将成为首家在车辆中集成Google Gemini AI系统的汽车制造商，为驾驶员提供智能语音助手服务。
"""
    
    generate_full_news_parallel(txt)