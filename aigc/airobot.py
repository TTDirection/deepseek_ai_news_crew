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

class MultimodalNewsBot:
    def __init__(self):
        """初始化多模态新闻播报机器人"""
        # 初始化各个组件
        self.tts = BytedanceTTS()
        self.image_generator = ArkImageGenerator()
        self.video_client = Ark(
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            api_key="5cf8e2f7-8465-4ccc-bf84-e32f05be0fb4",
        )
        
        # 初始化提示词优化模型
        self.llm = ChatOpenAI(
            temperature=0.0,
            model="ep-20250427095319-t4sw8",
            openai_api_key="5cf8e2f7-8465-4ccc-bf84-e32f05be0fb4",
            openai_api_base="https://ark.cn-beijing.volces.com/api/v3"
        )
        
        # 创建输出目录
        self.base_output_dir = "output"
        self.voice_dir = os.path.join(self.base_output_dir, "voice")
        self.image_dir = os.path.join(self.base_output_dir, "image")
        self.video_dir = os.path.join(self.base_output_dir, "video")
        
        for dir_path in [self.voice_dir, self.image_dir, self.video_dir]:
            os.makedirs(dir_path, exist_ok=True)
    
    def get_mimetype(self, file_path):
        """获取文件的MIME类型（参考i2v_2.py方法）"""
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type or not mime_type.startswith('image/'):
            # 如果无法识别，尝试按扩展名判断
            ext = Path(file_path).suffix.lower()
            mime_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.webp': 'image/webp',
                '.bmp': 'image/bmp',
                '.tiff': 'image/tiff',
                '.tif': 'image/tiff',
                '.gif': 'image/gif'
            }
            mime_type = mime_map.get(ext)
        
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
                
                # 保存为JPEG格式，质量设为90
                img.save(jpeg_path, 'JPEG', quality=90, optimize=True)
                print(f"图片已转换并保存为: {jpeg_path}")
                
                return jpeg_path
                
        except Exception as e:
            print(f"图片格式转换失败: {e}")
            return image_path  # 转换失败时返回原路径

    def encode_image(self, image_path):
        """将图片编码为base64格式（参考i2v_2.py方法并增强）"""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        
        # 首先尝试转换图片格式
        processed_image_path = self.convert_to_jpeg_if_needed(image_path)
        
        file_size = os.path.getsize(processed_image_path)
        if file_size > 10 * 1024 * 1024:  # 10MB
            raise ValueError(f"图片大小超出限制(10MB): {file_size / 1024 / 1024:.2f}MB")
        
        mime_type = self.get_mimetype(processed_image_path)
        
        with open(processed_image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            data_uri = f"data:{mime_type};base64,{encoded_string}"
            return data_uri
    
    def optimize_prompt_for_image(self, original_prompt: str) -> str:
        """优化原始提示词用于图像生成"""
        image_prompt_template = ChatPromptTemplate.from_template(
            """作为AI图像生成专家，请将以下AI新闻内容转换为详细的图像生成提示词。
            
            要求：
            1. 描述应该视觉化、具体化
            2. 包含科技感的场景元素
            3. 适合作为新闻播报的背景图像
            4. 风格现代、专业
            5. 避免包含具体的人脸或品牌标识
            
            原始新闻内容：{news_content}
            
            请直接返回优化后的图像生成提示词，不要包含其他解释："""
        )
        
        messages = image_prompt_template.format_messages(news_content=original_prompt)
        response = self.llm.invoke(messages)
        return response.content.strip()
    
    def optimize_prompt_for_video(self, original_prompt: str, audio_duration: float) -> str:
        """优化原始提示词用于视频生成"""
        # 确保时长在合理范围内
        duration = max(5, min(int(audio_duration), 30))
        
        video_prompt_template = ChatPromptTemplate.from_template(
            """作为AI视频生成专家，请将以下AI新闻内容转换为视频生成提示词。

            要求：
            1. 视频时长需要为{duration}秒
            2. 描述动态的科技场景，包含数据流动、光效等元素
            3. 风格现代、专业，适合新闻播报背景
            4. 描述要简洁明了，不超过80字
            5. 避免复杂格式，直接描述视觉内容

            原始新闻内容：{news_content}

            请直接返回视频描述提示词："""
        )
        
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
            return 10.0  # 默认10秒
    
    def generate_voice(self, text: str, timestamp: str) -> str:
        """生成语音文件"""
        print("步骤 1: 生成语音文件...")
        output_file = os.path.join(self.voice_dir, f"news_voice_{timestamp}.wav")
        voice_path = self.tts.generate(text, output_file=output_file)
        print(f"语音文件已生成: {voice_path}")
        return voice_path
    
    def generate_image(self, original_prompt: str, timestamp: str) -> List[str]:
        """生成图像文件"""
        print("步骤 2: 优化提示词并生成图像...")
        optimized_prompt = self.optimize_prompt_for_image(original_prompt)
        print(f"图像提示词: {optimized_prompt}")
        
        filename = f"news_image_{timestamp}"
        image_paths = self.image_generator.generate(
            prompt=optimized_prompt,
            output_dir=self.image_dir,
            filename=filename
        )
        print(f"图像文件已生成: {image_paths}")
        return image_paths
    
    def generate_video(self, original_prompt: str, audio_duration: float, timestamp: str, image_paths: List[str] = None) -> str:
        """生成视频文件 - 使用HTTP请求替代SDK"""
        print("步骤 3: 优化提示词并生成视频...")
        optimized_prompt = self.optimize_prompt_for_video(original_prompt, audio_duration)
        print(f"视频提示词: {optimized_prompt}")
        
        # 限制时长在合理范围内
        duration = max(5, min(int(audio_duration), 30))
        
        # 使用与i2v_2.py相同的参数格式
        video_params = f"--resolution 720p --dur {duration} --camerafixed false"
        video_prompts=f"{video_params} {optimized_prompt} "
        print(f"视频提示词: {video_prompts}")
        # 准备请求内容
        content = [
            {
                "type": "text",
                "text": video_prompts
            }
        ]
        
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
        
        # 使用HTTP请求替代SDK（参考i2v_2.py的方法）
        data = {
            "model": "doubao-seedance-1-0-lite-i2v-250428",
            "content": content
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer 5cf8e2f7-8465-4ccc-bf84-e32f05be0fb4"
        }
        
        base_url = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
        
        print("正在发送视频生成请求...")
        response = requests.post(base_url, headers=headers, json=data)
        response.raise_for_status()
        
        response_data = response.json()
        task_id = response_data.get("id")
        if not task_id:
            raise ValueError("无法获取任务ID，请检查API响应")
        
        print(f"视频生成任务已创建，任务ID: {task_id}")
        print(f"请求的视频时长: {duration}秒")
        
        # 等待任务完成并下载视频
        video_path = self.wait_and_download_video_http(task_id, timestamp)
        return video_path   

    def wait_and_download_video_http(self, task_id: str, timestamp: str) -> str:
        """使用HTTP请求等待视频生成完成并下载（参考i2v_2.py）"""
        max_wait_time = 300
        check_interval = 10
        waited_time = 0
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer 5cf8e2f7-8465-4ccc-bf84-e32f05be0fb4"
        }
        
        base_url = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
        
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
                    # 任务成功完成 - 使用与i2v_2.py相同的解析方式
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
        
    def wait_and_download_video(self, task_id: str, timestamp: str) -> str:
        """等待视频生成完成并下载（参考i2v_2.py的处理方式）"""
        max_wait_time = 300  # 最大等待5分钟
        check_interval = 10  # 每10秒检查一次
        waited_time = 0
        
        while waited_time < max_wait_time:
            try:
                get_result = self.video_client.content_generation.tasks.get(task_id=task_id)
                status = get_result.status
                
                print(f"视频生成状态: {status}")
                
                if status == "succeeded":
                    # 任务完成，尝试多种方式获取视频URL
                    video_url = None
                    
                    # 方式1：尝试从content属性获取
                    if hasattr(get_result, 'content') and get_result.content:
                        if hasattr(get_result.content, 'video_url'):
                            video_url = get_result.content.video_url
                        elif isinstance(get_result.content, dict) and 'video_url' in get_result.content:
                            video_url = get_result.content['video_url']
                    
                    # 方式2：尝试从output属性获取
                    if not video_url and hasattr(get_result, 'output') and get_result.output:
                        if isinstance(get_result.output, list) and len(get_result.output) > 0:
                            if hasattr(get_result.output[0], 'url'):
                                video_url = get_result.output[0].url
                            elif isinstance(get_result.output[0], dict) and 'url' in get_result.output[0]:
                                video_url = get_result.output[0]['url']
                    
                    # 方式3：尝试从results属性获取
                    if not video_url and hasattr(get_result, 'results') and get_result.results:
                        if isinstance(get_result.results, list) and len(get_result.results) > 0:
                            if hasattr(get_result.results[0], 'url'):
                                video_url = get_result.results[0].url
                            elif isinstance(get_result.results[0], dict) and 'url' in get_result.results[0]:
                                video_url = get_result.results[0]['url']
                    
                    # 方式4：直接从对象属性中查找URL
                    if not video_url:
                        # 打印对象的所有属性，帮助调试
                        print("API响应对象的属性:")
                        for attr in dir(get_result):
                            if not attr.startswith('_'):
                                try:
                                    value = getattr(get_result, attr)
                                    print(f"  {attr}: {type(value)} = {value}")
                                    
                                    # 如果是字符串且包含http，可能是URL
                                    if isinstance(value, str) and value.startswith('http'):
                                        video_url = value
                                        break
                                except:
                                    continue
                    
                    if video_url:
                        return self.download_video(video_url, timestamp)
                    else:
                        # 如果仍然找不到URL，将完整响应保存到文件以便调试
                        debug_file = os.path.join(self.video_dir, f"debug_response_{timestamp}.txt")
                        with open(debug_file, 'w', encoding='utf-8') as f:
                            f.write(f"Task ID: {task_id}\n")
                            f.write(f"Status: {status}\n")
                            f.write(f"Full response object: {get_result}\n")
                            f.write(f"Object type: {type(get_result)}\n")
                            f.write("Object attributes:\n")
                            for attr in dir(get_result):
                                if not attr.startswith('_'):
                                    try:
                                        value = getattr(get_result, attr)
                                        f.write(f"  {attr}: {type(value)} = {value}\n")
                                    except:
                                        f.write(f"  {attr}: <unable to access>\n")
                        
                        print(f"调试信息已保存到: {debug_file}")
                        raise Exception("无法从API响应中获取视频URL")
                
                elif status in ["failed", "cancelled"]:
                    # 获取失败原因
                    failure_reason = "未知错误"
                    if hasattr(get_result, 'failure_reason'):
                        failure_reason = get_result.failure_reason
                    elif hasattr(get_result, 'error'):
                        failure_reason = get_result.error
                    
                    raise Exception(f"视频生成失败，状态: {status}，原因: {failure_reason}")
                
                elif status in ["pending", "queued", "running"]:
                    # 任务仍在处理中，继续等待
                    time.sleep(check_interval)
                    waited_time += check_interval
                    continue
                
                else:
                    # 未知状态
                    print(f"未知任务状态: {status}")
                    time.sleep(check_interval)
                    waited_time += check_interval
                    
            except Exception as e:
                print(f"检查视频生成状态时出错: {e}")
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
    
    def generate_news_report(self, news_prompt: str) -> dict:
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
            image_paths = self.generate_image(news_prompt, timestamp)
            
            # 步骤3: 生成视频 - 传递图片路径
            video_path = self.generate_video(news_prompt, audio_duration, timestamp, image_paths)
            
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


# 从您提供的代码中导入必要的类
class BytedanceTTS:
    def __init__(self, url="http://172.31.10.71:8000/api/v1/bytedance/tts"):
        self.url = url
        self.headers = {"Content-Type": "application/json"}
        
    def generate(self, text, voice_type="zh_female_roumeinvyou_emo_v2_mars_bigtts", output_file=None):
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = "output/tts_output"
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"tts_{timestamp}.wav")
        
        data = {
            "text": text,
            "voice_type": voice_type
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
    def __init__(self, api_key: str = None, base_url: str = "https://ark.cn-beijing.volces.com/api/v3"):
        if api_key is None:
            api_key = os.environ.get("ARK_API_KEY", "5cf8e2f7-8465-4ccc-bf84-e32f05be0fb4")
        
        self.client = Ark(
            base_url=base_url,
            api_key=api_key,
        )
    
    def generate(self, prompt: str, model: str = "doubao-seedream-3-0-t2i-250415", 
                 output_dir: str = "output/ark_images", filename: Optional[str] = None) -> List[str]:
        os.makedirs(output_dir, exist_ok=True)
        
        response = self.client.images.generate(
            model=model,
            prompt=prompt,
        )
        
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


# 使用示例
if __name__ == "__main__":
    # 创建多模态新闻播报机器人
    news_bot = MultimodalNewsBot()
    
    # AI新闻示例
    ai_news_prompt = """
    与一两年前相比，谷歌的AI进展显著加快，Gemini 2.5系列模型已能响应文本、图像、音频和视频。
    这一系列更新展示了谷歌在构建全方位AI生态系统方面的战略布局和行业领先优势。
    新发布的Gemini 2.5 Flash模型在性能上有了显著提升，支持更复杂的多模态交互。
    """
    
    # 生成完整的多模态新闻播报  
    result = news_bot.generate_news_report(ai_news_prompt)
    
    # 打印结果
    print("\n生成结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))