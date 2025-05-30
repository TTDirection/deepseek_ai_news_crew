# aigc 文件说明
## 第一版， 
enhancedRobot.py 依赖 airobot.py
分词效果不好，拼接的也不好
## 第二版，
TotalVideoWithLLM.py 生成片段 依赖于MultimodalRobot.py
分词采用V3来分词，
video_concatenator.py 拼接片段
中间测试代码有single_audio_multi_video.py，segmentTest.py，
## 第三版
text_segmentation.py - Contains the prompt-based text segmentation logic extracted from TotalVideoWithLLM
video_generation.py - Handles the generation of individual video segments
subtitle_manager.py - Manages subtitle creation and integration
video_concatenator.py - Your existing concatenation functionality
news_processor.py - Core class that orchestrates the entire process