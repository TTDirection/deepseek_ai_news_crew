import os
import re
import random
import subprocess
from datetime import datetime
from typing import List, Tuple
import json
from MultimodalRobot import MultimodalNewsBot, TTSModule

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Tuple

# 导入重构后的模块
from text_segmenter import TextSegmenter
from subtitle_generator import SubtitleGenerator
from video_processor import VideoProcessor

class LongNewsProcessor:
    """长新闻处理器，整合文本分割、字幕生成和视频处理功能"""
    
    def __init__(self, max_chars_per_segment: int = 100, 
                 estimated_chars_per_second: float = 4.0,
                 max_audio_duration: float = 10.0,
                 output_dir: str = "./output",
                 llm_client = None,
                 tts_module = None,
                 news_bot = None):
        """初始化长新闻处理器
        
        Args:
            max_chars_per_segment: 每个片段的最大字符数
            estimated_chars_per_second: 估计的每秒朗读字符数
            max_audio_duration: 最大音频时长（秒）
            output_dir: 输出目录
            llm_client: LLM客户端，用于智能分割
            tts_module: TTS模块，用于语音合成
            news_bot: 新闻机器人，用于图像和视频生成
        """
        self.max_chars_per_segment = max_chars_per_segment
        self.estimated_chars_per_second = estimated_chars_per_second
        self.max_audio_duration = max_audio_duration
        self.output_dir = output_dir
        self.llm_client = llm_client
        self.tts_module = tts_module
        self.news_bot = news_bot
        
        # 创建输出目录
        self.voices_dir = os.path.join(output_dir, "voices")
        self.images_dir = os.path.join(output_dir, "images")
        self.videos_dir = os.path.join(output_dir, "videos")
        self.subtitles_dir = os.path.join(output_dir, "subtitles")
        self.final_videos_dir = os.path.join(output_dir, "final_videos")
        
        os.makedirs(self.voices_dir, exist_ok=True)
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.videos_dir, exist_ok=True)
        os.makedirs(self.subtitles_dir, exist_ok=True)
        os.makedirs(self.final_videos_dir, exist_ok=True)
        
        # 初始化子模块
        self.text_segmenter = TextSegmenter(
            max_chars_per_segment=max_chars_per_segment,
            estimated_chars_per_second=estimated_chars_per_second,
            max_audio_duration=max_audio_duration,
            llm_client=llm_client
        )
        
        self.subtitle_generator = SubtitleGenerator(
            output_dir=self.subtitles_dir
        )
        
        self.video_processor = VideoProcessor(
            output_dir=self.final_videos_dir
        )
    
    def estimate_audio_duration(self, text: str) -> float:
        """估计文本的音频时长
        
        Args:
            text: 输入文本
            
        Returns:
            float: 估计的音频时长（秒）
        """
        return self.text_segmenter.estimate_audio_duration(text)
    
    def calibrate_speech_rate(self, sample_text: str = None) -> float:
        """校准语速
        
        Args:
            sample_text: 样本文本，如果为None则使用默认样本
            
        Returns:
            float: 校准后的每秒字符数
        """
        if sample_text is None:
            sample_text = "这是一段用于校准语速的测试文本，包含标点符号和常见汉字。"
        
        print(f"使用样本文本进行语速校准: {sample_text}")
        
        try:
            # 生成样本语音
            voice_path, actual_duration = self.tts_module.generate_voice(
                sample_text, "speech_rate_calibration"
            )
            
            # 计算实际语速
            clean_text_length = len(sample_text.replace(" ", "").replace("\n", ""))
            actual_chars_per_second = clean_text_length / actual_duration
            
            # 更新估计语速
            self.estimated_chars_per_second = actual_chars_per_second
            self.text_segmenter.estimated_chars_per_second = actual_chars_per_second
            
            print(f"语速校准完成: {actual_chars_per_second:.2f} 字符/秒")
            return actual_chars_per_second
            
        except Exception as e:
            print(f"语速校准失败: {e}，使用默认值 {self.estimated_chars_per_second} 字符/秒")
            return self.estimated_chars_per_second
    
    def smart_split_text(self, text: str) -> List[str]:
        """智能分割文本
        
        Args:
            text: 输入的长文本
            
        Returns:
            List[str]: 分割后的文本片段列表
        """
        return self.text_segmenter.smart_split_text(text)
    
    def create_subtitle_file(self, text: str, duration: float, output_base_path: str, 
                            format: str = "srt") -> str:
        """创建字幕文件
        
        Args:
            text: 字幕文本
            duration: 音频时长（秒）
            output_base_path: 输出文件基础路径（不含扩展名）
            format: 字幕格式 ("srt", "ass", "vtt")
            
        Returns:
            str: 字幕文件路径
        """
        return self.subtitle_generator.create_subtitle_file(
            text, duration, output_base_path, format
        )
    
    def add_subtitles_to_video(self, video_path: str, subtitle_path: str, 
                              output_path: str, style: Dict[str, Any] = None) -> Optional[str]:
        """将字幕添加到视频
        
        Args:
            video_path: 视频文件路径
            subtitle_path: 字幕文件路径
            output_path: 输出文件路径
            style: 字幕样式设置
            
        Returns:
            Optional[str]: 成功时返回输出文件路径，失败时返回None
        """
        return self.video_processor.add_subtitles_to_video(
            video_path, subtitle_path, output_path, style
        )
    
    def merge_audio_video(self, audio_path: str, video_path: str, output_path: str) -> Optional[str]:
        """合并音频和视频
        
        Args:
            audio_path: 音频文件路径
            video_path: 视频文件路径
            output_path: 输出文件路径
            
        Returns:
            Optional[str]: 成功时返回输出文件路径，失败时返回None
        """
        return self.video_processor.merge_audio_video(
            audio_path, video_path, output_path
        )
    
    def generate_random_seed(self) -> int:
        """生成随机种子
        
        Returns:
            int: 随机种子
        """
        return self.video_processor.generate_random_seed()
    
    def process_long_news(self, news_text: str, project_name: str = None, calibrate: bool = True,
                         add_subtitles: bool = True, subtitle_format: str = "srt",
                         subtitle_style: dict = None) -> dict:
        """处理长新闻，生成分段播报
        
        Args:
            news_text: 长新闻文本
            project_name: 项目名称（可选）
            calibrate: 是否进行语速校准
            add_subtitles: 是否添加字幕
            subtitle_format: 字幕格式 ("srt", "ass", "vtt")
            subtitle_style: 字幕样式设置
            
        Returns:
            dict: 处理结果
        """
        if project_name is None:
            project_name = f"long_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        print(f"开始处理长新闻项目: {project_name}")
        print(f"原始新闻长度: {len(news_text)} 字符")
        print(f"字幕设置: {'启用' if add_subtitles else '禁用'} ({subtitle_format})")
        
        # 步骤0: 语速校准（可选）
        if calibrate:
            print("\n=== 步骤0: 语速校准 ===")
            self.calibrate_speech_rate()
        
        # 步骤1: 智能分割文本
        print("\n=== 步骤1: 智能分割文本 ===")
        segments = self.smart_split_text(news_text)
        print(f"分割得到 {len(segments)} 个片段")
        
        # 打印分割结果预览
        for i, segment in enumerate(segments):
            estimated_duration = self.estimate_audio_duration(segment)
            print(f"片段 {i+1}: {len(segment)} 字符, 估算 {estimated_duration:.2f}秒")
            print(f"  内容: {segment}")
        
        # 步骤2: 为每个片段生成多模态内容
        print(f"\n=== 步骤2: 生成多模态内容{'（含字幕）' if add_subtitles else ''} ===")
        results = []
        
        for i, segment in enumerate(segments):
            segment_id = f"{project_name}_segment_{i+1:03d}"
            print(f"\n处理片段 {i+1}/{len(segments)}: {segment_id}")
            print(f"片段内容: {segment}")
            
            try:
                # 生成随机种子
                seed = self.generate_random_seed()
                print(f"使用随机种子: {seed}")
                
                # 生成语音
                print("生成语音...")
                voice_path, audio_duration = self.tts_module.generate_voice(
                    segment, f"{segment_id}_voice"
                )
                
                # 检查实际时长是否超限
                if audio_duration > self.max_audio_duration:
                    print(f"警告: 实际音频时长 {audio_duration:.2f}秒 超过限制 {self.max_audio_duration}秒")
                
                # 生成图片
                print("生成图片...")
                image_paths = self.news_bot.image_module.generate_image(
                    segment, f"{segment_id}_image",
                    ratio="16:9", seed=seed
                )
                
                # 生成视频（固定5秒）
                print("生成视频...")
                video_path = self.news_bot.video_module.generate_video(
                    segment, 5.0, image_paths, f"{segment_id}_video",
                    resolution="720p", ratio="16:9"
                )
                
                # 合并音频和视频
                print("合并音视频...")
                temp_video_path = os.path.join(
                    self.final_videos_dir, f"{segment_id}_temp.mp4"
                )
                
                merged_video = self.merge_audio_video(
                    voice_path, video_path, temp_video_path
                )
                
                final_video_path = None
                subtitle_path = None
                
                if merged_video and add_subtitles:
                    # 创建字幕文件
                    print("创建字幕...")
                    subtitle_base_path = os.path.join(self.subtitles_dir, f"{segment_id}_subtitle")
                    subtitle_path = self.create_subtitle_file(
                        segment, audio_duration, subtitle_base_path, subtitle_format
                    )
                    
                    # 将字幕添加到视频
                    print("添加字幕到视频...")
                    final_video_path = os.path.join(
                        self.final_videos_dir, f"{segment_id}_final.mp4"
                    )
                    
                    final_video_with_subtitles = self.add_subtitles_to_video(
                        merged_video, subtitle_path, final_video_path, subtitle_style
                    )
                    
                    if final_video_with_subtitles:
                        # 删除临时视频文件
                        if os.path.exists(temp_video_path):
                            os.remove(temp_video_path)
                        final_video_path = final_video_with_subtitles
                    else:
                        # 如果添加字幕失败，使用无字幕版本
                        print("字幕添加失败，使用无字幕版本")
                        final_video_path = temp_video_path
                
                elif merged_video:
                    # 不添加字幕，直接使用合并后的视频
                    final_video_path = os.path.join(
                        self.final_videos_dir, f"{segment_id}_final.mp4"
                    )
                    
                    # 重命名临时文件
                    if os.path.exists(temp_video_path):
                        os.rename(temp_video_path, final_video_path)
                
                segment_result = {
                    "segment_id": segment_id,
                    "segment_index": i + 1,
                    "text": segment,
                    "voice_path": voice_path,
                    "image_paths": image_paths,
                    "video_path": video_path,
                    "final_video_path": final_video_path,
                    "subtitle_path": subtitle_path,
                    "audio_duration": audio_duration,
                    "estimated_duration": self.estimate_audio_duration(segment),
                    "seed": seed,
                    "has_subtitles": add_subtitles and subtitle_path is not None,
                    "subtitle_format": subtitle_format if add_subtitles else None,
                    "status": "success" if final_video_path else "failed"
                }
                
                results.append(segment_result)
                print(f"片段 {segment_id} 处理完成")
                
            except Exception as e:
                print(f"处理片段 {segment_id} 时出错: {e}")
                segment_result = {
                    "segment_id": segment_id,
                    "segment_index": i + 1,
                    "text": segment,
                    "status": "failed",
                    "error": str(e)
                }
                results.append(segment_result)
        
        # 汇总结果
        total_segments = len(segments)
        successful_segments = len([r for r in results if r["status"] == "success"])
        
        final_result = {
            "project_name": project_name,
            "original_text": news_text,
            "original_length": len(news_text),
            "total_segments": total_segments,
            "successful_segments": successful_segments,
            "estimated_chars_per_second": self.estimated_chars_per_second,
            "max_audio_duration": self.max_audio_duration,
            "subtitles_enabled": add_subtitles,
            "subtitle_format": subtitle_format,
            "segments": results,
            "output_directory": self.final_videos_dir,
            "subtitles_directory": self.subtitles_dir,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 保存结果到JSON文件
        result_file = os.path.join(self.output_dir, f"{project_name}_result.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, ensure_ascii=False, indent=2)
        
        print(f"\n=== 处理完成 ===")
        print(f"项目名称: {project_name}")
        print(f"总片段数: {total_segments}")
        print(f"成功片段数: {successful_segments}")
        print(f"字幕状态: {'已添加' if add_subtitles else '未添加'}")
        print(f"输出目录: {self.final_videos_dir}")
        print(f"字幕目录: {self.subtitles_dir}")
        print(f"结果文件: {result_file}")
        
        return final_result

def main():
    """主函数"""
    # 长AI新闻示例
    long_ai_news = """
    OpenAI最新发布的GPT-4 Turbo模型在多个维度实现了重大突破，不仅在语言理解和生成能力上有显著提升，还在代码编写、数学推理和创意写作等专业领域展现出前所未有的性能。该模型支持128K上下文长度，能够处理相当于300页文本的信息量，为复杂的文档分析和长篇内容创作提供了强大支持。
    """
    
    # 创建处理器
    processor = LongNewsProcessor(
        max_chars_per_segment=25,  # 每段最多25字符
        max_audio_duration=4.8    # 音频最长4.8秒，确保视频为5秒
    )
    
    # 自定义字幕样式
    custom_subtitle_style = {
        'fontsize': 24,
        'fontcolor': 'yellow',
        'box': 1,
        'boxcolor': 'black@0.7',
        'boxborderw': 3
    }
    
    # 处理长新闻（启用字幕）
    result = processor.process_long_news(
        long_ai_news, 
        "ai_report_",
        calibrate=True,
        add_subtitles=True,          # 启用字幕
        subtitle_format="srt",       # 使用SRT格式
        subtitle_style=custom_subtitle_style  # 自定义样式
    )
    
    # 打印结果摘要
    print("\n" + "="*60)
    print("处理结果摘要:")
    print(f"项目名称: {result['project_name']}")
    print(f"原始文本长度: {result['original_length']} 字符")
    print(f"分割片段数: {result['total_segments']}")
    print(f"成功处理: {result['successful_segments']}")
    print(f"字幕状态: {'已启用' if result['subtitles_enabled'] else '未启用'}")
    print(f"字幕格式: {result.get('subtitle_format', '无')}")
    print(f"语速参数: {result['estimated_chars_per_second']:.2f} 字符/秒")
    print(f"输出目录: {result['output_directory']}")
    print(f"字幕目录: {result['subtitles_directory']}")
    
    # 列出生成的视频文件
    print("\n生成的视频文件:")
    for i, segment in enumerate(result['segments']):
        if segment['status'] == 'success':
            subtitle_status = "有字幕" if segment.get('has_subtitles') else "无字幕"
            print(f"{i+1:2d}. {segment['segment_id']}: {segment['final_video_path']} ({subtitle_status})")
            print(f"    内容: {segment['text']}")
            print(f"    估算时长: {segment['estimated_duration']:.2f}秒, 实际时长: {segment['audio_duration']:.2f}秒")
            if segment.get('subtitle_path'):
                print(f"    字幕文件: {segment['subtitle_path']}")
        else:
            print(f"{i+1:2d}. {segment['segment_id']}: 处理失败")
    return result

if __name__ == "__main__":
    main()