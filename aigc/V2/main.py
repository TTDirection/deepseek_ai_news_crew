from TotalVideoWithLLM import LongNewsProcessor
from video_concatenator import VideoConcatenator

def process_and_concatenate_news(news_text, project_name=None, auto_concatenate=True):
    """
    Process a news text to generate video segments and then concatenate them
    
    Args:
        news_text: The long news text to process
        project_name: Optional custom name for the project
        auto_concatenate: Whether to automatically concatenate videos after generation
        
    Returns:
        dict: A dictionary containing results of both processes
    """
    # Step 1: Process the news text and generate video segments
    processor = LongNewsProcessor(
        max_chars_per_segment=25,  # Characters per segment
        max_audio_duration=4.8     # Maximum audio duration in seconds
    )
    
    # Process the news
    result = processor.process_long_news(
        news_text,
        project_name=project_name,
        calibrate=True,             # Whether to calibrate speech rate
        add_subtitles=True,         # Add subtitles to videos
        subtitle_format="srt"       # Subtitle format (srt, ass, vtt)
    )
    
    # Get output information
    segments_dir = result['output_directory']
    segments_count = result['successful_segments']
    
    print(f"\n=== Video segments generation complete ===")
    print(f"Successfully generated {segments_count} video segments")
    print(f"Videos directory: {segments_dir}")
    
    # Step 2: Concatenate the generated videos
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
    long_news = """
【AI日报】2025年05月30日
1. 企业级AI战略加速落地！传微软与巴克莱银行签订10万份Copilot许可证
微软在全员大会上展示企业级AI业务进展，其中与巴克莱银行达成的10万份Copilot许可证交易成为焦点。这一合作标志着企业级AI应用的快速落地，预计将推动更多金融机构采用AI技术，对行业具有变革性影响。
2. 不只是"小升级"！DeepSeek-R1新版获海外盛赞
DeepSeek最新发布的R1模型升级版在全球AI领域掀起热议，多位国际科技大佬及行业高管盛赞其技术突破。实测显示该模型在多项基准测试中表现优异，标志着中国AI公司在技术上的重大进步。
3. 云从科技多模态大模型「CongRong-v2.0」登顶全球榜单
云从科技自主研发的「从容大模型」在国际评测平台OpenCompass最新全球多模态榜单中，以80.7分的综合成绩登顶榜首。这一成绩标志着中国在多模态AI领域的技术实力获得国际认可。
    """
    
    # Process and concatenate
    result = process_and_concatenate_news(
        news_text=long_news,
        project_name="ai_news_demo",
        auto_concatenate=True
    )
    
    # Print results
    if result['concatenation']['status'] == 'success':
        print(f"\n✅ Complete process successful!")
        print(f"Final video: {result['concatenation']['output_path']}")
    else:
        print(f"\n⚠️ Video segments generated but concatenation {result['concatenation']['status']}")
        if result['concatenation']['status'] == 'failed':
            print("Check logs for error details")