import time
import os
import logging
import base64
import hashlib
import requests
from playwright.sync_api import sync_playwright
from openai import OpenAI
from . import config

# 配置日志
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, f"bot_{time.strftime('%Y%m%d')}.log"), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ClawdBot")

def get_doubao_client():
    """获取火山引擎 OpenAI 兼容客户端"""
    return OpenAI(
        api_key=config.LOGIC_API_KEY,
        base_url=config.LOGIC_API_URL,
    )

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# --- Playwright 截图 (支持单图 & 多周期) ---

def _take_single_snapshot_page(context, url, filename):
    """
    内部函数：在给定上下文中打开页面并截图
    """
    page = context.new_page()
    logger.info(f"🚀 打开页面: {url}")
    page.goto(url, timeout=config.SCREENSHOT_TIMEOUT * 1000)
    
    # 等待加载
    logger.info("⏳ 等待页面渲染 (7s)...")
    time.sleep(7)
    
    # 像素校验 (V2.0 健壮性)
    # 简单检查是否白屏 (这里暂略，先保证基本功能)
    
    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'screenshots', filename)
    page.screenshot(path=output_path)
    logger.info(f"📸 截图保存: {filename}")
    page.close()
    return output_path

def capture_single_snapshot(url, symbol):
    """
    单周期截图 (兼容旧逻辑)
    """
    timestamp = int(time.time())
    filename = f"{symbol.replace('/','_')}_{timestamp}.png"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=0.75)
        # 注入 Cookie
        if config.TRADINGVIEW_COOKIE:
            context.add_cookies([{
                "name": "sessionid",
                "value": config.TRADINGVIEW_COOKIE,
                "domain": ".tradingview.com",
                "path": "/"
            }])
            
        path = _take_single_snapshot_page(context, url, filename)
        browser.close()
        return path

def capture_multi_timeframe(base_url, symbol, timeframes=["1", "5", "25"]):
    """
    [多周期共振核心] 同时截取 1m, 5m, 25m 的图表
    base_url: TradingView的基础图表URL (不带 interval 参数)
    注意: 需要确保 URL 支持通过传参切换周期，或者我们手动拼接 URL
    TradingView URL 规则: /chart/LayoutID/?symbol=BTCUSDT&interval=5
    """
    timestamp = int(time.time())
    paths = []
    
    logger.info(f"🔥 触发多周期截图: {symbol} -> {timeframes}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=0.75)
        
        if config.TRADINGVIEW_COOKIE:
            context.add_cookies([{
                "name": "sessionid",
                "value": config.TRADINGVIEW_COOKIE,
                "domain": ".tradingview.com",
                "path": "/"
            }])
            
        # 并行截图逻辑: 
        # 简单起见，我们这里先顺序执行，因为 Python Playwright sync API 是同步的。
        # 如果要极致速度，可以用 async API。这里顺序执行差距也就几秒，完全可接受。
        
        for tf in timeframes:
            # 构造 URL (假设传入的 url 是基础 layout url)
            # 自动拼接 interval 参数
            # 注意: 请确保 symbol 和 interval 参数正确追加
            # 简单处理: 我们假设 base_url 已经包含了 symbol，只需要改 interval
            # TradingView 改周期通常是在 UI 上点，或者 URL 参数 &interval=5
            
            target_url = f"{base_url}&interval={tf}" 
            if "?" not in base_url:
                target_url = f"{base_url}?interval={tf}"
            else:
                target_url = f"{base_url}&interval={tf}"
                
            filename = f"{symbol.replace('/','_')}_{tf}m_{timestamp}.png"
            path = _take_single_snapshot_page(context, target_url, filename)
            paths.append(path)
            
        browser.close()
        
    return paths

# --- AI 调用 ---

def analyze_multi_images(image_paths):
    """
    [视觉] 同时看多张图，或分别看图后汇总
    V1策略: 分别分析，返回分析列表
    """
    results = {}
    client = get_doubao_client()
    
    prompt = """
    你是一个缠论技术分析专家。
    请识别当前K线图的：
    1. 中枢结构。
    2. 笔和线段走向。
    3. MACD背驰情况。
    简练描述事实。
    """
    
    for path in image_paths:
        # 解析文件名获取周期 (假设文件名包含 _1m_ )
        tf = "unknown"
        if "_1m_" in path: tf = "1m"
        elif "_5m_" in path: tf = "5m"
        elif "_25m_" in path: tf = "25m"
        
        logger.info(f"👁️ 正在分析 {tf} 周期...")
        base64_image = encode_image(path)
        
        response = client.chat.completions.create(
            model=config.VISION_ENDPOINT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"这是 {tf} 级别的图表。{prompt}"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                    ],
                }
            ],
        )
        results[tf] = response.choices[0].message.content
        
    return results

def make_resonance_decision(signal_data, vision_results):
    """
    [大脑] 多周期共振决策
    """
    logger.info("🧠 正在进行多周期共振思考...")
    client = get_doubao_client()
    
    system_prompt = """
    你是一个执行“缠论多周期共振”策略的交易决策引擎。
    规则：
    1. 【1m 信号周期】：必须满足背驰 + 买卖点形态。
    2. 【5m 次级别】：趋势不能反向（如做多时，5m不能是单边下跌）。
    3. 【25m 大级别】：必须在支撑/压力位，且无大级别反向背驰。
    
    请输出标准 JSON：
    {
        "decision": "STRONG_BUY/WEAK_BUY/WAIT/SELL",
        "reason": "简述三周期共振情况",
        "risk": "风险点",
        "position": 5 (建议仓位%)
    }
    """
    
    user_prompt = f"""
    【原始信号】：{signal_data}
    【1m 分析】：{vision_results.get('1m', 'N/A')}
    【5m 分析】：{vision_results.get('5m', 'N/A')}
    【25m 分析】：{vision_results.get('25m', 'N/A')}
    """
    
    response = client.chat.completions.create(
        model=config.LOGIC_ENDPOINT,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.choices[0].message.content

# --- 通知 ---

def send_alert(text, image_paths=[], ai_report=""):
    """
    发送通知 (支持多图)
    """
    if not config.WECHAT_WEBHOOK_URL: return
    
    # 1. 文本消息
    full_text = text + "\n\n🧠 AI 报告:\n" + ai_report
    requests.post(config.WECHAT_WEBHOOK_URL, json={"msgtype": "text", "text": {"content": full_text}})
    
    # 2. 图片消息 (逐张发送)
    for path in image_paths:
        try:
            with open(path, "rb") as f:
                content = f.read()
            base64_data = base64.b64encode(content).decode('utf-8')
            md5 = hashlib.md5(content).hexdigest()
            requests.post(config.WECHAT_WEBHOOK_URL, json={
                "msgtype": "image",
                "image": {"base64": base64_data, "md5": md5}
            })
            time.sleep(0.5) # 防止发太快
        except Exception as e:
            logger.error(f"❌ 发图失败: {e}")
