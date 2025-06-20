# -*- coding: utf-8 -*-
from long_news_processor import LongNewsProcessor
from video_concatenator import VideoConcatenator

def process_and_concatenate_news(news_text, project_name=None, auto_concatenate=True):
    processor = LongNewsProcessor(
        max_chars_per_segment=25,
        max_audio_duration=4.8
    )
    result = processor.process_long_news(
        news_text,
        project_name=project_name,
        calibrate=True,
        add_subtitles=True,
        subtitle_format="srt"
    )

    segments_dir = result['output_directory']
    seg_count = result['successful_segments']
    print(f"生成视频片段 {seg_count} 个，目录：{segments_dir}")

    if auto_concatenate and seg_count > 0:
        concatenator = VideoConcatenator(output_dir="output/concatenated")
        video = concatenator.auto_concatenate(
            search_dir=segments_dir,
            output_filename=f"{project_name}_complete.mp4" if project_name else None,
            pattern="*_final.mp4",
            force_reencode=False
        )
        status = 'success' if video else 'failed'
        result['concatenation'] = {
            'status': status,
            'output_path': video
        }
    else:
        result['concatenation'] = {'status': 'skipped'}

    return result

if __name__ == "__main__":
    # （此处放之前的示例 long_news 文本并调用 process_and_concatenate_news）
    long_news = """
【AI日报】2025年05月30日
1. 企业级AI战略加速落地！传微软与巴克莱银行签订10万份Copilot许可证
微软在全员大会上展示企业级AI业务进展，其中与巴克莱银行达成的10万份Copilot许可证交易成为焦点。这一合作标志着企业级AI应用的快速落地，预计将推动更多金融机构采用AI技术，对行业具有变革性影响。
2. 不只是"小升级"！DeepSeek-R1新版获海外盛赞
DeepSeek最新发布的R1模型升级版在全球AI领域掀起热议，多位国际科技大佬及行业高管盛赞其技术突破。实测显示该模型在多项基准测试中表现优异，标志着中国AI公司在技术上的重大进步。
3. 云从科技多模态大模型「CongRong-v2.0」登顶全球榜单
云从科技自主研发的「从容大模型」在国际评测平台OpenCompass最新全球多模态榜单中，以80.7分的综合成绩登顶榜首。这一成绩标志着中国在多模态AI领域的技术实力获得国际认可。
4. 微软开源Aurora AI气象模型
微软开源Aurora AI气象模型，该模型结合深度学习技术，能够实现精准气象预报，目前已在MSN天气应用中投入使用。同时腾讯也开源了混元语音数字人模型，显示AI开源生态持续发展。
5. 字节跳动内部禁用Cursor等AI编程工具，用旗下Trae作为替代
字节跳动宣布内部将禁用Cursor等第三方AI编程工具，转而使用自研的Trae工具。Trae搭载基座大模型doubao-1.5-pro，支持切换DeepSeek R1&V3，是国内首个AI原生IDE工具。
6. ICLR 2025 | LLaVA-MoD：MoE蒸馏训练轻量化多模态大模型
研究团队提出轻量化多模态大模型LLaVA-MoD，通过集成稀疏专家混合(MoE)架构优化模型结构，并设计两阶段蒸馏策略，在保持性能的同时显著减小模型规模，为多模态应用提供新方案。
7. 对标Coze和Dify，Java开发的AIFlowy v1.0.4发布
AIFlowy是基于Java开发的企业级开源AI应用开发平台，致力于为中国开发者和企业提供高效、本土化的AI工具，功能上对标字节Coze和腾讯Dify等平台，推动国内AI开发生态发展。
    """
    
    # Process and concatenate
    result = process_and_concatenate_news(
        news_text=long_news,
        project_name="ai_news_demo",
        auto_concatenate=True
    )
    
    # Print results
    if result['concatenation']['status'] == 'success':
        print(f"\n✅ Complete process successful!")
        print(f"Final video: {result['concatenation']['output_path']}")
    else:
        print(f"\n⚠️ Video segments generated but concatenation {result['concatenation']['status']}")
        if result['concatenation']['status'] == 'failed':
            print("Check logs for error details")