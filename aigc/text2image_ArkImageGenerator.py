import os
import requests
from datetime import datetime
from volcenginesdkarkruntime import Ark
from typing import Optional, List

class ArkImageGenerator:
    def __init__(self, api_key: str = None, base_url: str = "https://ark.cn-beijing.volces.com/api/v3"):
        """初始化方舟SDK图像生成器
        
        Args:
            api_key (str, optional): API密钥，如果为None则从环境变量ARK_API_KEY中读取
            base_url (str, optional): API基础URL
        """
        if api_key is None:
            api_key = os.environ.get("ARK_API_KEY", "5cf8e2f7-8465-4ccc-bf84-e32f05be0fb4")
        
        self.client = Ark(
            base_url=base_url,
            api_key=api_key,
        )
    
    def generate(self, prompt: str, model: str = "doubao-seedream-3-0-t2i-250415", 
                 output_dir: str = "output/ark_images", filename: Optional[str] = None) -> List[str]:
        """生成图像并保存
        
        Args:
            prompt (str): 图像生成提示词
            model (str, optional): 使用的模型名称
            output_dir (str, optional): 输出目录
            filename (str, optional): 文件名，不包含扩展名。如果为None则使用时间戳
            
        Returns:
            List[str]: 保存的图像文件路径列表
        """
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成图像
        response = self.client.images.generate(
            model=model,
            prompt=prompt,
        )
        
        saved_paths = []
        
        # 下载并保存每张图像
        for i, image_data in enumerate(response.data):
            image_url = image_data.url
            
            # 下载图像
            image_response = requests.get(image_url)
            if image_response.status_code != 200:
                print(f"下载图像失败: {image_response.status_code}")
                continue
            
            # 生成文件名
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if len(response.data) > 1:
                    file_path = os.path.join(output_dir, f"image_{timestamp}_{i}.png")
                else:
                    file_path = os.path.join(output_dir, f"image_{timestamp}.png")
            else:
                if len(response.data) > 1:
                    file_path = os.path.join(output_dir, f"{filename}_{i}.png")
                else:
                    file_path = os.path.join(output_dir, f"{filename}.png")
            
            # 保存图像
            with open(file_path, 'wb') as f:
                f.write(image_response.content)
            
            print(f"图像已保存至: {file_path}")
            saved_paths.append(file_path)
        
        return saved_paths
    
    def get_available_models(self):
        """获取可用的模型列表
        
        Returns:
            list: 可用模型列表
        """
        # 注意：此功能取决于API是否支持获取模型列表
        # 这里返回一个已知的模型列表
        return ["doubao-seedream-3-0-t2i-250415"]

# 使用示例
if __name__ == "__main__":
    # 创建图像生成器对象
    generator = ArkImageGenerator()
    
    # 生成图像的提示词
    prompt = """一幅以Google AI Studio新闻发布会为主题的科技发布会，场景为正式的发布会舞台，
    背景展示巨大的屏幕，上面显示Gemini 2.5 Pro模型、多模态能力和智能代理工具的相关信息。"""
    
    # 生成并保存图像
    image_paths = generator.generate(prompt)
    
    print(f"生成的图像文件路径: {image_paths}")