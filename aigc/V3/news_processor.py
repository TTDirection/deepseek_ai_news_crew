import os
import random
import json
from datetime import datetime
import concurrent.futures
from MultimodalRobot import TTSModule
from text_segmentation import TextSegmenter
from video_generation import VideoSegmentGenerator
from subtitle_manager import SubtitleManager
from audio_video_processor import AudioVideoProcessor

class LongNewsProcessor:
    """Long news processor that supports segmented broadcasting with parallel processing"""
    
    def __init__(self, max_chars_per_segment=20, max_audio_duration=4.8):
        """
        Initialize long news processor
        
        Args:
            max_chars_per_segment: Maximum characters per segment
            max_audio_duration: Maximum audio duration in seconds
        """
        self.max_chars_per_segment = max_chars_per_segment
        self.max_audio_duration = max_audio_duration
        
        # Initialize components
        self.tts_module = TTSModule()
        self.text_segmenter = TextSegmenter(
            max_chars_per_segment=max_chars_per_segment,
            max_audio_duration=max_audio_duration
        )
        self.video_generator = VideoSegmentGenerator()
        self.subtitle_manager = SubtitleManager()
        self.av_processor = AudioVideoProcessor()
        
        # Estimated characters per second (will be calibrated)
        self.estimated_chars_per_second = 5.0
        
        # Create output directories
        self.output_dir = os.path.join("output", "long_news")
        self.segments_dir = os.path.join(self.output_dir, "segments")
        self.final_videos_dir = os.path.join(self.output_dir, "final_videos")
        self.subtitles_dir = os.path.join(self.output_dir, "subtitles")
        
        for dir_path in [self.output_dir, self.segments_dir, self.final_videos_dir, self.subtitles_dir]:
            os.makedirs(dir_path, exist_ok=True)
    
    def process_segment(self, segment, segment_id, add_subtitles, subtitle_format, subtitle_style):
        """
        Process a single news segment (used for parallel processing)
        
        Args:
            segment: Text segment to process
            segment_id: Unique identifier for the segment
            add_subtitles: Whether to add subtitles
            subtitle_format: Subtitle format ("srt", "ass", "vtt")
            subtitle_style: Subtitle style settings
            
        Returns:
            dict: Segment processing result
        """
        print(f"Processing segment: {segment_id}")
        
        try:
            # Generate video segment
            segment_result = self.video_generator.generate_segment(
                segment, segment_id, 5.0
            )
            
            if segment_result["status"] == "success":
                # Merge audio and video
                print(f"[{segment_id}] Merging audio and video...")
                temp_video_path = os.path.join(
                    self.final_videos_dir, f"{segment_id}_temp.mp4"
                )
                
                merged_video = self.av_processor.merge_audio_video(
                    segment_result["voice_path"], 
                    segment_result["video_path"], 
                    temp_video_path
                )
                
                final_video_path = None
                subtitle_path = None
                
                # Add subtitles if enabled
                if merged_video and add_subtitles:
                    # Create subtitle file
                    print(f"[{segment_id}] Creating subtitles...")
                    subtitle_base_path = os.path.join(self.subtitles_dir, f"{segment_id}_subtitle")
                    subtitle_path = self.subtitle_manager.create_subtitle_file(
                        segment, segment_result["audio_duration"], subtitle_base_path, subtitle_format
                    )
                    
                    # Add subtitles to video
                    print(f"[{segment_id}] Adding subtitles to video...")
                    final_video_path = os.path.join(
                        self.final_videos_dir, f"{segment_id}_final.mp4"
                    )
                    
                    final_video_with_subtitles = self.subtitle_manager.add_subtitles_to_video(
                        merged_video, subtitle_path, final_video_path, subtitle_style
                    )
                    
                    if final_video_with_subtitles:
                        # Delete temporary video file
                        if os.path.exists(temp_video_path):
                            os.remove(temp_video_path)
                        final_video_path = final_video_with_subtitles
                    else:
                        # If adding subtitles fails, use version without subtitles
                        print(f"[{segment_id}] Subtitle addition failed, using version without subtitles")
                        final_video_path = temp_video_path
                
                elif merged_video:
                    # Don't add subtitles, use merged video directly
                    final_video_path = os.path.join(
                        self.final_videos_dir, f"{segment_id}_final.mp4"
                    )
                    
                    # Rename temporary file
                    if os.path.exists(temp_video_path):
                        os.rename(temp_video_path, final_video_path)
                
                # Update segment result with final paths
                segment_result.update({
                    "final_video_path": final_video_path,
                    "subtitle_path": subtitle_path,
                    "has_subtitles": add_subtitles and subtitle_path is not None,
                    "subtitle_format": subtitle_format if add_subtitles else None,
                    "estimated_duration": self.text_segmenter.estimate_audio_duration(segment),
                })
            
            print(f"Segment {segment_id} processing complete")
            return segment_result
            
        except Exception as e:
            error_msg = f"Error processing segment {segment_id}: {e}"
            print(error_msg)
            return {
                "segment_id": segment_id,
                "text": segment,
                "status": "failed",
                "error": str(e)
            }
    
    def process_long_news(self, news_text, project_name=None, calibrate=True,
                         add_subtitles=True, subtitle_format="srt",
                         subtitle_style=None, parallel_processing=False, max_workers=4):
        """
        Process long news, generate segmented broadcast
        
        Args:
            news_text: Long news text
            project_name: Project name (optional)
            calibrate: Whether to calibrate speech rate
            add_subtitles: Whether to add subtitles
            subtitle_format: Subtitle format ("srt", "ass", "vtt")
            subtitle_style: Subtitle style settings
            parallel_processing: Whether to process segments in parallel
            max_workers: Maximum number of worker threads for parallel processing
            
        Returns:
            dict: Processing results
        """
        if project_name is None:
            project_name = f"long_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        print(f"Starting to process long news project: {project_name}")
        print(f"Original news length: {len(news_text)} characters")
        print(f"Subtitle setting: {'Enabled' if add_subtitles else 'Disabled'} ({subtitle_format})")
        if parallel_processing:
            print(f"Parallel processing: Enabled (max workers: {max_workers})")
        
        # Step 0: Speech rate calibration (optional)
        if calibrate:
            print("\n=== Step 0: Speech Rate Calibration ===")
            self.estimated_chars_per_second = self.av_processor.calibrate_speech_rate(self.tts_module)
            # Update segmenter with calibrated rate
            self.text_segmenter.estimated_chars_per_second = self.estimated_chars_per_second
        
        # Step 1: Intelligent text segmentation
        print("\n=== Step 1: Intelligent Text Segmentation ===")
        segments = self.text_segmenter.segment_text(news_text)
        print(f"Segmentation yielded {len(segments)} segments")
        
        # Print segmentation preview
        for i, segment in enumerate(segments):
            estimated_duration = self.text_segmenter.estimate_audio_duration(segment)
            print(f"Segment {i+1}: {len(segment)} chars, estimated {estimated_duration:.2f} seconds")
            print(f"  Content: {segment}")
        
        # Step 2: Generate multimodal content for each segment
        print(f"\n=== Step 2: Generate Multimodal Content {'(with subtitles)' if add_subtitles else ''} ===")
        
        results = []
        
        # Prepare segment data
        segment_data = []
        for i, segment in enumerate(segments):
            segment_id = f"{project_name}_segment_{i+1:03d}"
            segment_data.append({
                'segment': segment,
                'segment_id': segment_id,
                'index': i
            })
        
        # Process segments (parallel or sequential)
        if parallel_processing and len(segments) > 1:
            print(f"Using parallel processing with {max_workers} workers")
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all segment processing tasks
                future_to_segment = {}
                for data in segment_data:
                    future = executor.submit(
                        self.process_segment,
                        data['segment'],
                        data['segment_id'],
                        add_subtitles,
                        subtitle_format,
                        subtitle_style
                    )
                    future_to_segment[future] = data
                
                # Process results as they complete
                for future in concurrent.futures.as_completed(future_to_segment):
                    data = future_to_segment[future]
                    try:
                        segment_result = future.result()
                        # Add segment index
                        segment_result["segment_index"] = data['index'] + 1
                        results.append(segment_result)
                    except Exception as exc:
                        print(f"Segment {data['segment_id']} generated an exception: {exc}")
                        results.append({
                            "segment_id": data['segment_id'],
                            "segment_index": data['index'] + 1,
                            "text": data['segment'],
                            "status": "failed",
                            "error": str(exc)
                        })
        else:
            # Sequential processing
            print("Using sequential processing")
            for data in segment_data:
                segment_result = self.process_segment(
                    data['segment'],
                    data['segment_id'],
                    add_subtitles,
                    subtitle_format,
                    subtitle_style
                )
                # Add segment index
                segment_result["segment_index"] = data['index'] + 1
                results.append(segment_result)
        
        # Sort results by segment index
        results.sort(key=lambda x: x.get("segment_index", 0))
        
        # Summarize results
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
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "parallel_processing_used": parallel_processing,
            "max_workers": max_workers if parallel_processing else None
        }
        
        # Save results to JSON file
        result_file = os.path.join(self.output_dir, f"{project_name}_result.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, ensure_ascii=False, indent=2)
        
        print(f"\n=== Processing Complete ===")
        print(f"Project name: {project_name}")
        print(f"Total segments: {total_segments}")
        print(f"Successful segments: {successful_segments}")
        print(f"Subtitle status: {'Added' if add_subtitles else 'Not added'}")
        print(f"Output directory: {self.final_videos_dir}")
        print(f"Subtitle directory: {self.subtitles_dir}")
        print(f"Result file: {result_file}")
        print(f"Processing mode: {'Parallel' if parallel_processing else 'Sequential'}")
        
        return final_result