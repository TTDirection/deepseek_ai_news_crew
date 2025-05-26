#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time
import base64
import mimetypes
from pathlib import Path

def encode_image(image_path):
    """将图片编码为base64格式"""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"图片文件不存在: {image_path}")
    
    file_size = os.path.getsize(image_path)
    if file_size > 10 * 1024 * 1024:  # 10MB
        raise ValueError(f"图片大小超出限制(10MB): {file_size / 1024 / 1024:.2f}MB")
    
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type or not mime_type.startswith('image/'):
        ext = Path(image_path).suffix.lower()
        mime_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp'
        }
        mime_type = mime_map.get(ext, 'image/jpeg')
    
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        data_uri = f"data:{mime_type};base64,{encoded_string}"
        return data_uri

def test_video_duration(test_duration, image_path=None):
    """测试特定时长的视频生成"""
    print(f"\n=== 测试视频时长: {test_duration}秒 ===")
    
    # 简单的测试提示词
    base_prompt = "科技感的数据流动和光效，现代简约的AI场景"
    
    # 测试不同的参数格式
    test_formats = [
        f"--resolution 720p --dur {test_duration} --camerafixed false {base_prompt}",
        f"--dur {test_duration} --resolution 720p {base_prompt}",
        f"{base_prompt} --dur {test_duration}",
        f"duration:{test_duration} {base_prompt}",
        f"[{test_duration}s] {base_prompt}"
    ]
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer 5cf8e2f7-8465-4ccc-bf84-e32f05be0fb4"
    }
    
    base_url = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
    
    for i, prompt_format in enumerate(test_formats):
        try:
            print(f"\n--- 测试格式 {i+1}: ---")
            print(f"提示词: {prompt_format}")
            
            content = [
                {
                    "type": "text",
                    "text": prompt_format
                }
            ]
            
            # 如果提供了图片路径，添加图片
            if image_path:
                try:
                    image_data_uri = encode_image(image_path)
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_uri
                        }
                    })
                    print(f"已添加图片: {image_path}")
                except Exception as e:
                    print(f"图片编码失败: {e}")
            
            data = {
                "model": "doubao-seedance-1-0-lite-i2v-250428",
                "content": content
            }
            
            print("发送请求...")
            response = requests.post(base_url, headers=headers, json=data)
            
            if response.status_code != 200:
                print(f"请求失败，状态码: {response.status_code}")
                print(f"响应内容: {response.text}")
                continue
            
            response_data = response.json()
            task_id = response_data.get("id")
            
            if not task_id:
                print("无法获取任务ID")
                print(f"响应: {json.dumps(response_data, ensure_ascii=False, indent=2)}")
                continue
            
            print(f"任务创建成功，ID: {task_id}")
            
            # 监控任务状态
            success = monitor_task(task_id, headers, base_url)
            
            if success:
                print(f"格式 {i+1} 成功！")
                return True
            else:
                print(f"格式 {i+1} 失败")
                
        except Exception as e:
            print(f"格式 {i+1} 出错: {e}")
    
    return False

def monitor_task(task_id, headers, base_url):
    """监控任务状态"""
    max_attempts = 30
    
    for attempt in range(max_attempts):
        try:
            url = f"{base_url}/{task_id}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            status_data = response.json()
            
            status = status_data.get("status")
            print(f"[{attempt+1}] 状态: {status}")
            
            if status == "succeeded":
                print("任务成功完成！")
                
                # 检查是否有视频URL信息
                if "content" in status_data:
                    print(f"Content: {status_data['content']}")
                if "results" in status_data:
                    print(f"Results: {status_data['results']}")
                
                return True
                
            elif status == "failed":
                print("任务失败")
                print(f"失败原因: {status_data.get('failure_reason', '未知')}")
                print(f"完整响应: {json.dumps(status_data, ensure_ascii=False, indent=2)}")
                return False
                
            elif status in ["pending", "queued", "running"]:
                time.sleep(10)
                continue
            else:
                print(f"未知状态: {status}")
                return False
                
        except Exception as e:
            print(f"监控出错: {e}")
            time.sleep(10)
    
    print("监控超时")
    return False

def main():
    """主测试函数"""
    print("=== 视频时长参数测试 ===")
    
    # 测试不同时长
    test_durations = [5, 8, 10, 15, 20]
    
    # 如果有图片，请修改这个路径
    image_path = "/home/taotao/Desktop/PythonProject/deepseek_ai_news_crew/aigc/output/image/news_image_20250526_101437.png"  # 修改为你的图片路径，或设为None
    
    # 检查图片是否存在
    if image_path and not os.path.exists(image_path):
        print(f"图片不存在: {image_path}")
        image_path = None
    
    success_durations = []
    
    for duration in test_durations:
        success = test_video_duration(duration, image_path)
        if success:
            success_durations.append(duration)
            print(f"✓ {duration}秒 - 成功")
        else:
            print(f"✗ {duration}秒 - 失败")
    
    print(f"\n=== 测试结果 ===")
    print(f"成功的时长: {success_durations}")
    print(f"失败的时长: {[d for d in test_durations if d not in success_durations]}")

if __name__ == "__main__":
    import os
    main()