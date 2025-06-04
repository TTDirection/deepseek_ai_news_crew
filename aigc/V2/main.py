from TotalVideoWithLLM import LongNewsProcessor
from video_concatenator import VideoConcatenator

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
                          subtitle_format="srt"):
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
            subtitle_format: 字幕格式，默认"srt"
            
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
            calibrate=True,                          # 是否校准语速
            add_subtitles=add_subtitles,             # 添加字幕
            subtitle_format=subtitle_format,         # 字幕格式
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
        else:
            result['concatenation'] = {
                'status': 'skipped',
                'reason': '没有生成视频片段'
            }
        
        # 打印最终结果
        if result['concatenation']['status'] == 'success':
            print(f"\n✅ 完整处理成功!")
            print(f"最终视频: {result['concatenation']['output_path']}")
            print(f"总处理时间: {result['processing_time_seconds']:.2f} 秒")
        else:
            print(f"\n⚠️ 视频片段已生成但合并{result['concatenation']['status']}")
            if result['concatenation']['status'] == 'failed':
                print("请查看日志获取错误详情")
                
        return result


# 示例代码
if __name__ == "__main__":
    # 测试代码
    generator = NewsVideoGenerator(output_dir="output/news_videos")
    
    news_text = """
【AI日报】2025年06月04日
1. DeepSeek会在全球AI竞争中沉沦吗？
2025年1月20日，DeepSeek发布R1模型，部分性能可以追赶上当时最先进的大模型之一OpenAI o1模型，而且能做到完全开源，7天内用户增长至1亿，登顶中国和美国苹果应用商店。这一突破性进展标志着中国AI企业在全球竞争中的地位显著提升。
2. 估值432亿的全球龙头，英伟达投了
IBM、谷歌等多家公司在量子机器学习领域进行研究，探索量子算法提高数据处理效率和模型训练速度。量子计算能够处理更大的数据集，优化机器学习模型，从而在图像识别等领域实现突破。英伟达此次投资将进一步推动量子计算与AI的融合。
3. AI agent 和Agentic AI 到底有啥区别？康奈尔大学最新论文
康奈尔大学最新研究详细阐述了AI智能体与Agentic AI系统的核心区别。研究指出，Agentic AI系统代表了一种更高级的组织形式，能够像跨国公司一样协调多个AI智能体完成复杂任务，这为未来AI系统设计提供了新的方向。
4. 突破数据与算力孤岛：释放遥感基础模型潜力
最新研究提出突破数据与算力孤岛的方法，释放遥感基础模型在通用地球观测智能中的潜力。该技术将显著提升遥感数据处理效率，为环境监测、灾害预警等领域提供更强大的支持。
5. 可信数据空间等AI领域标准参编，探索北电数智的创新实践
北电数智积极参与AI行业相关标准制定，在数据要素流通与安全体系建设、算力与模型国产化技术突破及AIDC智算中心建设方面取得显著成果。这些实践为中国AI基础设施的自主可控发展提供了重要参考。
6. 水利标准AI大模型正式发布
由水利部国科司组织中国水科院自主研发的基于多源语料的"水利标准AI大模型"正式发布，标志着我国在水利标准化工具方面迈出了重要的一步。该模型将显著提升水利行业标准制定的效率和准确性。
7. 魏桥创业集团"智铝大模型"入选攻关项目
魏桥创业集团"智铝大模型"入选山东省工业领域行业大模型"揭榜挂帅"攻关项目名单。该项目将推动AI技术在铝业生产中的深度应用，提升生产效率和产品质量。
    """
    
    result = generator.generate_news_video(
        news_text=news_text,
        output_filename="ai_news_0530.mp4",
        use_multiprocessing=True,
        max_workers=6
    )
#外部调用示例
# from aigc.V2.main import NewsVideoGenerator

# # 创建生成器实例，可以指定输出目录
# generator = NewsVideoGenerator(output_dir="你的输出路径")

# # 准备新闻文本
# news_text = """
# 【AI日报】2025年06月04日
# 1. 人工智能研究取得重大突破，新型模型准确率提升30%
# 2. 全球科技巨头纷纷加大AI领域投资，市场竞争加剧
# """

# # 生成视频
# result = generator.generate_news_video(
#     news_text=news_text,           # 新闻内容
#     output_filename="daily_ai_news_0604.mp4",  # 输出文件名
#     chars_per_segment=30,          # 可选：每段字符数
#     max_audio_duration=5.0,        # 可选：最大音频时长
#     use_multiprocessing=True,      # 可选：是否使用多进程
#     max_workers=4,                 # 可选：最大进程数
#     add_subtitles=True,            # 可选：是否添加字幕
#     subtitle_format="srt"          # 可选：字幕格式
# )

# # 检查结果
# if result['concatenation']['status'] == 'success':
#     print(f"视频生成成功: {result['concatenation']['output_path']}")
# else:
#     print(f"视频生成失败或跳过: {result['concatenation']['reason']}")