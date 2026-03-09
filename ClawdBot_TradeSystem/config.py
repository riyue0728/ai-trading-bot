# ============================================
# 🔮 Antigravity Trading Bot - 核心配置文件
# ============================================

import os

# --- 1. TradingView 设置 ---
# 你的 "万能钥匙" (Session ID)
# 获取方式: 浏览器 -> F12 -> Application -> Cookies -> sessionid
TRADINGVIEW_COOKIE = "nbizz42kdrbabk9r80e5a9q7z7gnlutx" 

# 默认图表地址
DEFAULT_CHART_URL = "https://cn.tradingview.com/chart/PP8uCQUu/"

# 默认浏览器窗口大小 (无需修改)
BROWSER_WIDTH = 1920
BROWSER_HEIGHT = 1080
BROWSER_ZOOM = 0.75  # 0.75 表示缩小到 75% 以获得更大视野

# 浏览器运行模式
# True = 后台静默运行 (服务器模式) | False = 弹窗显示 (调试模式)
BROWSER_HEADLESS = True 
# True = 使用本机 Chrome | False = 使用 Playwright 自带 Chromium (服务器模式)
USE_LOCAL_CHROME = False

# --- 2. 企业微信 (WeChat Work) 设置 ---
# 你的企业微信群机器人 Webhook 地址
# 获取方式: 企业微信群 -> 右上角三个点 -> 添加群机器人 -> 复制 Webhook
WECHAT_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=dbf4f375-3c85-4050-b64d-0f862167be4c" 

# --- 3. AI 大脑设置 (双脑架构) ---

# [A] 视觉模型 (The Eyes) - 负责看图
# 当前: Qwen3-VL-Plus (通义千问) / 备用: Doubao-Seed-1.6-vision
VISION_MODEL_PROVIDER = "qwen"    # 选项: "qwen", "doubao"
VISION_API_KEY = "sk-6abacc70e5024abb9c591547321a78f7"    # 通义千问 API Key
VISION_ENDPOINT_ID = "qwen3-vl-plus"  # 模型名称

# 通义千问配置
QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_API_KEY = "sk-6abacc70e5024abb9c591547321a78f7"
QWEN_MODEL = "qwen3-vl-plus"

# [B] 逻辑模型 (The Brain) - 负责决策 & RAG
# 当前: DeepSeek-V3 (最强逻辑)
# 备用: GLM-4.7 (ep-m-20260201094257-n7hkp) | Kimi-K2 (ep-m-20260201095404-b5nhr)
LOGIC_MODEL_PROVIDER = "doubao"   # 选项: "deepseek", "doubao", "minimax", "openai" (火山引擎托管统称 doubao)
LOGIC_API_KEY = "27ef94bd-bde2-4fbc-b060-57845559b0b4"     # (通常和上面同一个Key)
LOGIC_ENDPOINT_ID = "ep-m-20260201094201-4465b" # DeepSeek-V3

# --- 4. 服务设置 ---
HOST = "0.0.0.0"
PORT = 5001
DEBUG_MODE = True
