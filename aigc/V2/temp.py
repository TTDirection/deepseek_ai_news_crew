import os
import time
import subprocess

def test_compress_video():
    """
    测试视频压缩函数，直接对原始文件进行操作
    """
    # 测试文件路径
    input_file = "/home/taotao/Desktop/PythonProject/deepseek_ai_news_crew/output/concatenated/【AI日报】2025年06月04日_complete_20250604_161904.mp4"
    
    # 检查文件是否存在
    if not os.path.exists(input_file):
        print(f"测试文件不存在: {input_file}")
        return
    
    # 获取原始文件大小
    original_size_mb = os.path.getsize(input_file) / (1024 * 1024)
    print(f"原始文件大小: {original_size_mb:.2f}MB")
    
    # 测试场景1: 压缩到18MB
    print("\n=== 测试场景1: 压缩到18MB ===")
    start_time = time.time()
    result = _compress_video(None, input_file, 18)
    elapsed_time = time.time() - start_time
    
    if result:
        compressed_size_mb = os.path.getsize(input_file) / (1024 * 1024)
        print(f"压缩结果: {original_size_mb:.2f}MB → {compressed_size_mb:.2f}MB")
        print(f"耗时: {elapsed_time:.2f}秒")
    else:
        print("压缩失败")

# 添加这一行是为了让_compress_video方法可以作为独立函数调用
def _compress_video(self, input_file, target_size_mb, compress_threshold_mb=20, iteration=0, max_iterations=3):
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
            '-crf', str(23 + iteration * 2),  # 随迭代递增CRF，提高压缩率
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
# 执行测试
if __name__ == "__main__":
    test_compress_video()