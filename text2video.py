import os
from volcenginesdkarkruntime import Ark

# 请确保您已将 API Key 存储在环境变量 ARK_API_KEY 中
# 初始化Ark客户端，从环境变量中读取您的API Key

client = Ark(
    # 此为默认路径，您可根据业务所在地域进行配置
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    # 直接设置API Key
    api_key="5cf8e2f7-8465-4ccc-bf84-e32f05be0fb4",
)


print("----- create request -----")
# 创建视频生成任务
create_result = client.content_generation.tasks.create(
     # 替换 <Model> 为模型的Model ID
    model="<Model>", 
    content=[
        {
            # 文本提示词与参数组合
            "type": "text",
            "text": "一位身穿绿色亮片礼服的女性站在粉红色背景前，周围飘落着五彩斑斓的彩纸  --dur 10"
        }
    ]
)
print(create_result)


print("----- get request -----")
# 获取任务详情
get_result = client.content_generation.tasks.get(task_id=create_result.id)
print(get_result)


print("----- list request -----")
# 列出符合特定条件的任务
list_result = client.content_generation.tasks.list(
    page_num=1,
    page_size=10,
    status="queued",  # 按状态筛选, e.g succeeded, failed, running, cancelled
    # model="<YOUR_MODEL_EP>, # 按 ep 筛选
    # task_ids=["test-id-1", "test-id-2"] # 按 task_id 筛选
)
print(list_result)


print("----- delete request -----")
# 通过任务 id 删除任务
try:
    client.content_generation.tasks.delete(task_id=create_result.id)
    print(create_result.id)
except Exception as e:
    print(f"failed to delete task: {e}")