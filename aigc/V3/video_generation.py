import os
from MultimodalRobot import MultimodalNewsBot, TTSModule
import random

class VideoSegmentGenerator:
    """Module for generating video segments with TTS and images"""
    
    def __init__(self, output_dir="output/segments"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        self.news_bot = MultimodalNewsBot()
        self.tts_module = TTSModule()
    
    def generate_random_seed(self):
        """Generate random seed for consistent generation"""
        return random.randint(1, 10000)
    
    def generate_segment(self, text, segment_id, video_duration=5.0):
        """
        Generate a video segment for the given text
        
        Args:
            text: Text content for the segment
            segment_id: Unique identifier for the segment
            video_duration: Duration of the video in seconds
            
        Returns:
            dict: Segment generation results
        """
        try:
            print(f"Processing segment: {segment_id}")
            print(f"Content: {text}")
            
            # Generate random seed
            seed = self.generate_random_seed()
            print(f"Using random seed: {seed}")
            
            # Generate voice
            print("Generating voice...")
            voice_path, audio_duration = self.tts_module.generate_voice(
                text, f"{segment_id}_voice"
            )
            
            # Generate image
            print("Generating image...")
            image_paths = self.news_bot.image_module.generate_image(
                text, f"{segment_id}_image",
                ratio="16:9", seed=seed
            )
            
            # Generate video
            print("Generating video...")
            video_path = self.news_bot.video_module.generate_video(
                text, video_duration, image_paths, f"{segment_id}_video",
                resolution="720p", ratio="16:9"
            )
            
            return {
                "segment_id": segment_id,
                "text": text,
                "voice_path": voice_path,
                "image_paths": image_paths,
                "video_path": video_path,
                "audio_duration": audio_duration,
                "seed": seed,
                "status": "success"
            }
            
        except Exception as e:
            print(f"Error generating segment {segment_id}: {e}")
            return {
                "segment_id": segment_id,
                "text": text,
                "status": "failed",
                "error": str(e)
            }