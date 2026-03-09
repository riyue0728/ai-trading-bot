# ============================================
# 🔮 Antigravity Trading Bot - 核心配置文件
# ============================================

import os

# --- 1. TradingView 设置 ---
# 你的 "万能钥匙" (Session ID)
TRADINGVIEW_COOKIE = "nbizz42kdrbabk9r80e5a9q7z7gnlutx" 

# 默认图表地址（Webhook 不传 chart_url 时使用）
DEFAULT_CHART_URL = "https://cn.tradingview.com/chart/PP8uCQUu/" 

# 多品种图表配置
CHART_URLS = {
    "XAUUSD": "https://cn.tradingview.com/chart/PP8uCQUu/",  # 黄金
    "BTCUSD": "https://cn.tradingview.com/chart/AjeTUgRi/"    # 比特币
}

def get_chart_url(ticker):
    """获取品种对应的图表URL"""
    for key in CHART_URLS:
        if key in ticker.upper():
            return CHART_URLS[key]
    return DEFAULT_CHART_URL 

# --- 2. 企业微信 (WeChat Work) 设置 ---
WECHAT_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=dbf4f375-3c85-4050-b64d-0f862167be4c" 

# --- 3. AI 大脑设置 (双脑架构) ---

# [A] 视觉模型 (The Eyes) -
# 选项: "qwen" 负责看图 (通义千问), "gemini" (Google Gemini)
VISION_MODEL_PROVIDER = "gemini"    # 改为 gemini 使用 Google Gemini

# 通义千问配置
VISION_API_KEY = "sk-6abacc70e5024abb9c591547321a78f7"
VISION_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
VISION_ENDPOINT_ID = "qwen3-vl-plus"

# Google Gemini 配置
GEMINI_API_KEY = "AIzaSyCg-nQxEmFh5cAeb1V7OEOsErMKIv2u_j0"
GEMINI_MODEL = "gemini-3.1-pro-preview"  # 使用 3.1 版本

# [B] 逻辑模型 (The Brain) - 负责决策
LOGIC_MODEL_PROVIDER = "doubao"
LOGIC_API_KEY = "27ef94bd-bde2-4fbc-b060-57845559b0b4"
LOGIC_API_URL = "https://ark.cn-beijing.volces.com/api/v3"
LOGIC_ENDPOINT_ID = "ep-m-20260201094201-4465b"

# --- 4. 服务设置 ---
HOST = "0.0.0.0"
PORT = 80
DEBUG_MODE = True

# --- 5. 风控设置 ---
SIGNAL_DUPLICATE_TIME = 1800
