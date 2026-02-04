import os
from dotenv import load_dotenv

# 加载 .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# FastAPI
FASTAPI_HOST = os.getenv("FASTAPI_HOST", "0.0.0.0")
FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8000"))

# 通知 (企业微信)
WECHAT_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK")

# AI - Vision
VISION_API_KEY = os.getenv("QWEN_VL_API_KEY")
VISION_API_URL = os.getenv("QWEN_VL_API_URL")
VISION_ENDPOINT = os.getenv("VISION_ENDPOINT_ID")

# AI - Logic
LOGIC_API_KEY = os.getenv("DEEPSEEK_API_KEY")
LOGIC_API_URL = os.getenv("DEEPSEEK_API_URL")
LOGIC_ENDPOINT = os.getenv("LOGIC_ENDPOINT_ID")

# Playwright
TRADINGVIEW_COOKIE = os.getenv("TV_COOKIE")
SCREENSHOT_TIMEOUT = int(os.getenv("SCREENSHOT_TIMEOUT", 30))
SCREENSHOT_RETRY = int(os.getenv("SCREENSHOT_RETRY", 3))

# 风控
SIGNAL_DUPLICATE_TIME = int(os.getenv("SIGNAL_DUPLICATE_TIME", 120))
