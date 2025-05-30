# 【AI日报】2025年05月22日

## 1. Google AI Studio升级开发者体验
Google宣布对其AI Studio平台进行重大升级，引入Gemini 2.5 Pro模型和代理工具，增强了多模态能力。这些改进使开发者能够构建更复杂的AI应用，特别是在代码生成和智能代理方面有显著提升。该更新直接面向开发者社区，体现了Google在AI基础设施领域的技术领先地位。

## 2. Google推出AI Mode搜索功能
Google正式推出AI Mode搜索功能，该功能能够为用户提供更详细和个性化的搜索结果。这项基于生成式AI的技术可以理解复杂查询，整合多源信息，并生成结构化回答。这标志着搜索引擎向更智能、更交互式的方向发展，可能改变用户获取信息的方式。

## 3. Volvo将率先在汽车中安装Google Gemini
Volvo宣布将成为首家在车辆中集成Google Gemini AI系统的汽车制造商。这项合作将使Volvo车主能够通过自然语言与车载系统交互，获得路线建议、车辆信息等服务。这体现了AI在汽车智能化方面的重要应用，也是Google将其AI技术扩展到新领域的战略举措。

curl -X POST https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 5cf8e2f7-8465-4ccc-bf84-e32f05be0fb4" \
  -d '{
    "model": "doubao-seedance-1-0-lite-i2v-250428",
    "content": [
        {
            "type": "text",
            "text": "女孩抱着狐狸，女孩睁开眼，温柔地看向镜头，狐狸友善地抱着，镜头缓缓拉出，女孩的头发被风吹动  --resolution 720p  --dur 10 --camerafixed false"
        },
        {
            "type": "image_url",
            "image_url": {
                "url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/i2v_foxrgirl.png"
            }
        }
    ]
}

echo "----- get request -----"
# 查询任务
curl -X GET https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{cgt-20250529141447-ctprx} \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 5cf8e2f7-8465-4ccc-bf84-e32f05be0fb4"