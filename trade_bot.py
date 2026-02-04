# ============================================
# 🤖 Antigravity Trade Bot - 中控系统
# ============================================

import time
import json
import logging
# Trigger Reload
from flask import Flask, request, jsonify

# 导入配置
try:
    import config
    print(f"✅ 成功加载配置. 视觉模型: {config.VISION_MODEL_PROVIDER}, 逻辑模型: {config.LOGIC_MODEL_PROVIDER}")
except ImportError:
    print("❌ 错误: 找不到 config.py，请确保文件都在 jiqiren/ 目录下")
    exit(1)

# 初始化 Web Server
app = Flask(__name__)

# 配置日志
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()])
logger = logging.getLogger(__name__)

# 全局变量 (暂存浏览器实例)
browser_instance = None

# --- V2.0 信号去重缓存 ---
SIGNAL_CACHE = {} # 格式: {"ticker_level_signal": timestamp}
CACHE_TTL = 120   # 2分钟内不重复处理同一信号

def is_duplicate_signal(data):
    """
    检查信号是否重复 (防止 TradingView 短时间内连发)
    """
    try:
        # 生成唯一指纹: 标的_周期_方向_价格(取整)
        # 例如: XAUUSD_5m_1buy_2050
        ticker = data.get('ticker', 'unknown')
        level = data.get('level', 'unknown') # 确保你的 JSON 里有 level 字段
        signal = data.get('signal', 'unknown')
        price = int(float(data.get('price', 0))) # 价格取整，忽略微小波动
        
        key = f"{ticker}_{level}_{signal}_{price}"
        now = time.time()
        
        # 清理过期缓存
        to_remove = [k for k, v in SIGNAL_CACHE.items() if now - v > CACHE_TTL]
        for k in to_remove:
            del SIGNAL_CACHE[k]
        
        if key in SIGNAL_CACHE:
            last_time = SIGNAL_CACHE[key]
            if now - last_time < CACHE_TTL:
                logger.warning(f"🚫 拦截重复信号: {key} (上次触发: {int(now-last_time)}秒前)")
                return True
        
        # 记录新信号
        SIGNAL_CACHE[key] = now
        return False
    except Exception as e:
        logger.error(f"⚠️ 去重逻辑出错: {e}")
        return False

@app.route('/')
def home():
    return "Antigravity Bot is Running! 🚀"

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    接收 TradingView 的 JSON 信号
    """
    try:
        # 1. 获取数据
        data = request.json
        if not data:
            # 兼容有些情况下可能是 form data
            data = json.loads(request.data)
            
        logger.info(f"📩 收到信号: {data.get('ticker')} - {data.get('signal')}")
        
        # --- V2.0 去重校验 ---
        if is_duplicate_signal(data):
            return jsonify({"status": "ignored", "message": "Duplicate signal"}), 200

        # 2. 校验数据完整性 (根据我们 Pine Script 定义的格式)
        # {"signal": "1买", "price": 5200, "chart_url": "..."}
        required_keys = ['signal', 'price', 'chart_url']
        if not all(key in data for key in required_keys):
            logger.warning(f"⚠️ 信号格式不完整: {data}")
            return jsonify({"status": "error", "message": "Missing keys"}), 400
            
        # 3. 核心处理逻辑 (异步执行，避免阻塞 TradingView)
        # 这里我们将调用 Vision + Logic 模块
        process_trade_signal(data)
        
        return jsonify({"status": "success", "message": "Signal received"}), 200

    except Exception as e:
        logger.error(f"❌ Webhook 处理错误: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


# 导入 Playwright
from playwright.sync_api import sync_playwright

def process_trade_signal(data):
    """
    处理交易信号的核心流程:
    1. 截图 (Vision)
    2. 分析 (Doubao/DeepSeek)
    3. 通知 (Feishu)
    """
    logger.info(">>> 开始处理信号流程...")
    
    # 步骤 A: 调用 Playwright 截图
    try:
        chart_url = data.get('chart_url')
        if not chart_url:
            chart_url = "https://cn.tradingview.com/chart/PP8uCQUu/" # Fallback
            
        screenshot_path = take_snapshot(chart_url)
        logger.info(f"📸 截图成功: {screenshot_path}")
    except Exception as e:
        logger.error(f"❌ 截图失败: {e}")
        return # 截图失败就不继续了
    
    # 步骤 B: 调用 视觉模型 (Qwen/Doubao) 分析图片
    vision_analysis = "截图分析失败"
    try:
        print(">>> 正在调用视觉模型...")
        vision_analysis = analyze_chart_image(screenshot_path)
        print("<<< 视觉分析完成")
    except Exception as e:
        print(f"❌ 视觉分析失败: {e}")
        logger.error(f"❌ 视觉分析失败: {e}")

    # 步骤 C: 调用 逻辑模型 (DeepSeek/Doubao) 决策
    final_decision = "决策失败"
    try:
        print(">>> 正在调用逻辑模型...")
        final_decision = make_trading_decision(data, vision_analysis)
        print("<<< 逻辑决策完成")
    except Exception as e:
        print(f"❌ 逻辑决策失败: {e}")
        logger.error(f"❌ 逻辑决策失败: {e}")
        final_decision = f"AI 决策出错: {e}"

    # 步骤 D: 发送企业微信通知 (带图片 + AI结论)
    try:
        print(">>> 正在发送企业微信...")
        send_wechat_alert(data, screenshot_path, ai_content=final_decision)
        print("<<< 企业微信发送完成")
    except Exception as e:
        logger.error(f"❌ 企微通知发送失败: {e}")
    
    logger.info("<<< 信号流程处理完毕.")

# ==========================================
# 🧠 AI 核心模块 (OpenAI SDK 兼容模式)
# ==========================================
from openai import OpenAI
import base64

def get_doubao_client():
    """获取火山引擎(豆包)的 OpenAI 兼容客户端"""
    return OpenAI(
        api_key=config.LOGIC_API_KEY, # 假设 Vision 和 Logic 用同一个 Key
        base_url="https://ark.cn-beijing.volces.com/api/v3",
    )

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analyze_chart_image(image_path):
    """
    [眼睛] 让 AI 看图
    """
    logger.info("👁️ 正在请求视觉模型分析截图...")
    client = get_doubao_client()
    base64_image = encode_image(image_path)
    
    # 提示词: 专注于缠论形态识别
    prompt = """
    你是一个缠论技术分析专家。请仔细阅读这张 K线图（包含缠论指标）：
    1. 识别当前的中枢结构（是否有中枢破坏？）。
    2. 识别笔和线段的走向。
    3. 观察 MACD 黄白线和红绿柱，判断是否有背驰（底背驰/顶背驰）。
    
    请用简练的语言描述你看到的形态。不要给出操作建议，只描述事实。
    """
    
    response = client.chat.completions.create(
        model=config.VISION_ENDPOINT_ID, # 你的视觉 Endpoint
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        },
                    },
                ],
            }
        ],
    )
    result = response.choices[0].message.content
    logger.info(f"👁️ 视觉分析完成: {result[:50]}...")
    return result

def make_trading_decision(signal_data, vision_analysis):
    """
    [大脑] 结合 信号数据 + 视觉描述 -> 做出决策
    """
    logger.info("🧠 正在请求逻辑模型进行决策...")
    client = get_doubao_client()
    
    system_prompt = """
    你是一个严格执行“缠论”交易系统的量化交易决策引擎。
    你需要综合以下信息做出判断：
    1. TradingView 的硬信号（几买/几卖，价格，级别）。
    2. 视觉模型的看图描述（形态，背驰情况）。
    
    你的输出必须包含：
    【决策】：买入 / 卖出 / 观望
    【理由】：简述缠论依据（如：5分钟底背驰共振，区间套确认）。
    【风险】：当前主要风险点。
    """
    
    user_prompt = f"""
    【信号数据】：{json.dumps(signal_data, ensure_ascii=False)}
    【视觉分析】：{vision_analysis}
    
    请输出你的最终决策。
    """
    
    response = client.chat.completions.create(
        model=config.LOGIC_ENDPOINT_ID, # 你的逻辑 Endpoint (Doubao-Seed-1.8)
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    result = response.choices[0].message.content
    logger.info(f"🧠 逻辑决策完成: {result[:50]}...")
    return result

# ==========================================
# 🔔 通知模块 (更新版)
# ==========================================

def send_wechat_alert(data, image_path, ai_content=None):
    """
    发送企业微信通知 (文本 + 图片)
    """
    webhook_url = config.WECHAT_WEBHOOK_URL
    if not webhook_url:
        logger.warning("⚠️ 未配置企业微信 Webhook，跳过发送")
        return

    import requests
    import base64
    import hashlib

    # 1. 发送文字概览 (包含 AI 决策)
    text_content = f"""🚀 缠论信号触发
----------------
标的: {data.get('ticker')}
方向: {data.get('signal')} ({'买' if data.get('direction') == 'buy' else '卖'})
价格: {data.get('price')}
级别: {data.get('level')}"""

    if ai_content:
        # 截断过长的 AI 内容，防止超过企业微信限制 (2048字节)
        if len(ai_content) > 600:
            ai_content = ai_content[:600] + "\n...(内容过长已截断)"
        text_content += f"\n\n🤖 AI 决策报告:\n{ai_content}"
    else:
        text_content += "\n\n(AI 尚未介入)"
    
    # Debug: 打印最终发送的文本长度
    print(f"DEBUG: 文本长度: {len(text_content)}")

    try:
        resp1 = requests.post(webhook_url, json={
            "msgtype": "text",
            "text": {"content": text_content}
        })
        print(f"DEBUG: 企微文本响应: {resp1.text}")
    except Exception as e:
        print(f"❌ 企微文本发送挂了: {e}")

    # 2. 发送图片 (Base64模式)
    try:
        with open(image_path, "rb") as f:
            img_content = f.read()
            
        # 企微要求: Base64编码 和 MD5值
        base64_data = base64.b64encode(img_content).decode('utf-8')
        md5_val = hashlib.md5(img_content).hexdigest()
        
        img_payload = {
            "msgtype": "image",
            "image": {
                "base64": base64_data,
                "md5": md5_val
            }
        }
        
        resp = requests.post(webhook_url, json=img_payload)
        print(f"DEBUG: 企微图片响应: {resp.text}")
        
        if resp.json().get('errcode') == 0:
            logger.info("✅ 企微图片已发送")
        else:
            logger.error(f"❌ 企微图片发送失败: {resp.text}")
            
    except Exception as e:
        logger.error(f"❌ 图片处理异常: {e}")

def take_snapshot(url):
    """
    启动浏览器并截图
    """
    timestamp = int(time.time())
    filename = f"snapshot_{timestamp}.png"
    
    logger.info(f"🚀 正在启动浏览器访问: {url}")
    
    with sync_playwright() as p:
        # 1. 启动 (复用 verify_login.py 的配置)
        browser = p.chromium.launch(headless=False, channel="chrome", args=["--start-maximized"])
        
        # 2. 上下文 (Zoom 0.75)
        context = browser.new_context(viewport=None, device_scale_factor=0.75)
        
        # 3. 注入 Cookie
        context.add_cookies([{
            "name": "sessionid",
            "value": config.TRADINGVIEW_COOKIE,
            "domain": ".tradingview.com",
            "path": "/"
        }])
        
        # 4. 打开页面
        page = context.new_page()
        page.goto(url)
        
        # 5. 等待加载 (等待7秒，平衡速度与加载完整性)
        logger.info("⏳ 等待页面渲染 (7s)...")
        time.sleep(7)
        
        # 6. 截图
        page.screenshot(path=filename)
        
        browser.close()
        
    return filename

if __name__ == '__main__':
    print(f"🚀 Antigravity Bot 启动成功! 正在监听: http://{config.HOST}:{config.PORT}/webhook")
    print("提示: 这只是本地服务器，请确保 TradingView 警报能访问到此地址 (需要内网穿透) 或者你在本机用 Postman 测试。")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG_MODE)
