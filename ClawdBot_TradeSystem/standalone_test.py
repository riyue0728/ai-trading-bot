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
import os

# 加载知识库
def load_knowledge_base():
    """加载 knowledge/ 目录下的所有知识文件"""
    kb_dir = os.path.join(os.path.dirname(__file__), '..', 'knowledge')
    knowledge = ""
    for filename in ['chart_guide.md', 'chanlun_theory.md', 'trading_rules.md']:
        filepath = os.path.join(kb_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                knowledge += f"\n\n### {filename} ###\n{f.read()}"
    return knowledge

KNOWLEDGE_BASE = load_knowledge_base()  # 启动时加载一次

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
    [眼睛] 视觉分析 - 提取结构化数据
    """
    logger.info("👁️ 正在请求视觉模型提取结构化数据...")
    client = get_doubao_client()
    base64_image = encode_image(image_path)
    
    # 提示词: 强制输出 12 个核心字段的 JSON
    prompt = f"""
    你是一个缠论技术分析专家。请仔细阅读这张 K线图，严格按照以下要求提取数据，不要输出任何废话，只输出标准 JSON。
    
    参考知识库颜色定义：
    {KNOWLEDGE_BASE}
    
    【提取要求】
    请提取以下 12 个核心字段，组成 JSON 返回：
    1. "交易品种": 例如 XAUUSD
    2. "分析周期": 例如 25分钟
    3. "当前最新价格": 数值
    4. "整体趋势": 上涨/下跌/震荡
    5. "缠论核心信号": 底背驰/顶背驰/无背驰（标注依据）
    6. "走势结构": 下跌延伸段/上涨延伸段/中枢震荡（标注中枢区间）
    7. "最近前低支撑位": [价格1, 价格2]
    8. "最近前高压力位": [价格1, 价格2]
    9. "关键分水岭价位": 数值（趋势反转点）
    10. "次一级支撑位": 数值（止损参考）
    11. "次一级压力位": 数值（止盈/止损参考）
    12. "短期小压力支撑": 数值（目标位）
    13. "屏幕文字信号": 提取图中出现的所有关键文字，特别是左下角的信号提示（如"次级别底标准趋势背驰"、"1预期"、"本级别"等），以及K线附近的文字标注。
    14. "最后一个买卖点": 明确指出图中最右侧出现的最后一个买卖点类型（1/2/3买卖点）以及是否带有"预期"字样。
    
    务必确保返回的是合法的 JSON 格式。
    """
    
    response = client.chat.completions.create(
        model=config.VISION_ENDPOINT_ID, 
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                ],
            }
        ],
    )
    result = response.choices[0].message.content
    logger.info(f"👁️ 视觉提取完成: {result[:100]}...")
    return result

def make_trading_decision(signal_data, vision_json):
    """
    [大脑] 逻辑决策 - 复刻人工分析逻辑 (Seed-1.8)
    """
    logger.info("🧠 正在请求逻辑模型进行精准分析...")
    client = get_doubao_client()
    
    # 缠论量化规则
    chanlun_rules = """
    ### 缠论核心量化规则：
    1. 一买（底）：下跌趋势+底背驰信号+价格回踩最近前低支撑位且不再创新低；
    2. 二买（底）：下跌趋势后，价格突破关键分水岭价位+回踩分水岭下方且不跌破前低；
    3. 一卖（顶）：上涨趋势+顶背驰信号+价格反弹最近前高压力位且不再创新高；
    4. 二卖（顶）：上涨趋势后，价格跌破关键分水岭价位+反抽分水岭上方且不突破前高；
    5. 背驰后操作逻辑：底背驰优先低多博弈反弹，顶背驰优先高空博弈回落，震荡趋势不做单边；
    6. 止损逻辑：多单止损=最近前低支撑位下方10-20个点，空单止损=最近前高压力位上方10-20个点；
    7. 止盈逻辑：短期止盈=次一级压力/支撑位，波段止盈=最近前高/前低压力/支撑位；
    8. 级别定义："本级别"信号代表当前周期（如25m）的确认信号，权重高；"次级别"信号代表小级别（如5m/1m）的共振信号，适合提前入场但风险稍高；
    9. 预期信号："1预期"/"2预期"代表买卖点尚未完全确认（分型未定），属于激进左侧信号，必须提示需等待底分型/顶分型确认；
    10. 信号矛盾处理：若指标产生"卖点"信号（如底背驰卖），但结构显示应"低多"（如底背驰），请明确解释并【纠正信号名称】：将"次级别底盘整背驰(卖)"纠正为"本级别底背驰(多)"，避免方向混淆。
    11. 价格精度：给出的支撑/压力建议区间必须精确，尽量控制在10-15个点差以内。对于"二买"区域，应结合当前中枢震荡范围（如4700-4750），不要脱离实际走势。
    12. 做空特例：做空触发条件必须严格——反弹至压力位 + 顶分型 + 次级别（如5m）顶背驰共振，方可做空。
    13. 入场理由增强：对于"激进试多"区间，必须补充技术依据，例如"0.382回撤位"、"5日/10日均线支撑"等，增加说服力。
    """
    
    # 系统提示词 (Seed-1.8 专属)
    system_prompt = f"""
    请你作为专业的缠论交易分析师，严格按照缠论规则，基于以下行情结构化数据，进行精准分析。
    
    {chanlun_rules}
    
    分析结果必须严格包含以下4个模块，直接用于交易决策：
    
    1. 大周期方向判断：
       - 当前走势
       - 缠论结构
       - 信号解读（区分"本级别"与"次级别"，区分"确认"与"预期"）
       - 方向指引（明确趋势+信号的动能解读+核心操作方向）
       
    2. 买卖点与入场位：
       - 多单入场点（明确一买/二买，具体价位区间）
       - 空单入场点（明确一卖/二卖，具体价位区间）
       
    3. 止损与止盈建议：
       - 多单止损/止盈（基于结构支撑压力）
       - 空单止损/止盈（特例：反弹至压力位+顶分型+次级别顶背驰共振）
       
    4. 综合操作建议：
       - 明确优先操作方向
       - 用✅标注核心建议
       - 避免模棱两可，必须给出明确倾向

    5. 未来走势推演 (Next Move)：
       - 识别当前状态：当前是一笔上涨还是一笔下跌？
       - 预判下一笔：如果是上涨笔，关注回调是否形成2买/3买/中枢震荡？如果是下跌笔，关注反弹是否形成2卖/3卖？
       - 预判下一个买卖点：基于当前结构，推演下一个最可能出现的买卖点类型（例如：若不破前低，将形成二买）。
    """
    
    # 用户输入
    user_prompt = f"""
    【交易信号数据】：{json.dumps(signal_data, ensure_ascii=False)}
    
    【视觉结构化数据】：
    {vision_json}
    
    请输出你的最终决策分析报告。
    """
    
    response = client.chat.completions.create(
        model=config.LOGIC_ENDPOINT_ID, # Doubao-Seed-1.8
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
        # 截断过长的 AI 内容 (企业微信限制)
        # 我们的新报告比较长，放宽到 1800 字符试试
        if len(ai_content) > 1800:
            ai_content = ai_content[:1800] + "\n...(内容过长已截断)"
        text_content += f"\n\n📝 缠论深度复盘:\n{ai_content}"
    else:
        text_content += "\n\n(AI 尚未介入)"
    
    # Debug: 打印最终发送的文本长度
    print(f"DEBUG: 文本长度: {len(text_content)}")

    # 创建无代理的 Session
    session = requests.Session()
    session.trust_env = False

    try:
        resp1 = session.post(webhook_url, json={
            "msgtype": "text",
            "text": {"content": text_content}
        })
        print(f"DEBUG: 企微文本响应: {resp1.text}")
    except Exception as e:
        print(f"❌ 企微文本发送挂了: {e}")
        logger.error(f"❌ 企微文本发送异常: {e}")

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
        
        resp = session.post(webhook_url, json=img_payload)
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
        # 1. 启动 (根据 config.py 配置动态调整)
        launch_args = {
            "headless": config.BROWSER_HEADLESS,
            "args": ["--start-maximized"]
        }
        
        # 如果配置了使用本机 Chrome (仅限本地调试)
        if config.USE_LOCAL_CHROME:
            launch_args["channel"] = "chrome"
            
        logger.info(f"⚙️ 浏览器启动参数: Headless={config.BROWSER_HEADLESS}, Channel={'Chrome' if config.USE_LOCAL_CHROME else 'Bundled Chromium'}")
        browser = p.chromium.launch(**launch_args)
        
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
