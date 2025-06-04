import os
import re
import subprocess
import glob
from pathlib import Path
from typing import List, Tuple
import json
from datetime import datetime

class VideoConcatenator:
    """视频拼接器，用于将分段视频按顺序拼接"""
    
    def __init__(self, output_dir: str = "output/concatenated"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def find_video_segments(self, search_dir: str, pattern: str = "*_final.mp4") -> List[Tuple[str, int]]:
        video_files = []
        search_pattern = os.path.join(search_dir, "**", pattern)
        found_files = glob.glob(search_pattern, recursive=True)
        for file_path in found_files:
            filename = os.path.basename(file_path)
            patterns = [
                r'segment_(\d+)',
                r'_(\d+)_final',
                r'_(\d+)\.',
                r'(\d+)_final',
                r'(\d+)\.mp4'
            ]
            segment_num = None
            for pattern_regex in patterns:
                match = re.search(pattern_regex, filename)
                if match:
                    segment_num = int(match.group(1))
                    break
            if segment_num is not None:
                video_files.append((file_path, segment_num))
                print(f"找到视频片段: {filename} -> 序号 {segment_num}")
            else:
                print(f"警告: 无法从文件名提取序号: {filename}")
        video_files.sort(key=lambda x: x[1])
        print(f"\n总共找到 {len(video_files)} 个视频片段")
        return video_files
    
    def check_video_properties(self, video_path: str) -> dict:
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                info = json.loads(result.stdout)
                video_stream = None
                audio_stream = None
                for stream in info['streams']:
                    if stream['codec_type'] == 'video':
                        video_stream = stream
                    elif stream['codec_type'] == 'audio':
                        audio_stream = stream
                properties = {
                    'duration': float(info['format'].get('duration', 0)),
                    'size': int(info['format'].get('size', 0)),
                    'video_codec': video_stream.get('codec_name', 'unknown') if video_stream else None,
                    'audio_codec': audio_stream.get('codec_name', 'unknown') if audio_stream else None,
                    'width': int(video_stream.get('width', 0)) if video_stream else 0,
                    'height': int(video_stream.get('height', 0)) if video_stream else 0,
                    'fps': eval(video_stream.get('r_frame_rate', '0/1')) if video_stream else 0
                }
                return properties
            else:
                print(f"获取视频信息失败: {result.stderr}")
                return {}
        except Exception as e:
            print(f"检查视频属性时出错: {e}")
            return {}
    
    def create_filelist(self, video_files: List[Tuple[str, int]], temp_dir: str) -> str:
        filelist_path = os.path.join(temp_dir, "filelist.txt")
        with open(filelist_path, 'w', encoding='utf-8') as f:
            for file_path, segment_num in video_files:
                abs_path = os.path.abspath(file_path)
                escaped_path = abs_path.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        print(f"创建文件列表: {filelist_path}")
        return filelist_path
    
    def concatenate_videos_simple(self, video_files: List[Tuple[str, int]], output_path: str) -> bool:
        if not video_files:
            print("没有找到要拼接的视频文件")
            return False
        temp_dir = os.path.join(self.output_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        try:
            filelist_path = self.create_filelist(video_files, temp_dir)
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', filelist_path,
                '-c', 'copy',
                output_path
            ]
            print(f"开始拼接视频...")
            print(f"命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"视频拼接成功: {output_path}")
                try:
                    os.remove(filelist_path)
                    os.rmdir(temp_dir)
                except:
                    pass
                return True
            else:
                print(f"视频拼接失败: {result.stderr}")
                return False
        except Exception as e:
            print(f"拼接过程中出错: {e}")
            return False
    
    def concatenate_videos_with_reencoding(self, video_files: List[Tuple[str, int]], output_path: str) -> bool:
        if not video_files:
            print("没有找到要拼接的视频文件")
            return False
        temp_dir = os.path.join(self.output_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        try:
            filelist_path = self.create_filelist(video_files, temp_dir)
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', filelist_path,
                '-vf', 'scale=1280:720',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-b:v', '2M',
                '-b:a', '128k',
                '-r', '30',
                output_path
            ]
            print(f"开始重新编码并拼接视频...")
            print(f"命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"视频拼接成功: {output_path}")
                try:
                    os.remove(filelist_path)
                    os.rmdir(temp_dir)
                except:
                    pass
                return True
            else:
                print(f"视频拼接失败: {result.stderr}")
                return False
        except Exception as e:
            print(f"拼接过程中出错: {e}")
            return False
    
    def concatenate_with_intermediate_format(self, video_files: List[Tuple[str, int]], output_path: str) -> bool:
        """使用中间格式进行更稳定的拼接，避免音画不同步问题"""
        if not video_files:
            print("没有找到要拼接的视频文件")
            return False
        
        temp_dir = os.path.join(self.output_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # 转换每个视频到中间格式
        intermediate_files = []
        try:
            print(f"开始转换视频到中间格式...")
            for i, (file_path, segment_num) in enumerate(video_files):
                intermediate_file = os.path.join(temp_dir, f"intermediate_{segment_num:03d}.mkv")
                cmd = [
                    'ffmpeg', '-y',
                    '-i', file_path,
                    '-c:v', 'libx264',  # 使用H.264编码
                    '-preset', 'medium', # 编码速度和质量的平衡
                    '-crf', '18',       # 高质量
                    '-c:a', 'aac',      # AAC音频编码
                    '-b:a', '192k',     # 音频比特率
                    '-vsync', 'cfr',    # 恒定帧率
                    '-movflags', '+faststart',  # 优化Web播放
                    '-af', 'aresample=async=1000',  # 处理音频同步问题
                    intermediate_file
                ]
                print(f"转换第 {i+1}/{len(video_files)} 个视频: {os.path.basename(file_path)}")
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    intermediate_files.append((intermediate_file, segment_num))
                else:
                    print(f"转换中间格式失败: {result.stderr}")
                    return False
                
            # 创建中间文件列表
            intermediate_filelist_path = os.path.join(temp_dir, "intermediate_filelist.txt")
            with open(intermediate_filelist_path, 'w', encoding='utf-8') as f:
                for file_path, _ in intermediate_files:
                    abs_path = os.path.abspath(file_path)
                    escaped_path = abs_path.replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")
            
            # 拼接中间格式文件
            concat_cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', intermediate_filelist_path,
                '-c', 'copy',  # 只复制，不重新编码
                output_path
            ]
            print(f"拼接中间格式视频...")
            result = subprocess.run(concat_cmd, capture_output=True, text=True)
            success = result.returncode == 0
            
            # 清理中间文件
            try:
                for file_path, _ in intermediate_files:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                if os.path.exists(intermediate_filelist_path):
                    os.remove(intermediate_filelist_path)
                os.rmdir(temp_dir)
            except Exception as e:
                print(f"清理中间文件时出错: {e}")
            
            if success:
                print(f"使用中间格式拼接成功: {output_path}")
                return True
            else:
                print(f"使用中间格式拼接失败: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"中间格式拼接过程中出错: {e}")
            return False
    
    def auto_concatenate(self, 
                         search_dir: str = "output", 
                         output_filename: str = None, 
                         pattern: str = "*_final.mp4", 
                         force_reencode: bool = False,
                         use_intermediate: bool = True) -> str:
        print(f"在目录 {search_dir} 中搜索视频片段...")
        video_files = self.find_video_segments(search_dir, pattern)
        if not video_files:
            print("没有找到视频片段文件")
            return None
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            first_filename = os.path.basename(video_files[0][0])
            project_match = re.match(r'(.+?)_segment_\d+', first_filename)
            if project_match:
                project_name = project_match.group(1)
                output_filename = f"{project_name}_complete_{timestamp}.mp4"
            else:
                output_filename = f"concatenated_video_{timestamp}.mp4"
        output_path = os.path.join(self.output_dir, output_filename)
        print(f"\n拼接计划:")
        print(f"输出文件: {output_path}")
        print(f"视频片段顺序:")
        total_duration = 0
        for i, (file_path, segment_num) in enumerate(video_files):
            properties = self.check_video_properties(file_path)
            duration = properties.get('duration', 0)
            total_duration += duration
            print(f"  {i+1:2d}. 片段{segment_num:03d}: {os.path.basename(file_path)} ({duration:.2f}s)")
            if i == 0:
                print(f"      分辨率: {properties.get('width', 0)}x{properties.get('height', 0)}")
                print(f"      视频编码: {properties.get('video_codec', 'unknown')}")
                print(f"      音频编码: {properties.get('audio_codec', 'unknown')}")
                reference_props = properties
            else:
                current_props = properties
                if (current_props.get('width') != reference_props.get('width') or
                    current_props.get('height') != reference_props.get('height') or
                    current_props.get('video_codec') != reference_props.get('video_codec')):
                    force_reencode = True
                    print(f"      警告: 视频参数不一致，将使用重新编码模式")
        print(f"\n预计总时长: {total_duration:.2f}秒 ({total_duration/60:.1f}分钟)")
        
        success = False
        
        if use_intermediate:
            print(f"\n使用中间格式进行稳定拼接...")
            success = self.concatenate_with_intermediate_format(video_files, output_path)
        elif force_reencode:
            print(f"\n使用重新编码模式拼接...")
            success = self.concatenate_videos_with_reencoding(video_files, output_path)
        else:
            print(f"\n使用快速拼接模式...")
            success = self.concatenate_videos_simple(video_files, output_path)
            if not success:
                print(f"快速拼接失败，尝试重新编码模式...")
                success = self.concatenate_videos_with_reencoding(video_files, output_path)
        
        if success:
            if os.path.exists(output_path):
                final_props = self.check_video_properties(output_path)
                final_duration = final_props.get('duration', 0)
                file_size = os.path.getsize(output_path) / (1024 * 1024)
                print(f"\n拼接完成!")
                print(f"输出文件: {output_path}")
                print(f"文件大小: {file_size:.1f} MB")
                print(f"总时长: {final_duration:.2f}秒 ({final_duration/60:.1f}分钟)")
                print(f"分辨率: {final_props.get('width', 0)}x{final_props.get('height', 0)}")
                return output_path
            else:
                print(f"拼接失败: 输出文件不存在")
                return None
        else:
            print(f"拼接失败")
            return None

def main():
    # ====== 你可以在这里修改参数 ======
    search_dir = "/home/taotao/Desktop/PythonProject/deepseek_ai_news_crew/aigc/output/long_news/final_videos"  # 搜索目录
    output_dir = "output/concatenated"     # 输出目录
    output_filename = None                 # 输出文件名（None为自动生成）
    pattern = "*_final.mp4"                # 匹配模式
    force_reencode = False                 # 是否强制重编码
    use_intermediate = True                # 是否使用中间格式(解决音画不同步问题)
    # ===================================
    concatenator = VideoConcatenator(output_dir)
    result = concatenator.auto_concatenate(
        search_dir=search_dir,
        output_filename=output_filename,
        pattern=pattern,
        force_reencode=force_reencode,
        use_intermediate=use_intermediate
    )
    if result:
        print(f"\n✅ 拼接成功完成!")
        print(f"输出文件: {result}")
    else:
        print(f"\n❌ 拼接失败!")

if __name__ == "__main__":
    main()