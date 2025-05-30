from news_processor import LongNewsProcessor
from video_concatenator import VideoConcatenator
import concurrent.futures

def process_and_concatenate_news(news_text, project_name=None, auto_concatenate=True, max_workers=4):
    """
    Process a news text to generate video segments and then concatenate them
    
    Args:
        news_text: The long news text to process
        project_name: Optional custom name for the project
        auto_concatenate: Whether to automatically concatenate videos after generation
        max_workers: Maximum number of worker threads for parallel processing
        
    Returns:
        dict: A dictionary containing results of both processes
    """
    # Step 1: Process the news text and generate video segments
    processor = LongNewsProcessor(
        max_chars_per_segment=25,  # Characters per segment
        max_audio_duration=4.8     # Maximum audio duration in seconds
    )
    
    # Process the news with parallel segment processing
    result = processor.process_long_news(
        news_text,
        project_name=project_name,
        calibrate=True,             # Whether to calibrate speech rate
        add_subtitles=True,         # Add subtitles to videos
        subtitle_format="srt",      # Subtitle format (srt, ass, vtt)
        parallel_processing=True,   # Enable parallel segment processing
        max_workers=max_workers     # Number of worker threads
    )
    
    # Get output information
    segments_dir = result['output_directory']
    segments_count = result['successful_segments']
    
    print(f"\n=== Video segments generation complete ===")
    print(f"Successfully generated {segments_count} video segments")
    print(f"Videos directory: {segments_dir}")
    
    # Step 2: Concatenate the generated videos (sequential, since it's fast)
    if auto_concatenate and segments_count > 0:
        print(f"\n=== Starting video concatenation ===")
        concatenator = VideoConcatenator(output_dir="output/concatenated")
        
        # Automatically concatenate the videos
        concatenated_video = concatenator.auto_concatenate(
            search_dir=segments_dir,         # The directory with video segments
            output_filename=f"{project_name}_complete.mp4" if project_name else None,
            pattern="*_final.mp4",           # Pattern to match final videos
            force_reencode=False             # Auto-determine if re-encoding is needed
        )
        
        # Add concatenation result to the overall result
        result['concatenation'] = {
            'status': 'success' if concatenated_video else 'failed',
            'output_path': concatenated_video,
            'segment_count': segments_count
        }
    else:
        result['concatenation'] = {
            'status': 'skipped',
            'reason': 'auto_concatenate=False or no segments generated'
        }
    
    return result

# Example usage
if __name__ == "__main__":
    import multiprocessing
    
    long_news = """
【AI日报】2025年05月30日
1. 企业级AI战略加速落地！传微软与巴克莱银行签订10万份Copilot许可证
微软在全员大会上展示企业级AI业务进展，其中与巴克莱银行达成的10万份Copilot许可证交易成为焦点。这一合作标志着企业级AI应用的快速落地，预计将推动更多金融机构采用AI技术，对行业具有变革性影响。
2. 不只是"小升级"！DeepSeek-R1新版获海外盛赞
DeepSeek最新发布的R1模型升级版在全球AI领域掀起热议，多位国际科技大佬及行业高管盛赞其技术突破。实测显示该模型在多项基准测试中表现优异，标志着中国AI公司在技术上的重大进步。
3. 云从科技多模态大模型「CongRong-v2.0」登顶全球榜单
云从科技自主研发的「从容大模型」在国际评测平台OpenCompass最新全球多模态榜单中，以80.7分的综合成绩登顶榜首。这一成绩标志着中国在多模态AI领域的技术实力获得国际认可。
4. 微软开源Aurora AI气象模型
微软开源Aurora AI气象模型，该模型结合深度学习技术，能够实现精准气象预报，目前已在MSN天气应用中投入使用。同时腾讯也开源了混元语音数字人模型，显示AI开源生态持续发展。
5. 字节跳动内部禁用Cursor等AI编程工具，用旗下Trae作为替代
字节跳动宣布内部将禁用Cursor等第三方AI编程工具，转而使用自研的Trae工具。Trae搭载基座大模型doubao-1.5-pro，支持切换DeepSeek R1&V3，是国内首个AI原生IDE工具。

    """
    
    # 获取CPU核心数，用于确定最佳线程数
    cpu_count = multiprocessing.cpu_count()
    optimal_workers = max(1, min(cpu_count - 1, 8))  # 使用CPU核心数-1，但最多8个线程
    
    print(f"使用 {optimal_workers} 个线程进行并行处理...")
    
    # Process and concatenate with optimized parallel processing for segment generation
    result = process_and_concatenate_news(
        news_text=long_news,
        project_name="ai_news_demo",
        auto_concatenate=True,
        max_workers=optimal_workers  # 动态设置最佳线程数
    )
    
    # Print results
    if result['concatenation']['status'] == 'success':
        print(f"\n✅ Complete process successful!")
        print(f"Final video: {result['concatenation']['output_path']}")
    else:
        print(f"\n⚠️ Video segments generated but concatenation {result['concatenation']['status']}")
        if result['concatenation']['status'] == 'failed':
            print("Check logs for error details")