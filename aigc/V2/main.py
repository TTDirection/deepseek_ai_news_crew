from .TotalVideoWithLLM import LongNewsProcessor
from .video_concatenator import VideoConcatenator
import os
import subprocess
import math

class NewsVideoGenerator:
    """
    新闻视频生成器类，用于处理新闻文本并生成对应视频
    """
    
    def __init__(self, output_dir="output/concatenated"):
        """
        初始化新闻视频生成器
        
        参数:
            output_dir: 输出目录，默认为"output/concatenated"
        """
        self.output_dir = output_dir
        
    def generate_news_video(self, news_text, output_filename, 
                          chars_per_segment=25, 
                          max_audio_duration=4.8,
                          use_multiprocessing=True, 
                          max_workers=3,
                          add_subtitles=True,
                          compress_video=False,
                          target_size_mb=None
                          ):
        """
        处理新闻文本并生成视频
        
        参数:
            news_text: 要处理的新闻文本
            output_filename: 输出视频文件名
            chars_per_segment: 每个片段的最大字符数，默认25
            max_audio_duration: 最大音频时长(秒)，默认4.8秒
            use_multiprocessing: 是否使用多进程，默认True
            max_workers: 最大进程数，默认3
            add_subtitles: 是否添加字幕，默认True
            compress_video: 是否压缩视频，默认False
            target_size_mb: 目标视频大小(MB)，默认None表示不压缩
            
        返回:
            dict: 包含处理结果的字典
        """
        # 提取项目名称（不含扩展名）
        if "." in output_filename:
            project_name = output_filename.split(".")[0]
        else:
            project_name = output_filename
            output_filename = f"{output_filename}.mp4"
            
        # 步骤1: 处理新闻文本并生成视频片段
        processor = LongNewsProcessor(
            max_chars_per_segment=chars_per_segment,  # 每个片段的字符数
            max_audio_duration=max_audio_duration,    # 最大音频时长(秒)
            max_workers=max_workers                   # 并行进程数
        )
        
        # 处理新闻
        result = processor.process_long_news(
            news_text,
            project_name=project_name,
            calibrate=False,                          # 是否校准语速
            add_subtitles=add_subtitles,             # 添加字幕
            use_multiprocessing=use_multiprocessing  # 启用/禁用多进程
        )
        
        # 获取输出信息
        segments_dir = result['output_directory']
        segments_count = result['successful_segments']
        processing_time = result['processing_time_seconds']
        
        print(f"\n=== 视频片段生成完成 ===")
        print(f"成功生成 {segments_count} 个视频片段")
        print(f"处理时间: {processing_time:.2f} 秒")
        print(f"模式: {'多进程' if result['multiprocessing_used'] else '单进程'}")
        if result['multiprocessing_used']:
            print(f"并行进程数: {result['max_workers']}")
        print(f"视频目录: {segments_dir}")
        
        # 步骤2: 合并生成的视频片段
        if segments_count > 0:
            print(f"\n=== 开始视频合并 ===")
            concatenator = VideoConcatenator(output_dir=self.output_dir)
            
            # 自动合并视频片段
            concatenated_video = concatenator.auto_concatenate(
                search_dir=segments_dir,              # 视频片段目录
                output_filename=output_filename,      # 输出文件名
                pattern="*_final.mp4",                # 匹配最终视频的模式
                force_reencode=False                  # 自动决定是否需要重新编码
            )
            
            # 将合并结果添加到总体结果中
            result['concatenation'] = {
                'status': 'success' if concatenated_video else 'failed',
                'output_path': concatenated_video,
                'segment_count': segments_count
            }
            
            # 步骤3: 如果需要，压缩视频到指定大小
            if compress_video and target_size_mb and concatenated_video and os.path.exists(concatenated_video):
                print(f"\n=== 开始视频压缩 ===")
                print(f"目标大小: {target_size_mb} MB")
                
                # 创建压缩视频输出路径
                compressed_path = self._compress_video(
                    input_file=concatenated_video,
                    target_size_mb=target_size_mb
                )
                
                if compressed_path:
                    result['compression'] = {
                        'status': 'success',
                        'original_path': concatenated_video,
                        'compressed_path': compressed_path,
                        'target_size_mb': target_size_mb,
                        'actual_size_mb': os.path.getsize(compressed_path) / (1024 * 1024)
                    }
                    # 更新最终输出路径
                    result['concatenation']['output_path'] = compressed_path
                else:
                    result['compression'] = {
                        'status': 'failed',
                        'reason': '压缩过程失败'
                    }
            else:
                result['compression'] = {
                    'status': 'skipped',
                    'reason': '未启用压缩或没有生成视频'
                }
        else:
            result['concatenation'] = {
                'status': 'skipped',
                'reason': '没有生成视频片段'
            }
            result['compression'] = {
                'status': 'skipped',
                'reason': '没有生成视频片段'
            }
        
        # 打印最终结果
        if result['concatenation']['status'] == 'success':
            print(f"\n✅ 完整处理成功!")
            print(f"最终视频: {result['concatenation']['output_path']}")
            
            if result['compression']['status'] == 'success':
                original_size = os.path.getsize(result['compression']['original_path']) / (1024 * 1024)
                compressed_size = result['compression']['actual_size_mb']
                print(f"视频已压缩: {original_size:.2f}MB → {compressed_size:.2f}MB")
                
            print(f"总处理时间: {result['processing_time_seconds']:.2f} 秒")
        else:
            print(f"\n⚠️ 视频片段已生成但合并{result['concatenation']['status']}")
            if result['concatenation']['status'] == 'failed':
                print("请查看日志获取错误详情")
                
        return result
    
    def _compress_video(self, input_file, target_size_mb, compress_threshold_mb=20, iteration=0, max_iterations=4):
        """
        压缩视频到指定大小，并覆盖原文件
        
        参数:
            input_file: 输入视频文件路径
            target_size_mb: 目标大小(MB)
            compress_threshold_mb: 压缩阈值(MB)，只有文件大于此值时才压缩
            iteration: 当前迭代次数
            max_iterations: 最大迭代次数，防止无限循环
            
        返回:
            str: 压缩后的视频路径，如果失败则返回None
        """
        if not os.path.exists(input_file):
            print(f"错误: 输入文件不存在 {input_file}")
            return None
            
        try:
            # 获取原始视频信息
            file_size_bytes = os.path.getsize(input_file)
            file_size_mb = file_size_bytes / (1024 * 1024)
            
            # 如果文件已经小于目标大小，直接返回原文件
            if file_size_mb <= target_size_mb:
                print(f"视频已经小于目标大小 ({file_size_mb:.2f}MB <= {target_size_mb}MB)，无需压缩")
                return input_file
                
            # 如果文件小于压缩阈值，直接返回原文件
            if file_size_mb <= compress_threshold_mb:
                print(f"视频小于压缩阈值 ({file_size_mb:.2f}MB <= {compress_threshold_mb}MB)，跳过压缩")
                return input_file
                
            # 如果达到最大迭代次数，停止压缩
            if iteration >= max_iterations:
                print(f"达到最大压缩尝试次数({max_iterations})，返回当前结果")
                return input_file
                
            # 获取视频时长
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                '-of', 'default=noprint_wrappers=1:nokey=1', input_file]
            duration = float(subprocess.check_output(cmd).decode('utf-8').strip())
            
            # 计算目标比特率 (kb/s) = (target_size_bytes * 8) / (duration_seconds * 1000)
            target_size_bytes = target_size_mb * 1024 * 1024
            
            # 为音频预留一部分空间（假设音频64kbps）
            audio_size_bytes = (64 * 1000 / 8) * duration  # 音频大小（字节）
            video_size_bytes = target_size_bytes - audio_size_bytes
            
            # 确保视频大小非负
            video_size_bytes = max(video_size_bytes, target_size_bytes * 0.8)
            
            # 计算视频比特率
            target_bitrate_kbps = int((video_size_bytes * 8) / (duration * 1000))
            
            # 根据迭代次数逐渐降低比特率
            if iteration > 0:
                target_bitrate_kbps = int(target_bitrate_kbps * (0.8 ** iteration))
            
            # 限制最小比特率为100kbps，以确保视频质量
            target_bitrate_kbps = max(target_bitrate_kbps, 100)
            
            # 创建临时输出文件路径（使用唯一标识符以避免冲突）
            temp_output_file = f"{input_file}.temp_{iteration}.mp4"
            
            # 构建ffmpeg命令
            cmd = [
                'ffmpeg', '-i', input_file,
                '-c:v', 'libx264', 
                '-crf', str(23 + iteration * 3),  # 随迭代递增CRF，提高压缩率
                '-preset', 'slower',              # 较慢的编码速度，但能获得更好的压缩率
                '-b:v', f'{target_bitrate_kbps}k',  # 目标视频比特率
                '-maxrate', f'{int(target_bitrate_kbps * 1.5)}k',  # 最大比特率
                '-bufsize', f'{target_bitrate_kbps * 2}k',         # 缓冲区大小
                '-c:a', 'aac', '-b:a', '64k',    # 音频压缩到64kbps AAC
                '-y',                            # 覆盖输出文件
                temp_output_file
            ]
            
            print(f"正在压缩视频(第{iteration+1}次尝试): {input_file}")
            print(f"目标比特率: {target_bitrate_kbps}kbps, CRF: {23 + iteration * 2}")
            
            # 执行ffmpeg命令
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                print(f"视频压缩失败: {stderr.decode('utf-8')}")
                if os.path.exists(temp_output_file):
                    os.remove(temp_output_file)
                return None
                
            # 检查压缩后的文件大小
            compressed_size_mb = os.path.getsize(temp_output_file) / (1024 * 1024)
            
            print(f"压缩结果: {file_size_mb:.2f}MB → {compressed_size_mb:.2f}MB (目标: {target_size_mb}MB)")
            
            # 如果压缩后文件仍然超过目标大小10%以上，递归尝试下一次压缩
            if compressed_size_mb > target_size_mb * 1.1 and compressed_size_mb > 1:  # 确保至少有1MB
                print(f"压缩后仍超过目标大小，尝试更高压缩率...")
                # 删除当前临时文件
                os.remove(temp_output_file)
                # 递增迭代次数并重试
                return self._compress_video(input_file, target_size_mb, compress_threshold_mb, iteration + 1, max_iterations)
            
            # 如果压缩成功，使用最终压缩后的文件替换原文件
            os.replace(temp_output_file, input_file)
            print(f"压缩完成，已替换原文件: {input_file}")
            
            return input_file
            
        except Exception as e:
            print(f"视频压缩过程中发生错误: {str(e)}")
            import traceback
            traceback.print_exc()
            # 清理可能存在的临时文件
            temp_output_file = f"{input_file}.temp_{iteration}.mp4"
            if os.path.exists(temp_output_file):
                os.remove(temp_output_file)
            return None
# 示例代码
if __name__ == "__main__":
    # 测试代码
    generator = NewsVideoGenerator(output_dir="output/news_videos")
    
    news_text = """
【AI日报】2025年06月05日
1. 冲击自回归，扩散模型正在改写下一代通用模型范式
Google的Gemini Diffusion模型取得突破性进展，其生成速度是现有最快模型的五倍，同时保持了相当的编程性能。这一进展标志着扩散模型在通用模型范式中的重要突破，可能对未来AI模型设计产生深远影响。
2. OpenAI发布医疗大模型评测标准HealthBench
OpenAI最新发布了医疗大模型评测标准HealthBench，其o3模型在该标准上表现优于Claude 3.7 Sonnet和Gemini 2.5 Pro。相比之前的GPT-4o，性能提升了28%，展示了OpenAI在医疗AI领域的持续进步。
3. 无需训练，提升多模态大模型细粒度理解能力
北京大学彭宇新团队提出了一种训练无关的动态聚焦视觉搜索方法，能显著提升多模态大模型的细粒度理解能力。该工作已被CVPR 2025接收为Highlight(前13.5%)并完全开源。

    """
    
    result = generator.generate_news_video(
        news_text=news_text,
        output_filename="ai_news_0604.mp4",
        use_multiprocessing=True,
        max_workers=6,
        compress_video=True,     # 启用视频压缩
        target_size_mb=16        # 压缩目标大小为20MB
    )