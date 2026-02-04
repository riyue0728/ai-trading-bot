# 知识库加载工具
import os

def load_knowledge_base():
    """
    加载知识库文件并合并成一个字符串
    返回: 完整的知识库文本
    """
    knowledge_dir = os.path.join(os.path.dirname(__file__), '..', 'knowledge')
    
    knowledge_text = ""
    
    # 读取各个知识文件
    files = ['chart_guide.md', 'chanlun_theory.md', 'trading_rules.md']
    
    for filename in files:
        filepath = os.path.join(knowledge_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                knowledge_text += f"\n\n{'='*50}\n"
                knowledge_text += f"[{filename.replace('.md', '')}]\n"
                knowledge_text += f"{'='*50}\n"
                knowledge_text += f.read()
        else:
            print(f"⚠️ 知识库文件不存在: {filename}")
    
    return knowledge_text

# 测试函数
if __name__ == "__main__":
    kb = load_knowledge_base()
    print("知识库加载完成:")
    print(kb[:500])  # 打印前500字符
