import os
import re
import requests
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from datetime import datetime
from gtts import gTTS
import logging
import pathlib
from pathlib import Path
import time
import asyncio
from aigc.V2.main import NewsVideoGenerator
import shutil # Import shutil for directory removal

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WechatMessageInput(BaseModel):
    """Input schema for WechatMessageTool."""
    content: str = Field(..., description="要发送的内容")
    webhook_key: str = Field(None, description="企业微信webhook的key，默认使用环境变量中的值")
    mp3_file: str = Field(None, description="要发送的MP3文件路径，如果未提供则自动生成")

class WechatMessageTool(BaseTool):
    name: str = "企业微信消息发送工具"
    description: str = (
        "使用此工具将内容发送到企业微信机器人，支持发送文本和自动生成的MP3语音文件。"
    )
    args_schema: Type[BaseModel] = WechatMessageInput

    @staticmethod
    def clean_markdown(text):
        """
        清理 Markdown 格式，去除标题标记（##）和多余的空行，保留纯文本。
        
        参数：
        - text: 输入的 Markdown 文本
        返回：
        - 清理后的纯文本
        """
        # 去除 ## 开头的标题标记
        text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
        # 去除多余的空行
        text = re.sub(r'\n\s*\n', '\n', text)
        # 去除行首行尾的空白字符
        text = text.strip()
        return text
    
    @staticmethod
    def preprocess_for_chinese(text):
        """
        预处理中文文本，按句子分割并优化停顿，适合 gTTS 语音合成。
        
        参数：
        - text: 输入文本
        返回：
        - 优化后的文本，句子间添加换行
        """
        # 按中文句号、问号、感叹号等分割
        sentences = re.split(r'([。！？；])', text)
        # 合并标点与其前面的文本，并在句子间添加换行
        result = []
        for i in range(0, len(sentences)-1, 2):
            sentence = sentences[i] + (sentences[i+1] if i+1 < len(sentences) else '')
            result.append(sentence.strip())
        # 用换行符连接句子，增强语音断句
        return '\n'.join(result)

    def _run(self, content: str, webhook_key: str = None, mp3_file: str = None) -> str:
        try:
            logger.info("开始执行企业微信消息发送工具")
            
            # 验证输入内容
            if not content or not content.strip():
                logger.error("输入内容为空或仅包含空白字符")
                return "输入内容为空，无法发送到企业微信"

            # 检查是否需要发送到企业微信
            include_wechat = os.getenv("INCLUDE_WECHAT", "true").lower() == "true"
            if not include_wechat:
                logger.info("INCLUDE_WECHAT设置为false，跳过企业微信发送")
                return "企业微信发送已禁用"

            # 如果没有提供webhook_key，则使用环境变量中的值
            if not webhook_key:
                webhook_key = os.getenv("WECHAT_WEBHOOK_KEY", "8b529e9f-1dc9-4b5c-a60a-1b8d3298acdd")
                logger.info(f"使用Webhook密钥: {webhook_key[:8]}...")

            # 构建webhook完整URL
            webhook_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={webhook_key}"

            # 清理Markdown格式
            logger.info("清理Markdown格式")
            if content.startswith("```markdown") and content.endswith("```"):
                content = content[12:-3].strip()
            elif content.startswith("```") and content.endswith("```"):
                content = content[3:-3].strip()

            # 保留标题的Markdown格式
            lines = content.splitlines()
            processed_lines = []
            for line in lines:
                # 如果是标题行（以#开头），保持原样
                if line.strip().startswith('#'):
                    processed_lines.append(line)
                # 如果是【AI日报】开头的行，添加#前缀和当前日期
                elif line.strip().startswith('【AI日报】'):
                    today = datetime.now()
                    date_str = today.strftime("%Y年%m月%d日")
                    processed_lines.append(f"# 【AI日报】{date_str}")
                else:
                    processed_lines.append(line)
            
            clean_content = "\n".join(processed_lines)
            logger.info(f"清理后内容长度: {len(clean_content)} 字符")

            if not clean_content:
                logger.error("清理后的内容为空")
                return "清理后的内容为空，无法发送到企业微信"

            # 截断过长内容（企业微信消息有4096字节限制）
            max_length = 4000
            if len(clean_content.encode('utf-8')) > max_length:
                clean_content = clean_content[:max_length-50] + "...\n\n*[内容过长，已截断]*"
                logger.warning("内容过长，已截断")

            # 确保Outputs目录存在
            outputs_dir = pathlib.Path("Outputs")
            if not outputs_dir.exists():
                logger.info(f"创建Outputs目录: {outputs_dir.absolute()}")
                outputs_dir.mkdir(parents=True, exist_ok=True)
            else:
                logger.info(f"Outputs目录已存在: {outputs_dir.absolute()}")

            # 验证Outputs目录可写
            try:
                test_file = outputs_dir / "test_write.txt"
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                logger.info("Outputs目录可写")
            except Exception as e:
                logger.error(f"Outputs目录不可写: {str(e)}")
                return f"Outputs目录不可写: {str(e)}"

            # 检查是否需要发送媒体文件
            send_media = os.getenv("SEND_MEDIA", "true").lower() == "true"
            
            if send_media:
                # 检查是否需要生成视频
                generate_video = os.getenv("GENERATE_VIDEO", "false").lower() == "true"
                
                if generate_video:
                    # 生成视频文件
                    today = datetime.now()
                    date_str = today.strftime("%Y年%m月%d日")
                    video_file = outputs_dir / f"【AI日报】{date_str}.mp4"
                    logger.info(f"将生成视频文件: {video_file}")

                    try:
                        logger.info("开始生成视频文件")
                        # 清理 Markdown 格式
                        clean_text = self.clean_markdown(clean_content)

                        # 删除旧的 output 目录（如果存在）
                        home_dir = Path.home()
                        old_output_dir = home_dir / "Desktop" / "PythonProject" / "deepseek_ai_news_crew" / "output"
                        
                        print(f"尝试删除的目录路径: {old_output_dir}")    
                        if old_output_dir.exists() and old_output_dir.is_dir():
                            shutil.rmtree(old_output_dir)
                            print("旧的 output 目录删除成功。")
                        else:
                            print("未检测到旧的 output 目录，跳过删除。")              
                                                                                
                        # 调用aigec.V2.main中的generate_news_video生成视频
                        generator = NewsVideoGenerator(output_dir=str(outputs_dir))
                        result = generator.generate_news_video(
                            news_text=clean_text,
                            output_filename=video_file.name,
                            use_multiprocessing=True,
                            max_workers=6,
                            compress_video=True
                        )

                        output_path = result.get('concatenation', {}).get('output_path')

                        if output_path and os.path.exists(output_path):
                            logger.info(f"成功生成视频文件: {output_path}")
                            mp3_file = Path(output_path)
                            
                            # 等待文件完全写入
                            max_wait = 2000
                            wait_interval = 1
                            waited = 0
                            last_size = -1
                            stable_count = 0
                            
                            while waited < max_wait:
                                current_size = os.path.getsize(output_path)
                                if current_size > 0:
                                    if current_size == last_size:
                                        stable_count += 1
                                        if stable_count >= 3:
                                            logger.info(f"视频文件已完全生成，大小: {current_size} 字节")
                                            break
                                    else:
                                        stable_count = 0
                                        logger.info(f"视频文件正在生成中，当前大小: {current_size} 字节")
                                last_size = current_size
                                time.sleep(wait_interval)
                                waited += wait_interval
                                logger.info(f"等待视频文件生成完成... ({waited:.1f}秒)")
                            
                            if waited >= max_wait:
                                logger.error("等待视频文件生成超时")
                                return "文本消息准备发送，但视频文件生成超时"
                        else:
                            logger.error("生成视频文件失败")
                            return "文本消息准备发送，但生成视频文件失败"
                    except Exception as e:
                        logger.error(f"生成视频文件失败: {str(e)}")
                        return f"文本消息准备发送，但生成视频文件失败: {str(e)}"
                else:
                    # 生成语音文件
                    today = datetime.now()
                    date_str = today.strftime("%Y年%m月%d日")
                    mp3_file = outputs_dir / f"【AI日报】{date_str}.wav"
                    logger.info(f"将生成语音文件: {mp3_file}")

                    try:
                        logger.info("开始生成语音文件")
                        # 从环境变量读取语音生成方式
                        use_bytedance_tts = os.getenv("USE_BYTEDANCE_TTS", "false").lower() == "true"
                        
                        if use_bytedance_tts:
                            # 使用字节跳动TTS服务生成语音
                            from text2voice_BytedanceTTS import BytedanceTTS
                            tts = BytedanceTTS()
                            output_path = tts.generate(clean_content, output_file=str(mp3_file))
                        else:
                            # 使用Google TTS生成语音
                            from gtts import gTTS
                            # 清理 Markdown 格式
                            clean_text = self.clean_markdown(clean_content)
                            # 预处理中文文本，优化断句
                            processed_text = self.preprocess_for_chinese(clean_text)
                            tts = gTTS(text=processed_text, lang='zh-cn')
                            output_path = str(mp3_file)
                            tts.save(output_path)
                        
                        if output_path and os.path.exists(output_path):
                            logger.info(f"成功生成WAV文件: {output_path}")
                            mp3_file = Path(output_path)
                            
                            # 等待文件完全写入
                            max_wait = 300
                            wait_interval = 1
                            waited = 0
                            last_size = -1
                            stable_count = 0
                            
                            while waited < max_wait:
                                current_size = os.path.getsize(output_path)
                                if current_size > 0:
                                    if current_size == last_size:
                                        stable_count += 1
                                        if stable_count >= 3:
                                            logger.info(f"WAV文件已完全生成，大小: {current_size} 字节")
                                            break
                                    else:
                                        stable_count = 0
                                        logger.info(f"WAV文件正在生成中，当前大小: {current_size} 字节")
                                last_size = current_size
                                time.sleep(wait_interval)
                                waited += wait_interval
                                logger.info(f"等待WAV文件生成完成... ({waited:.1f}秒)")
                            
                            if waited >= max_wait:
                                logger.error("等待WAV文件生成超时")
                                return "文本消息准备发送，但WAV文件生成超时"
                        else:
                            logger.error("生成WAV文件失败")
                            return "文本消息准备发送，但生成WAV文件失败"
                    except Exception as e:
                        logger.error(f"生成语音文件失败: {str(e)}")
                        return f"文本消息准备发送，但生成语音文件失败: {str(e)}"

                # 验证媒体文件是否存在
                if not os.path.exists(mp3_file):
                    logger.error(f"媒体文件不存在: {mp3_file}")
                    return f"文本消息准备发送，但媒体文件不存在: {mp3_file}"

                # 发送媒体文件
                logger.info(f"上传媒体文件: {mp3_file}")
                upload_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key={webhook_key}&type=file"

                with open(mp3_file, 'rb') as f:
                    files = {
                        'file': (os.path.basename(mp3_file), f)
                    }
                    upload_response = requests.post(upload_url, files=files, timeout=60)

                    if upload_response.status_code == 200:
                        upload_result = upload_response.json()
                        if upload_result.get("errcode") == 0:
                            media_id = upload_result.get("media_id")
                            logger.info(f"文件上传成功，media_id: {media_id}")

                            file_payload = {
                                "msgtype": "file",
                                "file": {
                                    "media_id": media_id
                                }
                            }

                            file_response = requests.post(
                                webhook_url,
                                headers={"Content-Type": "application/json"},
                                json=file_payload,
                                timeout=10
                            )

                            file_result = file_response.json()
                            if file_result.get("errcode") == 0:
                                logger.info("媒体文件发送成功")
                                return "文本消息和媒体文件发送成功"
                            else:
                                logger.error(f"媒体文件消息发送失败: {file_result}")
                                return f"文本消息发送成功，但媒体文件消息发送失败: {file_result}"
                        else:
                            logger.error(f"上传媒体文件失败: {upload_result}")
                            return f"文本消息发送成功，但上传媒体文件失败: {upload_result}"
                    else:
                        logger.error(f"上传媒体文件请求失败，状态码: {upload_response.status_code}")
                        return f"文本消息发送成功，但上传媒体文件请求失败，状态码: {upload_response.status_code}"

            # 构建payload - 使用markdown格式
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": clean_content 
                }
            }

            # 发送文本消息
            logger.info("发送文本消息到企业微信")
            response = requests.post(
                webhook_url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=10
            )

            result = response.json()
            if result.get("errcode") != 0:
                logger.error(f"文本消息发送失败: {result}")
                return f"文本消息发送失败: {result}"

            logger.info("文本消息发送成功")
            return "文本消息发送成功" + ("（媒体文件发送已禁用）" if not send_media else "")

        except Exception as e:
            logger.error(f"发送企业微信消息时发生错误: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return f"发送企业微信消息时发生错误: {str(e)}"

class MarkdownCleanerInput(BaseModel):
    """Input schema for MarkdownCleanerTool."""
    content: str = Field(..., description="需要清理的Markdown内容")

class MarkdownCleanerTool(BaseTool):
    name: str = "Markdown格式清理工具"
    description: str = (
        "使用此工具清理Markdown内容中的格式标记，比如开头的```markdown和结尾的```。"
    )
    args_schema: Type[BaseModel] = MarkdownCleanerInput

    def _run(self, content: str) -> str:
        try:
            if content.startswith("```markdown") and content.endswith("```"):
                content = content[12:-3].strip()
            elif content.startswith("```") and content.endswith("```"):
                content = content[3:-3].strip()

            return content

        except Exception as e:
            return f"清理Markdown格式时发生错误: {str(e)}"