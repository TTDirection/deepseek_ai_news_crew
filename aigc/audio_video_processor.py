import os
import subprocess

class AudioVideoProcessor:
    """Handles audio and video processing operations"""
    
    def __init__(self, output_dir="output/processed"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def merge_audio_video(self, audio_path, video_path, output_path):
        """
        Merge audio and video, trimming video duration to match audio
        
        Args:
            audio_path: Audio file path
            video_path: Video file path
            output_path: Output file path
            
        Returns:
            str: Path to merged video file
        """
        try:
            # Use ffmpeg to merge audio and video, and trim video length
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-shortest',  # Use the shortest stream as the output length
                output_path
            ]
            
            print(f"Merging audio and video: {output_path}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"Audio-video merge successful: {output_path}")
                return output_path
            else:
                print(f"Audio-video merge failed: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"Error in audio-video merge: {e}")
            return None
    
    def calibrate_speech_rate(self, tts_module, sample_text="这是一个用于测试语速的示例文本，包含了中文和English单词。"):
        """
        Calibrate speech rate parameters
        
        Args:
            tts_module: TTS module instance
            sample_text: Sample text for testing
            
        Returns:
            float: Calibrated characters/second rate
        """
        # Implementation details...
        # This would be similar to your original code
        # Omitted for brevity