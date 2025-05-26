import librosa

def get_audio_length(file_path):
    # 只加载头部，获取采样率和总采样点数
    y, sr = librosa.load(file_path, sr=None)
    duration = len(y) / sr
    return duration
#/home/taotao/Desktop/PythonProject/deepseek_ai_news_crew/aigc/volcengine-python-sdk-master/volcengine-python-sdk-master/setup.py
# 示例
audio_path = '/home/taotao/Desktop/PythonProject/deepseek_ai_news_crew/aigc/output/voice/voice.mp3'
length = f'{get_audio_length(audio_path):.1f}'
print(f'音频长度为 {length} 秒')