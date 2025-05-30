import os
import requests
import json
import time
import random
import subprocess
import base64
import mimetypes
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
from PIL import Image
import math
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

class VideoGenerator:
    """视频生成器，负责生成和处理视频"""
    
    def __init__(self, output_dir: str = "output/videos", api_config: Dict[str, Any] = None):
        """初始化视频生成器
        
        Args:
            output_dir: 视频输出目录
            api_config: API配置
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # 默认API配置
        self.config = {
            "api_key": "YOUR_API_KEY",
            "base_url": "https://api.deepseek.com/v1",
            "llm_model": "deepseek-chat",
            "image_model": "deepseek-image",
            "video_model": "deepseek-video"
        }
        
        # 视频配置
        self.video_config = {
            "default_resolution": "720p",
            "default_ratio": "16:9",
            "supported_ratios": ["16:9", "1:1", "9:16"],
            "max_wait_time": 300,  # 最大等待时间（秒）
            "check_interval": 5    # 检查间隔（秒）
        }
        
        # 图片配置
        self.image_config = {
            "default_size": "1024x1024",
            "supported_sizes": {
                "16:9": "1024x576",
                "1:1": "1024x1024",
                "9:16": "576x1024"
            },
            "response_format": "url",
            "default_guidance_scale": 7.5,
            "default_seed": None
        }
        
        # 文件配置
        self.file_config = {
            "max_image_size_mb": 5,
            "jpeg_quality": 90,
            "supported_image_formats": {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp"
            }
        }
        
        if api_config:
            self.config.update(api_config)
        
        # 初始化LLM用于提示词优化
        self.llm = ChatOpenAI(
            temperature=0.0,
            model=self.config["llm_model"],
            openai_api_key=self.config["api_key"],
            openai_api_base=self.config["base_url"]
        )
    
    def optimize_prompt_for_image(self, original_prompt: str) -> str:
        """优化原始提示词用于图像生成
        
        Args:
            original_prompt: 原始提示词
            
        Returns:
            str: 优化后的提示词
        """
        print("正在优化图片生成提示词...")
        
        image_prompt_template = ChatPromptTemplate.from_template(
            """你是一个专业的AI图像提示词优化专家。请将以下新闻内容转化为详细的图像生成提示词，使其能够生成高质量的新闻配图。
            提示词应该包含场景描述、风格、氛围、光线等要素，但不要包含任何不适合在新闻中展示的内容。
            只返回优化后的提示词，不要有任何解释或其他内容。
            
            新闻内容：
            {news_content}
            """
        )
        
        messages = image_prompt_template.format_messages(news_content=original_prompt)
        response = self.llm.invoke(messages)
        
        optimized_prompt = response.content.strip()
        print(f"优化后的图片提示词: {optimized_prompt}")
        
        return optimized_prompt
    
    def optimize_prompt_for_video(self, original_prompt: str, duration: int) -> str:
        """优化原始提示词用于视频生成
        
        Args:
            original_prompt: 原始提示词
            duration: 视频时长（秒）
            
        Returns:
            str: 优化后的提示词
        """
        print("正在优化视频生成提示词...")
        
        video_prompt_template = ChatPromptTemplate.from_template(
            """你是一个专业的AI视频提示词优化专家。请将以下新闻内容转化为详细的视频生成提示词，使其能够生成高质量的新闻视频片段。
            提示词应该包含场景描述、动作、转场、风格、氛围、光线等要素，但不要包含任何不适合在新闻中展示的内容。
            视频时长为{duration}秒，请确保提示词适合这个时长。
            只返回优化后的提示词，不要有任何解释或其他内容。
            
            新闻内容：
            {news_content}
            """
        )
        
        messages = video_prompt_template.format_messages(
            news_content=original_prompt,
            duration=duration
        )
        response = self.llm.invoke(messages)
        
        optimized_prompt = response.content.strip()
        print(f"优化后的视频提示词: {optimized_prompt}")
        
        return optimized_prompt
    
    def generate_image(self, original_prompt: str, filename: Optional[str] = None,
                      size: str = None, ratio: str = None, 
                      guidance_scale: float = None, seed: int = None) -> List[str]:
        """扩写提示词并生成图片
        
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
        elif ratio and ratio in self.image_config["supported_sizes"]:
            img_size = self.image_config["supported_sizes"][ratio]
        else:
            img_size = self.image_config["default_size"]
        
        # 步骤2: 生成图片
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config['api_key']}"
        }
        
        data = {
            "model": self.config["image_model"],
            "prompt": realistic_prompt,
            "size": img_size,
            "response_format": self.image_config["response_format"],
            "guidance_scale": guidance_scale or self.image_config["default_guidance_scale"],
            "seed": seed if seed is not None else random.randint(1, 10000)
        }
        
        print(f"图片生成参数: {data}")
        
        try:
            response = requests.post(
                f"{self.config['base_url']}/images/generations",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            response_data = response.json()
            
            saved_paths = []
            
            for i, image_data in enumerate(response_data.get("data", [])):
                image_url = image_data.get("url")
                if not image_url:
                    continue
                
                image_response = requests.get(image_url)
                if image_response.status_code != 200:
                    print(f"下载图像失败: {image_response.status_code}")
                    continue
                
                if len(response_data.get("data", [])) > 1:
                    file_path = os.path.join(self.output_dir, f"{filename}_{i}.png")
                else:
                    file_path = os.path.join(self.output_dir, f"{filename}.png")
                
                with open(file_path, 'wb') as f:
                    f.write(image_response.content)
                
                print(f"图像已保存: {file_path}")
                saved_paths.append(file_path)
            
            return saved_paths
            
        except Exception as e:
            print(f"图片生成失败: {e}")
            return []
    
    def get_mimetype(self, file_path):
        """获取文件的MIME类型"""
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type or not mime_type.startswith('image/'):
            ext = Path(file_path).suffix.lower()
            mime_type = self.file_config["supported_image_formats"].get(ext)
        
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
                img.save(jpeg_path, 'JPEG', quality=self.file_config["jpeg_quality"], optimize=True)
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
        max_size = self.file_config["max_image_size_mb"] * 1024 * 1024
        
        if file_size > max_size:
            raise ValueError(f"图片大小超出限制({self.file_config['max_image_size_mb']}MB): {file_size / 1024 / 1024:.2f}MB")
        
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
        
        return duration
    
    def generate_video(self, original_prompt: str, audio_duration: float, 
                      image_paths: List[str] = None, filename: Optional[str] = None,
                      resolution: str = None, ratio: str = None) -> str:
        """扩写提示词并生成视频
        
        Args:
            original_prompt: 原始提示词
            audio_duration: 音频时长（用于确定视频时长）
            image_paths: 可选的参考图片路径列表
            filename: 可选的文件名
            resolution: 视频分辨率
            ratio: 视频比例
            
        Returns:
            str: 生成的视频文件路径
        """
        print("开始生成视频...")
        
        # 步骤1: 验证并调整视频时长
        duration = self.validate_duration(audio_duration)
        print(f"视频时长设置为: {duration}秒")
        
        # 步骤2: 优化提示词
        optimized_prompt = self.optimize_prompt_for_video(original_prompt, duration)
        
        # 添加写实风格描述
        realistic_prompt = f"photorealistic, documentary style, professional video, high quality, detailed, {optimized_prompt}"
        
        # 生成文件名
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"video_{timestamp}"
        
        # 确定视频分辨率和比例
        video_resolution = resolution or self.video_config["default_resolution"]
        video_ratio = ratio or self.video_config["default_ratio"]
        
        # 步骤3: 准备参考图像（如果有）
        image_data_list = []
        if image_paths and len(image_paths) > 0:
            print(f"处理 {len(image_paths)} 张参考图像...")
            for image_path in image_paths:
                try:
                    image_data = self.encode_image(image_path)
                    image_data_list.append(image_data)
                except Exception as e:
                    print(f"处理参考图像失败: {e}")
        
        # 步骤4: 生成视频
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config['api_key']}"
        }
        
        data = {
            "model": self.config["video_model"],
            "prompt": realistic_prompt,
            "duration": duration,
            "resolution": video_resolution,
            "aspect_ratio": video_ratio
        }
        
        # 添加参考图像（如果有）
        if image_data_list:
            data["reference_images"] = image_data_list
        
        print(f"视频生成参数: {data}")
        
        try:
            # 发送视频生成请求
            response = requests.post(
                f"{self.config['base_url']}/videos/generations",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            response_data = response.json()
            
            # 获取任务ID
            task_id = response_data.get("task_id")
            if not task_id:
                raise ValueError("未能获取视频生成任务ID")
            
            print(f"视频生成任务已提交，任务ID: {task_id}")
            
            # 轮询检查任务状态
            status_url = f"{self.config['base_url']}/videos/generations/{task_id}"
            wait_time = 0
            
            while wait_time < self.video_config["max_wait_time"]:
                time.sleep(self.video_config["check_interval"])
                wait_time += self.video_config["check_interval"]
                
                status_response = requests.get(
                    status_url,
                    headers=headers
                )
                
                if status_response.status_code != 200:
                    print(f"检查任务状态失败: {status_response.status_code}")
                    continue
                
                status_data = status_response.json()
                status = status_data.get("status")
                
                print(f"任务状态: {status} (等待时间: {wait_time}秒)")
                
                if status == "completed":
                    # 获取视频URL并下载
                    video_url = status_data.get("result", {}).get("url")
                    if not video_url:
                        raise ValueError("未能获取视频URL")
                    
                    video_response = requests.get(video_url)
                    if video_response.status_code != 200:
                        raise ValueError(f"下载视频失败: {video_response.status_code}")
                    
                    # 保存视频文件
                    video_path = os.path.join(self.output_dir, f"{filename}.mp4")
                    with open(video_path, 'wb') as f:
                        f.write(video_response.content)
                    
                    print(f"视频已保存: {video_path}")
                    return video_path
                    
                elif status == "failed":
                    error_message = status_data.get("error", {}).get("message", "未知错误")
                    raise ValueError(f"视频生成失败: {error_message}")
            
            raise TimeoutError(f"视频生成超时，已等待 {wait_time} 秒")
            
        except Exception as e:
            print(f"视频生成过程中出错: {e}")
            return ""