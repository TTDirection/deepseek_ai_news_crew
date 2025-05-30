import os
import requests
import librosa
from datetime import datetime
from volcenginesdkarkruntime import Ark
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from typing import Optional, List, Tuple
import json
import base64
import mimetypes
from pathlib import Path
from PIL import Image
import io
import time
import math

# ================================
# 核心配置参数
# ================================

# API配置
API_CONFIG = {
    "api_key": "5cf8e2f7-8465-4ccc-bf84-e32f05be0fb4",
    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "llm_model": "ep-20250427095319-t4sw8",
    "image_model": "doubao-seedream-3-0-t2i-250415",
    "video_model": "doubao-seedance-1-0-lite-i2v-250428",
    "tts_url": "http://172.31.10.71:8000/api/v1/bytedance/tts",
    "voice_type": "ICL_zh_female_zhixingwenwan_tob"
}

# 输出目录配置
OUTPUT_CONFIG = {
    "base_dir": "output",
    "voice_dir": "voice",
    "image_dir": "image", 
    "video_dir": "video"
}

# 文件处理配置
FILE_CONFIG = {
    "max_image_size_mb": 10,
    "jpeg_quality": 90,
    "supported_image_formats": {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
        '.tiff': 'image/tiff',
        '.tif': 'image/tiff',
        '.gif': 'image/gif'
    }
}

# 图片生成配置
IMAGE_CONFIG = {
    "default_size": "1280x720",
    "supported_sizes": {
        "1:1": "1024x1024",
        "3:4": "864x1152", 
        "4:3": "1152x864",
        "16:9": "1280x720",
        "9:16": "720x1280",
        "2:3": "832x1248",
        "3:2": "1248x832",
        "21:9": "1512x648"
    },
    "response_format": "url",
    "default_guidance_scale": 2.5,
    "default_seed": -1
}

# 视频生成配置
VIDEO_CONFIG = {
    "default_resolution": "720p",
    "default_ratio": "16:9",
    "supported_ratios": ["16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "9:21"],
    "min_duration": 5,  # 最小5秒
    "max_duration": 10, # 最大10秒
    "default_duration": 5,
    "max_wait_time": 300,
    "check_interval": 10
}

# 提示词模板配置
PROMPT_TEMPLATES = {
    "image_generation": """作为专业的摄影师和视觉艺术总监，请将以下AI新闻内容转换为极其真实的摄影场景描述。并限制描述的长度，避免超过100字。

要求：
1. 采用纪实摄影风格，画面真实自然，具有新闻摄影质感
2. 描述具体的现实场景：现代化办公环境、科技公司内部、数据中心、研发实验室等
3. 包含真实的光影效果：自然光、室内照明、屏幕光源反射等
4. 添加细节元素：现代化设备、显示屏、工作人员背影、科技设备细节
5. 色彩真实自然：冷暖色调平衡，符合现代办公环境的色彩搭配
6. 避免夸张特效，追求专业新闻摄影的质感
7. 场景应该像真实拍摄的新闻照片一样可信
8. 减少对显示器以及其他带有文字的部件的描述，注重场景，因为该生成模型对文字的生成支持不好
9. 输出仅保留相关场景描述即可，无需说明扩充后的提示词长度

新闻内容：{news_content}

请用专业摄影术语描述一个真实可拍摄的场景，仿佛是为新闻报道拍摄的照片：""",

    "video_generation": """作为专业的纪录片导演，请将以下AI新闻内容转换为真实的视频拍摄场景描述。并限制描述的长度，避免超过100字。

要求：
1. 时长：{duration}秒的真实纪录片风格画面
2. 拍摄风格：类似BBC或CNN新闻纪录片的真实感
3. 场景描述：现代化办公室、科技公司、研发中心等真实环境
4. 镜头运动：缓慢推拉、平移，模拟专业摄像师操作
5. 光影效果：自然光线变化，真实的室内照明环境
6. 细节展现：键盘敲击、屏幕内容变化、人员走动等真实细节
7. 色彩风格：真实自然的色调，符合现代办公环境
8. 避免特效和动画，追求纪录片的真实质感
9. 减少对显示器以及其他带有文字的部件的描述，注重场景，因为该生成模型对文字的生成支持不好
10. 输出仅保留相关场景描述即可，无需说明扩充后的提示词长度

新闻内容：{news_content}

请描述一个可以真实拍摄的{duration}秒纪录片场景："""
}

# ================================
# 模块1：TTS语音生成
# ================================

class TTSModule:
    """文本转语音模块"""
    
    def __init__(self, custom_config=None):
        self.config = API_CONFIG.copy()
        if custom_config:
            self.config.update(custom_config)
        
        self.tts_url = self.config["tts_url"]
        self.voice_type = self.config["voice_type"]
        self.headers = {"Content-Type": "application/json"}
        
        # 创建输出目录
        self.voice_dir = os.path.join(OUTPUT_CONFIG["base_dir"], OUTPUT_CONFIG["voice_dir"])
        os.makedirs(self.voice_dir, exist_ok=True)
    
    def generate_voice(self, text: str, filename: Optional[str] = None) -> tuple[str, float]:
        """
        生成语音文件
        
        Args:
            text: 要转换的文本
            filename: 可选的文件名（不含扩展名）
            
        Returns:
            tuple: (语音文件路径, 音频时长)
        """
        print("正在生成语音文件...")
        
        # 生成文件名
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tts_{timestamp}"
        
        output_file = os.path.join(self.voice_dir, f"{filename}.wav")
        
        # 调用TTS API
        data = {
            "text": text,
            "voice_type": self.voice_type
        }
        
        response = requests.post(self.tts_url, headers=self.headers, json=data)
        
        if response.status_code == 200:
            with open(output_file, "wb") as f:
                f.write(response.content)
            
            # 获取音频时长
            try:
                duration = librosa.get_duration(filename=output_file)
            except Exception as e:
                print(f"获取音频时长失败: {e}")
                duration = 5.0  # 默认时长
            
            print(f"语音文件已保存: {output_file}")
            print(f"音频时长: {duration:.2f}秒")
            
            return output_file, duration
        else:
            error_msg = f"TTS请求失败，状态码: {response.status_code}, 错误信息: {response.text}"
            print(error_msg)
            raise Exception(error_msg)

# ================================
# 模块2：图片生成模块
# ================================

class ImageGenerationModule:
    """提示词扩写并生成图片模块"""
    
    def __init__(self, custom_config=None):
        self.config = API_CONFIG.copy()
        if custom_config:
            self.config.update(custom_config)
        
        # 初始化LLM用于提示词优化
        self.llm = ChatOpenAI(
            temperature=0.0,
            model=self.config["llm_model"],
            openai_api_key=self.config["api_key"],
            openai_api_base=self.config["base_url"]
        )
        
        # 初始化图片生成器
        self.image_generator = Ark(
            base_url=self.config["base_url"],
            api_key=self.config["api_key"],
        )
        
        # 创建输出目录
        self.image_dir = os.path.join(OUTPUT_CONFIG["base_dir"], OUTPUT_CONFIG["image_dir"])
        os.makedirs(self.image_dir, exist_ok=True)
    
    def optimize_prompt_for_image(self, original_prompt: str) -> str:
        """优化原始提示词用于图像生成"""
        print("正在优化图片生成提示词...")
        
        image_prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATES["image_generation"])
        messages = image_prompt_template.format_messages(news_content=original_prompt)
        response = self.llm.invoke(messages)
        
        optimized_prompt = response.content.strip()
        print(f"优化后的图片提示词: {optimized_prompt}")
        
        return optimized_prompt
    
    def generate_image(self, original_prompt: str, filename: Optional[str] = None,
                      size: str = None, ratio: str = None, 
                      guidance_scale: float = None, seed: int = None) -> List[str]:
        """
        扩写提示词并生成图片
        
        Args:
            original_prompt: 原始提示词
            filename: 可选的文件名（不含扩展名）
            size: 图片尺寸
            ratio: 图片比例
            guidance_scale: 引导强度
            seed: 随机种子
            
        Returns:
            List[str]: 生成的图片文件路径列表
        """
        print("开始生成图片...")
        
        # 步骤1: 优化提示词
        optimized_prompt = self.optimize_prompt_for_image(original_prompt)
        
        # 添加写实风格描述
        realistic_prompt = f"photorealistic, documentary style, professional photography, high quality, detailed, {optimized_prompt}"
        
        # 生成文件名
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"image_{timestamp}"
        
        # 确定图片尺寸
        if size:
            img_size = size
        elif ratio and ratio in IMAGE_CONFIG["supported_sizes"]:
            img_size = IMAGE_CONFIG["supported_sizes"][ratio]
        else:
            img_size = IMAGE_CONFIG["default_size"]
        
        # 步骤2: 生成图片
        generation_params = {
            "model": self.config["image_model"],
            "prompt": realistic_prompt,
            "size": img_size,
            "response_format": IMAGE_CONFIG["response_format"],
            "guidance_scale": guidance_scale or IMAGE_CONFIG["default_guidance_scale"],
            "seed": seed if seed is not None else IMAGE_CONFIG["default_seed"]
        }
        
        print(f"图片生成参数: {generation_params}")
        
        response = self.image_generator.images.generate(**generation_params)
        
        saved_paths = []
        
        for i, image_data in enumerate(response.data):
            image_url = image_data.url
            
            image_response = requests.get(image_url)
            if image_response.status_code != 200:
                print(f"下载图像失败: {image_response.status_code}")
                continue
            
            if len(response.data) > 1:
                file_path = os.path.join(self.image_dir, f"{filename}_{i}.png")
            else:
                file_path = os.path.join(self.image_dir, f"{filename}.png")
            
            with open(file_path, 'wb') as f:
                f.write(image_response.content)
            
            print(f"图像已保存: {file_path}")
            saved_paths.append(file_path)
        
        return saved_paths

# ================================
# 模块3：视频生成模块
# ================================

class VideoGenerationModule:
    """提示词扩写并生成视频模块"""
    
    def __init__(self, custom_config=None):
        self.config = API_CONFIG.copy()
        if custom_config:
            self.config.update(custom_config)
        
        # 初始化LLM用于提示词优化
        self.llm = ChatOpenAI(
            temperature=0.0,
            model=self.config["llm_model"],
            openai_api_key=self.config["api_key"],
            openai_api_base=self.config["base_url"]
        )
        
        # 创建输出目录
        self.video_dir = os.path.join(OUTPUT_CONFIG["base_dir"], OUTPUT_CONFIG["video_dir"])
        os.makedirs(self.video_dir, exist_ok=True)
    
    def optimize_prompt_for_video(self, original_prompt: str, duration: int) -> str:
        """优化原始提示词用于视频生成"""
        print("正在优化视频生成提示词...")
        
        video_prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATES["video_generation"])
        messages = video_prompt_template.format_messages(
            news_content=original_prompt,
            duration=duration
        )
        response = self.llm.invoke(messages)
        
        optimized_prompt = response.content.strip()
        print(f"优化后的视频提示词: {optimized_prompt}")
        
        return optimized_prompt
    
    def get_mimetype(self, file_path):
        """获取文件的MIME类型"""
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type or not mime_type.startswith('image/'):
            ext = Path(file_path).suffix.lower()
            mime_type = FILE_CONFIG["supported_image_formats"].get(ext)
        
        if not mime_type:
            raise ValueError(f"不支持的图片格式: {file_path}")
        return mime_type

    def convert_to_jpeg_if_needed(self, image_path):
        """如果图片不是JPEG格式，转换为JPEG格式"""
        try:
            mime_type = self.get_mimetype(image_path)
            
            if mime_type == 'image/jpeg':
                return image_path
            
            print(f"检测到 {mime_type} 格式，正在转换为JPEG格式...")
            
            with Image.open(image_path) as img:
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                jpeg_path = os.path.splitext(image_path)[0] + '_converted.jpg'
                img.save(jpeg_path, 'JPEG', quality=FILE_CONFIG["jpeg_quality"], optimize=True)
                print(f"图片已转换并保存为: {jpeg_path}")
                
                return jpeg_path
                
        except Exception as e:
            print(f"图片格式转换失败: {e}")
            return image_path

    def encode_image(self, image_path):
        """将图片编码为base64格式"""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        
        processed_image_path = self.convert_to_jpeg_if_needed(image_path)
        
        file_size = os.path.getsize(processed_image_path)
        max_size = FILE_CONFIG["max_image_size_mb"] * 1024 * 1024
        if file_size > max_size:
            raise ValueError(f"图片大小超出限制({FILE_CONFIG['max_image_size_mb']}MB): {file_size / 1024 / 1024:.2f}MB")
        
        mime_type = self.get_mimetype(processed_image_path)
        
        with open(processed_image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            data_uri = f"data:{mime_type};base64,{encoded_string}"
            return data_uri
    
    def validate_duration(self, audio_duration: float) -> int:
        """验证并调整视频时长，确保是5-10之间的整数且比音频长"""
        # 向上取整确保视频比音频长
        duration = math.ceil(audio_duration)
        
        # 确保在5-10秒范围内
        duration = max(5, min(duration, 10))
        
        # 如果向上取整后的时长仍然小于等于音频时长，则至少增加1秒
        if duration <= audio_duration:
            duration = min(math.ceil(audio_duration) + 1, 10)
        
        # print(f"原始音频时长: {audio_duration:.2f}秒，调整后视频时长: {duration}秒")
        return duration
    
    def generate_video(self, original_prompt: str, audio_duration: float, 
                      image_paths: List[str] = None, filename: Optional[str] = None,
                      resolution: str = None, ratio: str = None) -> str:
        """
        扩写提示词并生成视频
        
        Args:
            original_prompt: 原始提示词
            audio_duration: 音频时长（用于确定视频时长）
            image_paths: 可选的参考图片路径列表
            filename: 可选的文件名（不含扩展名）
            resolution: 视频分辨率
            ratio: 视频比例
            
        Returns:
            str: 生成的视频文件路径
        """
        print("开始生成视频...")
        
        # 步骤1: 验证并调整时长
        duration = self.validate_duration(audio_duration)
        
        # 步骤2: 优化提示词
        optimized_prompt = self.optimize_prompt_for_video(original_prompt, duration)
        
        # 添加写实风格描述
        realistic_prompt = f"documentary style, realistic cinematography, professional videography, high quality, {optimized_prompt}"
        
        # 生成文件名
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"video_{timestamp}"
        
        # 使用配置的默认值或传入的参数
        video_resolution = resolution or VIDEO_CONFIG["default_resolution"]
        video_ratio = ratio or VIDEO_CONFIG["default_ratio"]
        
        # 验证比例是否支持
        if video_ratio not in VIDEO_CONFIG["supported_ratios"]:
            print(f"警告: 不支持的视频比例 {video_ratio}，使用默认比例 {VIDEO_CONFIG['default_ratio']}")
            video_ratio = VIDEO_CONFIG["default_ratio"]
        
        # 步骤3: 准备请求内容
        content = []
        
        # 如果有图片路径，添加图片内容
        if image_paths and len(image_paths) > 0:
            image_path = image_paths[0]
            try:
                image_data_uri = self.encode_image(image_path)
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": image_data_uri
                    }
                })
                print(f"已将图片 {image_path} 添加到视频生成请求")
            except Exception as e:
                print(f"图片编码失败: {e}，将继续使用纯文本生成视频")
        
        # 添加文本内容
        content.append({
            "type": "text",
            "text": realistic_prompt
        })
        
        # 步骤4: 发送视频生成请求
        data = {
            "model": self.config["video_model"],
            "content": content,
            "resolution": video_resolution,
            "ratio": video_ratio,
            "duration": duration
        }
        
        print(f"视频生成参数: resolution={video_resolution}, ratio={video_ratio}, duration={duration}")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config['api_key']}"
        }
        
        base_url = f"{self.config['base_url']}/contents/generations/tasks"
        
        print("正在发送视频生成请求...")
        response = requests.post(base_url, headers=headers, json=data)
        response.raise_for_status()
        
        response_data = response.json()
        task_id = response_data.get("id")
        if not task_id:
            raise ValueError("无法获取任务ID，请检查API响应")
        
        print(f"视频生成任务已创建，任务ID: {task_id}")
        
        # 步骤5: 等待任务完成并下载视频
        video_path = self.wait_and_download_video(task_id, filename)
        return video_path
    
    def wait_and_download_video(self, task_id: str, filename: str) -> str:
        """等待视频生成完成并下载"""
        max_wait_time = VIDEO_CONFIG["max_wait_time"]
        check_interval = VIDEO_CONFIG["check_interval"]
        waited_time = 0
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config['api_key']}"
        }
        
        base_url = f"{self.config['base_url']}/contents/generations/tasks"
        
        last_status = None
        while waited_time < max_wait_time:
            try:
                url = f"{base_url}/{task_id}"
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                status_data = response.json()
                
                status = status_data.get("status")
                
                if status != last_status:
                    print(f"任务状态变更: {status}")
                    last_status = status
                else:
                    print(f"任务状态: {status}")
                
                if status == "succeeded":
                    video_url = None
                    
                    if "content" in status_data and "video_url" in status_data["content"]:
                        video_url = status_data["content"]["video_url"]
                    else:
                        results = status_data.get("results", [])
                        if results and len(results) > 0:
                            video_url = results[0].get("url")
                    
                    if video_url:
                        return self.download_video(video_url, filename)
                    else:
                        print("错误: 无法从结果中获取视频URL")
                        print(f"响应内容: {json.dumps(status_data, indent=2)}")
                        raise Exception("无法获取视频URL")
                
                elif status == "failed":
                    error = status_data.get("failure_reason", "未知错误")
                    raise Exception(f"任务失败: {error}")
                
                elif status in ["pending", "queued", "running"]:
                    time.sleep(check_interval)
                    waited_time += check_interval
                    continue
                
                else:
                    print(f"未知任务状态: {status}")
                    time.sleep(check_interval)
                    waited_time += check_interval
                    
            except Exception as e:
                print(f"查询任务状态时出错: {str(e)}")
                time.sleep(check_interval)
                waited_time += check_interval
        
        raise Exception("视频生成超时")
    
    def download_video(self, video_url: str, filename: str) -> str:
        """下载视频文件"""
        video_path = os.path.join(self.video_dir, f"{filename}.mp4")
        
        print(f"正在下载视频到: {video_path}")
        response = requests.get(video_url, stream=True)
        response.raise_for_status()
        
        file_size = int(response.headers.get('content-length', 0))
        
        with open(video_path, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    percent = int(100 * downloaded / file_size) if file_size > 0 else 0
                    print(f"\r下载进度: {percent}% [{downloaded}/{file_size} bytes]", end="")
        
        print(f"\n视频下载完成: {video_path}")
        return video_path

# ================================
# 整合类（可选）
# ================================

class MultimodalNewsBot:
    """多模态新闻播报机器人整合类"""
    
    def __init__(self, custom_config=None):
        self.tts_module = TTSModule(custom_config)
        self.image_module = ImageGenerationModule(custom_config)
        self.video_module = VideoGenerationModule(custom_config)
    
    def generate_news_report(self, news_prompt: str, image_ratio: str = None, video_ratio: str = None,
                           image_size: str = None, video_resolution: str = None,
                           guidance_scale: float = None, seed: int = None) -> dict:
        """生成完整的多模态新闻播报"""
        print(f"开始生成多模态新闻播报...")
        print(f"原始新闻内容: {news_prompt}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # 步骤1: 生成语音
            voice_path, audio_duration = self.tts_module.generate_voice(
                news_prompt, f"news_voice_{timestamp}"
            )
            
            # 步骤2: 生成图像
            image_paths = self.image_module.generate_image(
                news_prompt, f"news_image_{timestamp}",
                size=image_size, ratio=image_ratio,
                guidance_scale=guidance_scale, seed=seed
            )
            
            # 步骤3: 生成视频
            video_path = self.video_module.generate_video(
                news_prompt, audio_duration, image_paths, f"news_video_{timestamp}",
                resolution=video_resolution, ratio=video_ratio
            )
            
            result = {
                "timestamp": timestamp,
                "original_prompt": news_prompt,
                "voice_path": voice_path,
                "image_paths": image_paths,
                "video_path": video_path,
                "audio_duration": audio_duration,
                "status": "success"
            }
            
            print("=" * 50)
            print("多模态新闻播报生成完成！")
            print(f"语音文件: {voice_path}")
            print(f"图像文件: {image_paths}")
            print(f"视频文件: {video_path}")
            print("=" * 50)
            
            return result
            
        except Exception as e:
            error_result = {
                "timestamp": timestamp,
                "original_prompt": news_prompt,
                "status": "failed",
                "error": str(e)
            }
            print(f"生成过程中出现错误: {e}")
            return error_result

# ================================
# 使用示例
# ================================

if __name__ == "__main__":
    # 示例1: 使用单独的模块
    print("=== 使用单独模块 ===")
    
    # TTS模块
    tts = TTSModule()
    voice_path, duration = tts.generate_voice("这是一个测试文本")
    
    # 图片生成模块
    image_gen = ImageGenerationModule()
    image_paths = image_gen.generate_image("AI技术发展", ratio="16:9")
    
    # 视频生成模块
    video_gen = VideoGenerationModule()
    video_path = video_gen.generate_video("AI技术发展", duration, image_paths)
    
    print("\n=== 使用整合类 ===")
    
    # 整合使用
    news_bot = MultimodalNewsBot()
    
    ai_news_prompt = """
    与一两年前相比，谷歌的AI进展显著加快，Gemini 2.5系列模型已能响应文本、图像、音频和视频。
    这一系列更新展示了谷歌在构建全方位AI生态系统方面的战略布局和行业领先优势。
    """
    
    result = news_bot.generate_news_report(
        ai_news_prompt,
        image_ratio="16:9",
        video_ratio="16:9",
        video_resolution="720p",
        guidance_scale=2.5,
        seed=12
    )
    
    print("\n生成结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))