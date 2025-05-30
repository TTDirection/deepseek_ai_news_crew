import os
import json
import time
from typing import Dict, Any, List, Optional

from text_segmentation import TextSegmenter
from audio_processor import AudioProcessor
from video_generation import VideoGenerator
from subtitle_processor import SubtitleProcessor
from video_concatenator import VideoConcatenator

class NewsProcessor:
    """新闻处理器，整合所有模块处理长文本新闻"""
    
    def __init__(self, 
                 max_chars_per_segment: int = 100,
                 max_audio_duration: float = 10.0,
                 output_dir: str = "output/news",
                 api_config: Dict[str, Any] = None):
        """初始化新闻处理器
        
        Args:
            max_chars_per_segment: 每段最大字符数
            max_audio_duration: 每段最大音频时长（秒）
            output_dir: 输出目录
            api_config: API配置
        """
        self.max_chars_per_segment = max_chars_per_segment
        self.max_audio_duration = max_audio_duration
        self.output_dir = output_dir
        self.api_config = api_config or {}
        
        # 创建输出目录
        self.segments_dir = os.path.join(output_dir, "segments")
        self.final_dir = os.path.join(output_dir, "final_videos")
        os.makedirs(self.segments_dir, exist_ok=True)
        os.makedirs(self.final_dir, exist_ok=True)
        
        # 初始化各模块
        self.text_segmenter = TextSegmenter(
            max_chars_per_segment=max_chars_per_segment,
            max_audio_duration=max_audio_duration,
            llm_config=api_config
        )
        
        self.audio_processor = AudioProcessor(
            output_dir=os.path.join(output_dir, "audio"),
            api_config=api_config
        )
        
        self.video_generator = VideoGenerator(
            output_dir=os.path.join(output_dir, "video"),
            api_config=api_config
        )
        
        self.subtitle_processor = SubtitleProcessor(
            output_dir=os.path.join(output_dir, "subtitles")
        )
        
        self.video_concatenator = VideoConcatenator(
            output_dir=self.final_dir
        )
    
    def process_news(self, news_text: str, title: str = None, subtitle_format: str = "srt") -> Dict[str, Any]:
        """处理新闻文本，生成视频报道
        
        Args:
            news_text: 新闻文本
            title: 新闻标题
            subtitle_format: 字幕格式
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        print(f"\n{'='*50}")
        print(f"开始处理新闻: {title or '未命名新闻'}")
        print(f"{'='*50}\n")
        
        start_time = time.time()
        
        # 1. 校准语速参数
        chars_per_second = self.audio_processor.calibrate_speech_rate()
        self.text_segmenter.estimated_chars_per_second = chars_per_second
        
        # 2. 分段处理文本
        print(f"\n正在分段处理文本...")
        segments = self.text_segmenter.segment_chinese_text_with_llm(news_text)
        print(f"文本已分为 {len(segments)} 个片段")
        
        # 3. 处理每个片段
        segment_results = []
        for i, segment_text in enumerate(segments):
            print(f"\n{'*'*50}")
            print(f"处理片段 {i+1}/{len(segments)}")
            print(f"{'*'*50}")
            print(f"文本: {segment_text[:50]}...")
            
            segment_dir = os.path.join(self.segments_dir, f"segment_{i+1:03d}")
            os.makedirs(segment_dir, exist_ok=True)
            
            # 3.1 生成语音
            voice_path, audio_duration = self.audio_processor.generate_voice(
                segment_text, 
                f"segment_{i+1:03d}"
            )
            
            # 3.2 生成视频
            video_path = self.video_generator.generate_video(
                segment_text,
                audio_duration,
                filename=f"segment_{i+1:03d}"
            )
            
            # 3.3 创建字幕
            subtitle_path = self.subtitle_processor.create_subtitle_file(
                segment_text,
                audio_duration,
                os.path.join(segment_dir, f"segment_{i+1:03d}"),
                subtitle_format
            )
            
            # 3.4 合并音频和视频
            merged_path = os.path.join(segment_dir, f"segment_{i+1:03d}_merged.mp4")
            merged_video = self.merge_audio_video(voice_path, video_path, merged_path)
            
            # 3.5 添加字幕
            final_path = os.path.join(segment_dir, f"segment_{i+1:03d}_final.mp4")
            final_video = self.subtitle_processor.add_subtitles_to_video(
                merged_video,
                subtitle_path,
                final_path
            )
            
            # 保存结果
            segment_result = {
                "segment_id": i+1,
                "text": segment_text,
                "audio_path": voice_path,
                "audio_duration": audio_duration,
                "video_path": video_path,
                "subtitle_path": subtitle_path,
                "merged_path": merged_video,
                "final_path": final_video
            }
            segment_results.append(segment_result)
            
            print(f"片段 {i+1} 处理完成: {final_video}")
        
        # 4. 拼接所有视频
        print(f"\n{'='*50}")
        print(f"开始拼接所有视频片段...")
        print(f"{'='*50}\n")
        
        concatenated_video = self.video_concatenator.auto_concatenate(
            search_dir=self.segments_dir,
            pattern="*_final.mp4"
        )
        
        # 5. 生成结果报告
        end_time = time.time()
        processing_time = end_time - start_time
        
        result = {
            "title": title or "未命名新闻",
            "text_length": len(news_text),
            "segment_count": len(segments),
            "segments": segment_results,
            "concatenated_video": concatenated_video,
            "processing_time": processing_time
        }
        
        # 保存结果到JSON文件
        result_path = os.path.join(self.output_dir, "result.json")
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n{'='*50}")
        print(f"处理完成!")
        print(f"总处理时间: {processing_time:.2f}秒 ({processing_time/60:.2f}分钟)")
        print(f"最终视频: {concatenated_video}")
        print(f"结果报告: {result_path}")
        print(f"{'='*50}\n")
        
        return result
    
    def merge_audio_video(self, audio_path: str, video_path: str, output_path: str) -> str:
        """合并音频和视频
        
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
                print(f"合并成功: {output_path}")
                return output_path
            else:
                print(f"合并失败: {result.stderr}")
                return None
        except Exception as e:
            print(f"合并音频和视频时出错: {e}")
            return None

def main():
    # 配置参数
    api_config = {
        "api_key": "YOUR_API_KEY",  # 替换为你的API密钥
        "base_url": "https://api.deepseek.com/v1",
        "tts_model": "deepseek-tts",
        "voice_id": "zh-CN-YunxiNeural",  # 默认中文男声
        "rate": 1.0,  # 语速
        "pitch": 1.0  # 音调
    }
    
    # 示例新闻文本
    sample_news = """
【AI日报】2025年05月30日
1. 企业级AI战略加速落地！传微软与巴克莱银行签订10万份Copilot许可证
微软在全员大会上展示企业级AI业务进展，其中与巴克莱银行达成的10万份Copilot许可证交易成为焦点。
    """
    
    # 初始化处理器
    processor = NewsProcessor(
        max_chars_per_segment=100,
        max_audio_duration=10.0,
        output_dir="output/news",
        api_config=api_config
    )
    
    # 处理新闻
    result = processor.process_news(
        news_text=sample_news,
        title="AI算法突破提升推理效率",
        subtitle_format="srt"  # 可选: "srt", "ass", "vtt"
    )
    
    # 打印结果
    print(f"\n处理结果摘要:")
    print(f"标题: {result['title']}")
    print(f"文本长度: {result['text_length']} 字符")
    print(f"分段数: {result['segment_count']}")
    print(f"处理时间: {result['processing_time']:.2f} 秒")
    print(f"最终视频: {result['concatenated_video']}")

if __name__ == "__main__":
    main()