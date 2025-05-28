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

# 图片生成配置 - 根据官方文档
IMAGE_CONFIG = {
    # 根据文档，支持的尺寸
    "default_size": "1280x720",  # 默认16:9
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
    "response_format": "url",  # 或 "b64_json"
    "default_guidance_scale": 2.5,
    "default_seed": -1  # -1表示随机
}

# 视频生成配置 - 根据官方文档
VIDEO_CONFIG = {
    "default_resolution": "720p",  # 480p, 720p
    "default_ratio": "16:9",       # 支持的比例：16:9, 4:3, 1:1, 3:4, 9:16, 21:9, 9:21
    "supported_ratios": ["16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "9:21"],
    "min_duration": 5,
    "max_duration": 30,
    "default_duration": 5,
    "max_wait_time": 300,
    "check_interval": 10
}

# 更加写实的提示词模板配置
PROMPT_TEMPLATES = {
    "image_generation": """作为专业的摄影师和视觉艺术总监，请将以下AI新闻内容转换为极其真实的摄影场景描述。并限制描述的长度，避免超过200字。

要求：
1. 采用纪实摄影风格，画面真实自然，具有新闻摄影质感
2. 描述具体的现实场景：现代化办公环境、科技公司内部、数据中心、研发实验室等
3. 包含真实的光影效果：自然光、室内照明、屏幕光源反射等
4. 添加细节元素：现代化设备、显示屏、工作人员背影、科技设备细节
5. 色彩真实自然：冷暖色调平衡，符合现代办公环境的色彩搭配
6. 避免夸张特效，追求专业新闻摄影的质感
7. 场景应该像真实拍摄的新闻照片一样可信
8.减少对显示器以及其他带有文字的描述，注重场景，因为该模型对文字描述不敏感

新闻内容：{news_content}

请用专业摄影术语描述一个真实可拍摄的场景，仿佛是为新闻报道拍摄的照片：""",

    "video_generation": """作为专业的纪录片导演，请将以下AI新闻内容转换为真实的视频拍摄场景描述。并限制描述的长度，避免超过200字。

要求：
1. 时长：{duration}秒的真实纪录片风格画面
2. 拍摄风格：类似BBC或CNN新闻纪录片的真实感
3. 场景描述：现代化办公室、科技公司、研发中心等真实环境
4. 镜头运动：缓慢推拉、平移，模拟专业摄像师操作
5. 光影效果：自然光线变化，真实的室内照明环境
6. 细节展现：键盘敲击、屏幕内容变化、人员走动等真实细节
7. 色彩风格：真实自然的色调，符合现代办公环境
8. 避免特效和动画，追求纪录片的真实质感
9.减少对显示器以及其他带有文字的描述，注重场景，因为该模型对文字描述不敏感

新闻内容：{news_content}

请描述一个可以真实拍摄的{duration}秒纪录片场景："""
}

# ================================
# 工具类定义
# ================================

class BytedanceTTS:
    def __init__(self, url=None, voice_type=None):
        self.url = url or API_CONFIG["tts_url"]
        self.voice_type = voice_type or API_CONFIG["voice_type"]
        self.headers = {"Content-Type": "application/json"}
        
    def generate(self, text, output_file=None):
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(OUTPUT_CONFIG["base_dir"], "tts_output")
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"tts_{timestamp}.wav")
        
        data = {
            "text": text,
            "voice_type": self.voice_type
        }
        
        response = requests.post(self.url, headers=self.headers, json=data)
        
        if response.status_code == 200:
            with open(output_file, "wb") as f:
                f.write(response.content)
            print(f"音频已保存至 {output_file}")
            return output_file
        else:
            error_msg = f"请求失败，状态码: {response.status_code}, 错误信息: {response.text}"
            print(error_msg)
            raise Exception(error_msg)


class ArkImageGenerator:
    def __init__(self, api_key=None, base_url=None, model=None):
        api_key = api_key or API_CONFIG["api_key"]
        base_url = base_url or API_CONFIG["base_url"]
        self.model = model or API_CONFIG["image_model"]
        
        self.client = Ark(
            base_url=base_url,
            api_key=api_key,
        )
    
    def generate(self, prompt: str, output_dir: str = None, filename: Optional[str] = None, 
                 size: str = None, response_format: str = None, 
                 guidance_scale: float = None, seed: int = None) -> List[str]:
        if output_dir is None:
            output_dir = os.path.join(OUTPUT_CONFIG["base_dir"], OUTPUT_CONFIG["image_dir"])
        
        os.makedirs(output_dir, exist_ok=True)
        
        # 构建图片生成参数 - 严格按照官方文档
        generation_params = {
            "model": self.model,
            "prompt": prompt,
        }
        
        # 添加size参数
        if size:
            generation_params["size"] = size
        else:
            generation_params["size"] = IMAGE_CONFIG["default_size"]
        
        # 添加response_format参数
        if response_format:
            generation_params["response_format"] = response_format
        else:
            generation_params["response_format"] = IMAGE_CONFIG["response_format"]
        
        # 添加guidance_scale参数
        if guidance_scale is not None:
            generation_params["guidance_scale"] = guidance_scale
        else:
            generation_params["guidance_scale"] = IMAGE_CONFIG["default_guidance_scale"]
        
        # 添加seed参数
        if seed is not None:
            generation_params["seed"] = seed
        else:
            generation_params["seed"] = IMAGE_CONFIG["default_seed"]
        
        print(f"图片生成参数: {generation_params}")
        
        response = self.client.images.generate(**generation_params)
        
        saved_paths = []
        
        for i, image_data in enumerate(response.data):
            image_url = image_data.url
            
            image_response = requests.get(image_url)
            if image_response.status_code != 200:
                print(f"下载图像失败: {image_response.status_code}")
                continue
            
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if len(response.data) > 1:
                    file_path = os.path.join(output_dir, f"image_{timestamp}_{i}.png")
                else:
                    file_path = os.path.join(output_dir, f"image_{timestamp}.png")
            else:
                if len(response.data) > 1:
                    file_path = os.path.join(output_dir, f"{filename}_{i}.png")
                else:
                    file_path = os.path.join(output_dir, f"{filename}.png")
            
            with open(file_path, 'wb') as f:
                f.write(image_response.content)
            
            print(f"图像已保存至: {file_path}")
            saved_paths.append(file_path)
        
        return saved_paths


# ================================
# 主要业务类
# ================================

class MultimodalNewsBot:
    def __init__(self, custom_config=None):
        """初始化多模态新闻播报机器人"""
        # 允许自定义配置覆盖默认配置
        if custom_config:
            self._update_config(custom_config)
        
        # 初始化各个组件
        self.tts = BytedanceTTS()
        self.image_generator = ArkImageGenerator()
        self.video_client = Ark(
            base_url=API_CONFIG["base_url"],
            api_key=API_CONFIG["api_key"],
        )
        
        # 初始化提示词优化模型
        self.llm = ChatOpenAI(
            temperature=0.0,
            model=API_CONFIG["llm_model"],
            openai_api_key=API_CONFIG["api_key"],
            openai_api_base=API_CONFIG["base_url"]
        )
        
        # 创建输出目录
        self._setup_directories()
    
    def _update_config(self, custom_config):
        """更新配置参数"""
        global API_CONFIG, OUTPUT_CONFIG, FILE_CONFIG, IMAGE_CONFIG, VIDEO_CONFIG, PROMPT_TEMPLATES
        
        for config_type, config_dict in custom_config.items():
            if config_type == "api":
                API_CONFIG.update(config_dict)
            elif config_type == "output":
                OUTPUT_CONFIG.update(config_dict)
            elif config_type == "file":
                FILE_CONFIG.update(config_dict)
            elif config_type == "image":
                IMAGE_CONFIG.update(config_dict)
            elif config_type == "video":
                VIDEO_CONFIG.update(config_dict)
            elif config_type == "prompts":
                PROMPT_TEMPLATES.update(config_dict)
    
    def _setup_directories(self):
        """设置输出目录"""
        self.base_output_dir = OUTPUT_CONFIG["base_dir"]
        self.voice_dir = os.path.join(self.base_output_dir, OUTPUT_CONFIG["voice_dir"])
        self.image_dir = os.path.join(self.base_output_dir, OUTPUT_CONFIG["image_dir"])
        self.video_dir = os.path.join(self.base_output_dir, OUTPUT_CONFIG["video_dir"])
        
        for dir_path in [self.voice_dir, self.image_dir, self.video_dir]:
            os.makedirs(dir_path, exist_ok=True)
    
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
            
            # 如果已经是JPEG格式，直接返回
            if mime_type == 'image/jpeg':
                return image_path
            
            # 转换为JPEG格式
            print(f"检测到 {mime_type} 格式，正在转换为JPEG格式...")
            
            # 打开图片
            with Image.open(image_path) as img:
                # 如果图片有透明通道，转换为RGB
                if img.mode in ('RGBA', 'LA', 'P'):
                    # 创建白色背景
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 生成新的文件路径
                jpeg_path = os.path.splitext(image_path)[0] + '_converted.jpg'
                
                # 保存为JPEG格式
                img.save(jpeg_path, 'JPEG', quality=FILE_CONFIG["jpeg_quality"], optimize=True)
                print(f"图片已转换并保存为: {jpeg_path}")
                
                return jpeg_path
                
        except Exception as e:
            print(f"图片格式转换失败: {e}")
            return image_path  # 转换失败时返回原路径

    def encode_image(self, image_path):
        """将图片编码为base64格式"""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        
        # 首先尝试转换图片格式
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
    
    def optimize_prompt_for_image(self, original_prompt: str) -> str:
        """优化原始提示词用于图像生成"""
        image_prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATES["image_generation"])
        messages = image_prompt_template.format_messages(news_content=original_prompt)
        response = self.llm.invoke(messages)
        return response.content.strip()
    
    def optimize_prompt_for_video(self, original_prompt: str, audio_duration: float) -> str:
        """优化原始提示词用于视频生成"""
        # 确保时长在合理范围内
        duration = max(VIDEO_CONFIG["min_duration"], 
                      min(int(audio_duration), VIDEO_CONFIG["max_duration"]))
        
        video_prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATES["video_generation"])
        messages = video_prompt_template.format_messages(
            news_content=original_prompt,
            duration=duration
        )
        response = self.llm.invoke(messages)
        return response.content.strip()
    
    def get_audio_duration(self, audio_file_path: str) -> float:
        """获取音频文件时长"""
        try:
            duration = librosa.get_duration(filename=audio_file_path)
            return duration
        except Exception as e:
            print(f"获取音频时长失败: {e}")
            return VIDEO_CONFIG["default_duration"]  # 默认时长
    
    def generate_voice(self, text: str, timestamp: str) -> str:
        """生成语音文件"""
        print("步骤 1: 生成语音文件...")
        output_file = os.path.join(self.voice_dir, f"news_voice_{timestamp}.wav")
        voice_path = self.tts.generate(text, output_file=output_file)
        print(f"语音文件已生成: {voice_path}")
        return voice_path
    
    def generate_image(self, original_prompt: str, timestamp: str, 
                      size: str = None, ratio: str = None, 
                      guidance_scale: float = None, seed: int = None) -> List[str]:
        """生成图像文件"""
        print("步骤 2: 优化提示词并生成图像...")
        optimized_prompt = self.optimize_prompt_for_image(original_prompt)
        
        # 添加写实风格描述
        realistic_prompt = f"photorealistic, documentary style, professional photography, high quality, detailed, {optimized_prompt}"
        print(f"图像提示词: {realistic_prompt}")
        
        filename = f"news_image_{timestamp}"
        
        # 确定图片尺寸
        if size:
            img_size = size
        elif ratio and ratio in IMAGE_CONFIG["supported_sizes"]:
            img_size = IMAGE_CONFIG["supported_sizes"][ratio]
        else:
            img_size = IMAGE_CONFIG["default_size"]
        
        image_paths = self.image_generator.generate(
            prompt=realistic_prompt,
            output_dir=self.image_dir,
            filename=filename,
            size=img_size,
            response_format=IMAGE_CONFIG["response_format"],
            guidance_scale=guidance_scale or IMAGE_CONFIG["default_guidance_scale"],
            seed=seed if seed is not None else IMAGE_CONFIG["default_seed"]
        )
        print(f"图像文件已生成: {image_paths}")
        return image_paths
    
    def generate_video(self, original_prompt: str, audio_duration: float, timestamp: str, 
                    image_paths: List[str] = None, resolution: str = None, ratio: str = None) -> str:
        """生成视频文件"""
        print("步骤 3: 优化提示词并生成视频...")
        optimized_prompt = self.optimize_prompt_for_video(original_prompt, audio_duration)
        
        # 添加写实风格描述
        realistic_prompt = f"documentary style, realistic cinematography, professional videography, high quality, {optimized_prompt}"
        print(f"视频提示词: {realistic_prompt}")
        
        # 限制时长在合理范围内
        duration = max(VIDEO_CONFIG["min_duration"], 
                    min(int(audio_duration), VIDEO_CONFIG["max_duration"]))
        
        # 使用配置的默认值或传入的参数
        video_resolution = resolution or VIDEO_CONFIG["default_resolution"]
        video_ratio = ratio or VIDEO_CONFIG["default_ratio"]
        
        # 验证比例是否支持
        if video_ratio not in VIDEO_CONFIG["supported_ratios"]:
            print(f"警告: 不支持的视频比例 {video_ratio}，使用默认比例 {VIDEO_CONFIG['default_ratio']}")
            video_ratio = VIDEO_CONFIG["default_ratio"]
        
        # 准备请求内容 - 修改这里的格式
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
        
        # 发送HTTP请求 - 修改这里的参数格式
        data = {
            "model": API_CONFIG["video_model"],
            "content": content,
            "resolution": video_resolution,
            "ratio": video_ratio,
            "duration": duration
        }
        
        print(f"完整视频请求参数: resolution={video_resolution}, ratio={video_ratio}, duration={duration}")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_CONFIG['api_key']}"
        }
        
        base_url = f"{API_CONFIG['base_url']}/contents/generations/tasks"
        
        print("正在发送视频生成请求...")
        response = requests.post(base_url, headers=headers, json=data)
        response.raise_for_status()
        
        response_data = response.json()
        task_id = response_data.get("id")
        if not task_id:
            raise ValueError("无法获取任务ID，请检查API响应")
        
        print(f"视频生成任务已创建，任务ID: {task_id}")
        print(f"请求的视频参数: 分辨率={video_resolution}, 比例={video_ratio}, 时长={duration}秒")
        
        # 等待任务完成并下载视频
        video_path = self.wait_and_download_video_http(task_id, timestamp)
        return video_path  

    def wait_and_download_video_http(self, task_id: str, timestamp: str) -> str:
        """使用HTTP请求等待视频生成完成并下载"""
        max_wait_time = VIDEO_CONFIG["max_wait_time"]
        check_interval = VIDEO_CONFIG["check_interval"]
        waited_time = 0
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_CONFIG['api_key']}"
        }
        
        base_url = f"{API_CONFIG['base_url']}/contents/generations/tasks"
        
        last_status = None
        while waited_time < max_wait_time:
            try:
                url = f"{base_url}/{task_id}"
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                status_data = response.json()
                
                status = status_data.get("status")
                
                # 仅当状态变化时才打印
                if status != last_status:
                    print(f"任务状态变更: {status}")
                    last_status = status
                else:
                    print(f"任务状态: {status}")
                
                if status == "succeeded":
                    # 任务成功完成
                    video_url = None
                    
                    if "content" in status_data and "video_url" in status_data["content"]:
                        video_url = status_data["content"]["video_url"]
                    else:
                        # 尝试旧的结果格式
                        results = status_data.get("results", [])
                        if results and len(results) > 0:
                            video_url = results[0].get("url")
                    
                    if video_url:
                        return self.download_video(video_url, timestamp)
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
                    print(f"响应内容: {json.dumps(status_data, indent=2)}")
                    time.sleep(check_interval)
                    waited_time += check_interval
                    
            except Exception as e:
                print(f"查询任务状态时出错: {str(e)}")
                time.sleep(check_interval)
                waited_time += check_interval
        
        raise Exception("视频生成超时")
        
    def download_video(self, video_url: str, timestamp: str) -> str:
        """下载视频文件"""
        video_path = os.path.join(self.video_dir, f"news_video_{timestamp}.mp4")
        
        print(f"正在下载视频到: {video_path}")
        response = requests.get(video_url, stream=True)
        response.raise_for_status()
        
        file_size = int(response.headers.get('content-length', 0))
        
        # 下载并显示进度
        with open(video_path, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    percent = int(100 * downloaded / file_size) if file_size > 0 else 0
                    print(f"\r下载进度: {percent}% [{downloaded}/{file_size} bytes]", end="")
        
        print(f"\n视频下载完成: {video_path}")
        return video_path
    
    def generate_news_report(self, news_prompt: str, image_ratio: str = None, video_ratio: str = None,
                           image_size: str = None, video_resolution: str = None,
                           guidance_scale: float = None, seed: int = None) -> dict:
        """生成完整的多模态新闻播报"""
        print(f"开始生成多模态新闻播报...")
        print(f"原始新闻内容: {news_prompt}")
        
        # 生成时间戳用于文件命名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # 步骤1: 生成语音
            voice_path = self.generate_voice(news_prompt, timestamp)
            
            # 获取音频时长
            audio_duration = self.get_audio_duration(voice_path)
            print(f"音频时长: {audio_duration:.2f}秒")
            
            # 步骤2: 生成图像
            image_paths = self.generate_image(
                news_prompt, timestamp, 
                size=image_size, 
                ratio=image_ratio,
                guidance_scale=guidance_scale,
                seed=seed
            )
            
            # 步骤3: 生成视频 - 传递图片路径和视频参数
            video_path = self.generate_video(
                news_prompt, audio_duration, timestamp, 
                image_paths=image_paths,
                resolution=video_resolution,
                ratio=video_ratio
            )
            
            # 确定实际使用的参数
            actual_image_size = image_size or (IMAGE_CONFIG["supported_sizes"].get(image_ratio) if image_ratio else IMAGE_CONFIG["default_size"])
            actual_video_ratio = video_ratio or VIDEO_CONFIG["default_ratio"]
            actual_video_resolution = video_resolution or VIDEO_CONFIG["default_resolution"]
            
            result = {
                "timestamp": timestamp,
                "original_prompt": news_prompt,
                "voice_path": voice_path,
                "image_paths": image_paths,
                "video_path": video_path,
                "audio_duration": audio_duration,
                "parameters": {
                    "image_size": actual_image_size,
                    "image_ratio": image_ratio or "16:9",
                    "video_ratio": actual_video_ratio,
                    "video_resolution": actual_video_resolution,
                    "guidance_scale": guidance_scale or IMAGE_CONFIG["default_guidance_scale"],
                    "seed": seed if seed is not None else IMAGE_CONFIG["default_seed"]
                },
                "status": "success"
            }
            
            print("=" * 50)
            print("多模态新闻播报生成完成！")
            print(f"语音文件: {voice_path}")
            print(f"图像文件: {image_paths}")
            print(f"视频文件: {video_path}")
            print(f"生成参数: {result['parameters']}")
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
    # 创建多模态新闻播报机器人
    news_bot = MultimodalNewsBot()
    
    # AI新闻示例
    ai_news_prompt = """
    与一两年前相比，谷歌的AI进展显著加快，Gemini 2.5系列模型已能响应文本、图像、音频和视频。
    这一系列更新展示了谷歌在构建全方位AI生态系统方面的战略布局和行业领先优势。
    新发布的Gemini 2.5 Flash模型在性能上有了显著提升，支持更复杂的多模态交互。
    """
    
    # 生成完整的多模态新闻播报，使用官方文档支持的参数
    result = news_bot.generate_news_report(
        ai_news_prompt,
        image_ratio="16:9",           # 使用支持的比例
        video_ratio="16:9",           # 使用支持的比例  
        video_resolution="720p",      # 使用支持的分辨率
        guidance_scale=2.5,           # 使用支持的引导强度
        seed=12                       # 使用固定种子确保可重现
    )
    
    # 打印结果
    print("\n生成结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))