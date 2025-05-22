import os
import re
import sys
import logging
from gtts import gTTS

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('text_to_speech.log', encoding='utf-8')
    ]
)

def clean_markdown(text):
    """
    清理 Markdown 格式，去除标题标记（##）和多余的空行，保留纯文本。
    
    参数：
    - text: 输入的 Markdown 文本
    返回：
    - 清理后的纯文本
    """
    try:
        # 去除 ## 开头的标题标记
        text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
        # 去除多余的空行
        text = re.sub(r'\n\s*\n', '\n', text)
        # 去除行首行尾的空白字符
        text = text.strip()
        logging.info(f"成功清理Markdown格式，文本长度: {len(text)}")
        return text
    except Exception as e:
        logging.error(f"清理Markdown格式时出错: {str(e)}")
        return text

def convert_text_to_speech(input_file, output_file, language='zh-cn'):
    """
    使用 Google 文本转语音将文件中的文本转换为中文语音并保存为 MP3。
    
    参数：
    - input_file: 输入文本或 Markdown 文件的路径
    - output_file: 保存输出 MP3 文件的路径
    - language: 语音的语言代码（默认：'zh-cn' 表示简体中文）
    """
    try:
        logging.info(f"开始转换文件: {input_file} -> {output_file}")
        
        # 检查输入文件是否存在
        if not os.path.exists(input_file):
            logging.error(f"输入文件不存在: {input_file}")
            return False
            
        # 读取输入文件内容
        with open(input_file, 'r', encoding='utf-8') as file:
            text = file.read()
            logging.info(f"成功读取输入文件，内容长度: {len(text)}")
        
        # 清理 Markdown 格式
        clean_text = clean_markdown(text)
        logging.info(f"清理后的文本长度: {len(clean_text)}")
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"创建输出目录: {output_dir}")
        
        # 使用清理后的文本初始化 gTTS
        logging.info("开始初始化gTTS...")
        tts = gTTS(text=clean_text, lang=language, slow=False)
        
        # 将语音保存为 MP3 文件
        logging.info(f"开始保存MP3文件: {output_file}")
        tts.save(output_file)
        
        # 验证文件是否成功创建
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            logging.info(f"成功生成MP3文件，大小: {file_size} 字节")
            return True
        else:
            logging.error("MP3文件未成功创建")
            return False
        
    except FileNotFoundError as e:
        logging.error(f"文件未找到: {str(e)}")
        return False
    except Exception as e:
        logging.error(f"转换过程中发生错误: {str(e)}")
        return False

# 如果直接运行这个脚本
if __name__ == "__main__":
    # 如果提供了命令行参数
    if len(sys.argv) > 2:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
    else:
        # 默认使用当前日期的文件
        from datetime import datetime
        today_date = datetime.now().strftime("%Y%m%d")
        input_file = f"Outputs/ai_news_report_{today_date}.md"
        output_file = f"Outputs/ai_news_report_{today_date}.mp3"
    
    logging.info(f"使用输入文件: {input_file}")
    logging.info(f"使用输出文件: {output_file}")
    
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        logging.error(f"找不到输入文件: {input_file}")
        sys.exit(1)
    
    # 转换为语音
    if convert_text_to_speech(input_file, output_file):
        logging.info("转换成功完成")
    else:
        logging.error("转换失败")
        sys.exit(1) 