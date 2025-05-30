import os
# 通过 pip install 'volcengine-python-sdk[ark]' 安装方舟SDK
from volcenginesdkarkruntime import Ark

# 请确保您已将 API Key 存储在环境变量 ARK_API_KEY 中
# 初始化Ark客户端，从环境变量中读取您的API Key
client = Ark(
    # 此为默认路径，您可根据业务所在地域进行配置
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    # 从环境变量中获取您的 API Key。此为默认方式，您可根据需要进行修改
    api_key="5cf8e2f7-8465-4ccc-bf84-e32f05be0fb4",
)

imagesResponse = client.images.generate(
    model="doubao-seedream-3-0-t2i-250415",
    prompt="""一幅以Google AI Studio新闻发布会为主题的科技发布会，场景为正式的发布会舞台，背景展示巨大的屏幕，上面显示Gemini 2.5 Pro模型、多模态能力和智能代理工具的相关信息。"""
)

print(imagesResponse.data[0].url)