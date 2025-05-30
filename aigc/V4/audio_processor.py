import os
import requests
import json
import time
import librosa
from typing import Dict, Any, Tuple, Optional

class AudioProcessor:
    """音频处理器，负责生成和处理音频"""
    
    def __init__(self, output_dir: str = "output/audio", api_config: Dict[str, Any] = None):
        """初始化音频处理器
        
        Args:
            output_dir: 音频输出目录
            api_config: API配置
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # 默认API配置
        self.config = {
            "api_key": "YOUR_API_KEY",
            "base_url": "https://api.deepseek.com/v1",
            "tts_model": "deepseek-tts",
            "voice_id": "zh-CN-YunxiNeural",  # 默认中文男声
            "rate": 1.0,  # 语速
            "pitch": 1.0  # 音调
        }
        
        if api_config:
            self.config.update(api_config)
    
    def generate_voice(self, text: str, filename: Optional[str] = None) -> Tuple[str, float]:
        """生成语音文件
        
        Args:
            text: 要转换为语音的文本
            filename: 可选的文件名（不含扩展名）
            
        Returns:
            Tuple[str, float]: 语音文件路径和音频时长
        """
        print(f"正在生成语音: {text[:30]}...")
        
        # 生成文件名
        if filename is None:
            timestamp = int(time.time())
            filename = f"voice_{timestamp}"
        
        # 构建API请求
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config['api_key']}"
        }
        
        data = {
            "model": self.config["tts_model"],
            "input": text,
            "voice": self.config["voice_id"],
            "response_format": "mp3",
            "speed": self.config["rate"],
            "pitch": self.config["pitch"]
        }
        
        # 发送请求
        try:
            response = requests.post(
                f"{self.config['base_url']}/audio/speech",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            
            # 保存音频文件
            output_path = os.path.join(self.output_dir, f"{filename}.mp3")
            with open(output_path, "wb") as f:
                f.write(response.content)
            
            # 获取音频时长
            audio_duration = self.get_audio_duration(output_path)
            
            print(f"语音生成成功: {output_path} (时长: {audio_duration:.2f}秒)")
            return output_path, audio_duration
            
        except Exception as e:
            print(f"语音生成失败: {e}")
            raise
    
    def get_audio_duration(self, audio_path: str) -> float:
        """获取音频文件的时长
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            float: 音频时长（秒）
        """
        try:
            y, sr = librosa.load(audio_path, sr=None)
            duration = librosa.get_duration(y=y, sr=sr)
            return duration
        except Exception as e:
            print(f"获取音频时长失败: {e}")
            return 0.0
    
    def calibrate_speech_rate(self, sample_text: str = "这是一段用于校准语速的测试文本") -> float:
        """校准语速参数
        
        Args:
            sample_text: 用于校准的样本文本
            
        Returns:
            float: 估计的每秒字符数
        """
        print("正在校准语速参数...")
        
        try:
            # 生成样本语音
            _, audio_duration = self.generate_voice(sample_text, "calibration_sample")
            
            # 计算字符数（去除空白字符）
            cleaned_text = sample_text.replace(" ", "").replace("\n", "").replace("\t", "")
            char_count = len(cleaned_text)
            
            # 计算每秒字符数
            chars_per_second = char_count / audio_duration if audio_duration > 0 else 5.0
            
            print(f"语速校准完成: {chars_per_second:.2f} 字符/秒")
            return chars_per_second
            
        except Exception as e:
            print(f"语速校准失败: {e}，使用默认值 5.0 字符/秒")
            return 5.0