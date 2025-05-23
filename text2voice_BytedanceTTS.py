import requests
import os
from datetime import datetime
from pathlib import Path

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
            output_file (str, optional): 输出文件路径。如果为None，则抛出错误
            
        Returns:
            str: 生成的音频文件的路径
            
        Raises:
            ValueError: 如果 output_file 为 None
        """
       # 如果未提供 output_file，设置为默认路径 logs/ai_news_report_{today_str}.wav
        if output_file is None:
            today_str = datetime.now().strftime("%Y%m%d")
            output_file = Path("Outputs") / f"ai_news_report_{today_str}.wav"
        else:
            output_file = Path(output_file)
        
        # 确保输出目录存在
        output_file.parent.mkdir(exist_ok=True)             
        
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
            return str(output_file)
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

    # 定义输出目录为 Path 对象
    output_dir = Path("Outputs")

    # 如果输出目录不存在，则创建
    output_dir.mkdir(exist_ok=True)

    # 初始化 mp3_file 为 None 或默认值
    mp3_file = None

    # 如果 mp3_file 未设置，则构建文件路径
    if not mp3_file:
        today_str = datetime.now().strftime("%Y%m%d")
        mp3_file = output_dir / f"ai_news_report_{today_str}.wav"

    # 将 mp3_file 转换为字符串
    mp3_file = str(mp3_file)
        
    # 要转换的文本
    text = """
   【AI日报】2025年05月23日

## 1. 摩根大通大赞谷歌：AI技术领先，远超此前的创新速度
谷歌宣布了Gemini 2.5 Pro和Gemini 2.5 Flash的升级，以及新文本模型Gemini Diffusion的实验演示。摩根大通分析师高度评价谷歌在AI领域的领先地位，认为其创新速度远超预期。Gemini系列模型在多项基准测试中表现优异，已开始向企业用户提供高级功能订阅服务。

## 2. Google大会一文读懂：用AI革自己的命
谷歌在年度开发者大会上发布了十余款AI新产品，包括轻量级的Gemini 2.5 Flash模型和Veo 3视频生成系统。Gemini 2.5 Flash兼具高速和强大推理能力，而Veo 3首次实现了画面与声音的一体化生成，被认为比OpenAI的Sora更进一步。这些创新展示了谷歌在AI领域的全面布局。

## 3. OpenAI再强，也挡不住Google往生态里狂塞AI
谷歌Gemini 2.5 Pro在多方面领先竞争对手，Elo评分比第一代Gemini Pro提升了300多分。谷歌正将AI技术深度整合到搜索、办公等核心产品中，通过生态优势与OpenAI竞争。分析师认为谷歌的AI战略正在取得显著成效，用户覆盖面和产品集成度远超单一AI公司。

## 4. 腾讯混元大模型矩阵全面升级并推出多款新品
腾讯宣布混元大模型系列全面升级，其中混元Voice模型实现了低延迟语音通话，提升了响应速度和拟人性，已在腾讯元宝App灰度上线。同时发布的还有多款多模态模型，包括混元图像生成等新功能，展示了腾讯在AI领域的持续投入和技术积累。

## 5. 多模态大模型MMaDA：让AI学会「跨次元思考」
新型多模态大模型MMaDA号称能让AI拥有深度思考能力，在文本、图像和复杂推理任务间灵活转换。开发者表示其表现力超越GPT-4、Gemini和SDXL等知名模型，特别擅长跨模态理解和生成任务，为AI应用开辟了新的可能性。

## 6. 图像分词器造反了！华为Selftok：自回归内核完美统一扩散模型
华为发布Selftok技术，成功将自回归(AR)范式应用于图像领域，统一了扩散模型架构。该技术借鉴了大语言模型的离散token处理方法，在图像生成领域取得突破，有望为计算机视觉带来新的发展路径。

## 7. 基于扩散模型的视频生成技术解析与实践指南
技术文章详细解析了扩散模型在视频生成领域的应用原理和实践方法，特别介绍了DeepSeek大模型在AIGC(人工智能生成内容)中的创新应用。内容包括模型架构设计、训练技巧和实际应用案例，为开发者提供了实用参考。
    """
    
    # 生成语音文件
    output_path = tts.generate(text, output_file=mp3_file)
    
    print(f"生成的音频文件路径: {output_path}")