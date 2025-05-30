project_root/
│
├─ prompt_builder.py          # 专门负责构造各种 LLM 提示词
├─ llm_client.py              # 封装 ChatOpenAI 调用，提供 invoke() 接口
├─ long_news_processor.py     # 核心流程：文本分段、生成多模态内容、合成视频
├─ video_concatenator.py      # 视频拼接器（原样保留）
└─ main.py                    # 用户入口：process_and_concatenate_news + CLI 示例