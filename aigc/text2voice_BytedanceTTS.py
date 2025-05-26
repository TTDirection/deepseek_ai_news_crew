import requests
import os
from datetime import datetime

class BytedanceTTS:
    def __init__(self, url="http://172.31.10.71:8000/api/v1/bytedance/tts"):
        """初始化字节跳动TTS类
        
        Args:
            url (str): TTS服务的API地址
        """
        self.url = url
        self.headers = {"Content-Type": "application/json"}
        
    def generate(self, text, voice_type="zh_female_roumeinvyou_emo_v2_mars_bigtts", output_file=None):
        """生成语音文件
        
        Args:
            text (str): 需要转换为语音的文本
            voice_type (str): 语音类型
            output_file (str, optional): 输出文件路径。如果为None，则自动生成文件名
            
        Returns:
            str: 生成的音频文件的路径
        """
        # 如果没有指定输出文件，创建一个基于时间戳的文件名
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = "output/tts_output"
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"tts_{timestamp}.wav")
        
        # 构建请求数据
        data = {
            "text": text,
            "voice_type": voice_type
        }
        
        # 发送请求
        response = requests.post(self.url, headers=self.headers, json=data)
        
        # 检查响应状态
        if response.status_code == 200:
            # 保存音频文件
            with open(output_file, "wb") as f:
                f.write(response.content)
            print(f"音频已保存至 {output_file}")
            return output_file
        else:
            error_msg = f"请求失败，状态码: {response.status_code}, 错误信息: {response.text}"
            print(error_msg)
            raise Exception(error_msg)
            
    def get_available_voices(self):
        """获取可用的语音类型列表（如果API支持此功能）
        
        Returns:
            list: 可用语音类型列表
        """
        # 注意：此功能取决于API是否支持获取语音类型列表
        # 如果API不支持，可以返回预定义的列表或实现其他逻辑
        # 这只是一个示例实现
        return ["zh_female_roumeinvyou_emo_v2_mars_bigtts"]

# 使用示例
if __name__ == "__main__":
    # 创建TTS对象
    tts = BytedanceTTS()
    
    # 要转换的文本
    text = """
    与一两年前相比，谷歌的AI进展显著加快，Gemini 2.5系列模型已能响应文本、图像、音频和视频。
    这一系列更新展示了谷歌在构建全方位AI生态系统方面的战略布局和行业领先优势。
    """
    
    # 生成语音文件
    # 可以指定输出文件名，也可以让它自动生成
    output_path = tts.generate(text)
    
    print(f"生成的音频文件路径: {output_path}")