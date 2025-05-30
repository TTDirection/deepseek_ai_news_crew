from TotalVideoWithLLM import LongNewsProcessor
from video_concatenator import VideoConcatenator

def process_and_concatenate_news(news_text, project_name=None, auto_concatenate=True, 
                                use_multiprocessing=True, max_workers=None):
    """
    Process a news text to generate video segments and then concatenate them
    
    Args:
        news_text: The long news text to process
        project_name: Optional custom name for the project
        auto_concatenate: Whether to automatically concatenate videos after generation
        use_multiprocessing: Whether to use multiprocessing for faster generation
        max_workers: Maximum number of parallel processes
        
    Returns:
        dict: A dictionary containing results of both processes
    """
    # Step 1: Process the news text and generate video segments
    processor = LongNewsProcessor(
        max_chars_per_segment=25,  # Characters per segment
        max_audio_duration=4.8,   # Maximum audio duration in seconds
        max_workers=max_workers    # Number of parallel processes
    )
    
    # Process the news
    result = processor.process_long_news(
        news_text,
        project_name=project_name,
        calibrate=True,                    # Whether to calibrate speech rate
        add_subtitles=True,                # Add subtitles to videos
        subtitle_format="srt",             # Subtitle format (srt, ass, vtt)
        use_multiprocessing=use_multiprocessing  # Enable/disable multiprocessing
    )
    
    # Get output information
    segments_dir = result['output_directory']
    segments_count = result['successful_segments']
    processing_time = result['processing_time_seconds']
    
    print(f"\n=== Video segments generation complete ===")
    print(f"Successfully generated {segments_count} video segments")
    print(f"Processing time: {processing_time:.2f} seconds")
    print(f"Mode: {'Multiprocessing' if result['multiprocessing_used'] else 'Single process'}")
    if result['multiprocessing_used']:
        print(f"Parallel workers: {result['max_workers']}")
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
微软在全员大会上展示企业级AI业务进展，其中与巴克莱银行达成的10万份Copilot许可证交易成为焦点。
    """
    
    # Process and concatenate with multiprocessing enabled
    result = process_and_concatenate_news(#?
        news_text=long_news,
        project_name="ai_news_0530_mp",
        auto_concatenate=True,
        use_multiprocessing=True,  # Enable multiprocessing
        max_workers=3              # Use 3 parallel processes
    )
    
    # Print results
    if result['concatenation']['status'] == 'success':
        print(f"\n✅ Complete process successful!")
        print(f"Final video: {result['concatenation']['output_path']}")
        print(f"Total processing time: {result['processing_time_seconds']:.2f} seconds")
    else:
        print(f"\n⚠️ Video segments generated but concatenation {result['concatenation']['status']}")
        if result['concatenation']['status'] == 'failed':
            print("Check logs for error details")