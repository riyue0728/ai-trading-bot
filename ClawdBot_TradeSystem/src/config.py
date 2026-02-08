# ============================================
# 🔮 Antigravity Trading Bot - 核心配置文件
# ============================================

import os

# --- 1. TradingView 设置 ---
# 你的 "万能钥匙" (Session ID)
# 获取方式: 浏览器 -> F12 -> Application -> Cookies -> sessionid
TRADINGVIEW_COOKIE = "nbizz42kdrbabk9r80e5a9q7z7gnlutx" 

# --- 2. 企业微信 (WeChat Work) 设置 ---
WECHAT_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=dbf4f375-3c85-4050-b64d-0f862167be4c" 

# --- 3. AI 大脑设置 (双脑架构) ---

# [A] 视觉模型 (The Eyes) - 负责看图
# 选项: "qwen" (通义千问), "gemini" (Google Gemini)
VISION_MODEL_PROVIDER = "gemini"    # 改为 gemini 使用 Google Gemini

# 通义千问配置
VISION_API_KEY = "sk-6abacc70e5024abb9c591547321a78f7"
VISION_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
VISION_ENDPOINT_ID = "qwen3-vl-plus"

# Google Gemini 配置
GEMINI_API_KEY = "AIzaSyCQJn7WmqffRstHT5D0ZxKx1vEytPK5LQk"
GEMINI_MODEL = "gemini-2.5-flash"  # 免费额度充足

# [B] 逻辑模型 (The Brain) - 负责决策
LOGIC_MODEL_PROVIDER = "doubao"
LOGIC_API_KEY = "27ef94bd-bde2-4fbc-b060-57845559b0b4"
LOGIC_API_URL = "https://ark.cn-beijing.volces.com/api/v3"
LOGIC_ENDPOINT_ID = "ep-m-20260201094201-4465b"

# --- 4. 服务设置 ---
HOST = "0.0.0.0"
PORT = 5001
DEBUG_MODE = True

# --- 5. 风控设置 ---
SIGNAL_DUPLICATE_TIME = 1800
