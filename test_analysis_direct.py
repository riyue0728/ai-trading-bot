#!/usr/bin/env python3
"""
直接测试 AI 分析功能的脚本
用法: python test_analysis_direct.py [图片路径]
"""

import sys
import os
import json
from openai import OpenAI

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ClawdBot_TradeSystem.src import config, utils

def test_analysis(image_path=None):
    """测试 AI 分析"""
    print("=" * 60)
    print("🧪 直接测试 AI 分析功能")
    print("=" * 60)
    
    # 1. 如果有图片，测试图片分析
    if image_path and os.path.exists(image_path):
        print(f"📸 测试图片: {image_path}")
        print("-" * 60)
        
        # 编码图片
        base64_image = utils.encode_image(image_path)
        
        # 获取客户端
        provider = getattr(config, 'VISION_MODEL_PROVIDER', 'doubao').lower()
        if provider == 'qwen':
            client = utils.get_qwen_client()
            model_id = getattr(config, 'QWEN_MODEL', 'qwen3-vl-plus')
        else:
            client = utils.get_doubao_client()
            model_id = getattr(config, 'VISION_ENDPOINT_ID', config.VISION_ENDPOINT_ID)
        
        print(f"🤖 使用模型: {model_id}")
        print("⏳ AI 分析中...")
        
        # 调用 AI
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": utils.ANALYSIS_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                ]}
            ],
        )
        
        result = response.choices[0].message.content
        print("-" * 60)
        print("📊 AI 分析结果:")
        print(result)
        
        # 尝试解析 JSON
        try:
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                json_result = json.loads(json_match.group())
                print("-" * 60)
                print("✅ JSON 解析成功:")
                print(json.dumps(json_result, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"⚠️ JSON 解析失败: {e}")
    
    # 2. 如果没有图片，打印 prompt 内容
    else:
        print("📄 测试 Prompt 内容（没有提供图片）:")
        print("-" * 60)
        print(f"Prompt 长度: {len(utils.ANALYSIS_PROMPT)} 字符")
        print("Prompt 前 500 字符:")
        print(utils.ANALYSIS_PROMPT[:500])
        print("...")
    
    print("=" * 60)
    print("🧪 测试完成")
    print("=" * 60)

if __name__ == "__main__":
    import re
    
    # 检查参数
    if len(sys.argv) > 1:
        test_analysis(sys.argv[1])
    else:
        test_analysis()
