import time
import os
import json
import logging
import base64
import hashlib
import requests
import re
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright
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

# 周期配置
TIMEFRAME_CONFIGS = {
    "XAUUSD": {
        "timeframes": ["25分钟", "5分钟", "1分钟"],
        "keys": ["25分钟", "5分钟", "1分钟"],
        "left": "1分钟",
        "top_right": "5分钟", 
        "bottom_right": "25分钟"
    },
    "BTCUSD": {
        "timeframes": ["2小时", "25分钟", "5分钟"],
        "keys": ["2小时", "25分钟", "5分钟"],
        "left": "5分钟",
        "top_right": "25分钟",
        "bottom_right": "2小时"
    }
}

def get_analysis_prompt(ticker="XAUUSD"):
    """获取对应品种的分析Prompt"""
    tf_config = TIMEFRAME_CONFIGS.get(ticker, TIMEFRAME_CONFIGS["XAUUSD"])
    
    main_tf = tf_config["keys"][0]
    mid_tf = tf_config["keys"][1]
    small_tf = tf_config["keys"][2]
    
    return f"""你是一个严格执行规则的缠论多周期分析师，分析必须按以下步骤进行：

## 分析步骤（必须严格遵守）

### 第一步：识别【所有可见买卖点】
对每个周期（{main_tf}、{mid_tf}、{small_tf}）：

**关键规则**：
- ✅ **只关注图表右侧区域**（K线最右端的可见区域）
- ✅ **如果有多个标注在同一区域，全部识别并列出**
- ❌ **忽略左侧的历史标注**

**识别要求**：
- 先看最右侧的 K 线区域
- 如果该区域有多个买卖点标注，**全部列出来**
- 格式："标注1 + 标注2 + 标注3"

**判断规则**：
| 包含文字 | 方向 | 位置 |
|---------|------|------|
| "卖"/"顶背驰" | 卖点 | K线上方 |
| "买"/"底背驰" | 买点 | K线下方 |

**级别判断**（看字样大小和颜色）：
| 字样大小 | 颜色 | 级别 |
|---------|------|------|
| 最小 | 绿色/橙色 | 次级别（笔） |
| 中等 | 粉色/红色 | 本级别（线段） |
| 较大 | 黄色/蓝色 | 大级别（趋势） |

**背驰类型判断**（重要！看MACD区域）：
- 仔细看MACD指标区域是否有背驰类型标注
- 背驰类型包括：
  - "标准趋势背驰"（或"有中枢的趋势背驰"）→ **最强！** ← 重点开仓
  - "趋势背驰" → 中等
  - "盘整背驰" → 较弱
- 如果MACD区域有标注，必须识别出来

**输出格式**：
- {main_tf}可见标注：[列出所有右侧可见的标注，用"+"连接]
- {mid_tf}可见标注：[列出所有右侧可见的标注，用"+"连接]
- {small_tf}可见标注：[列出所有右侧可见的标注，用"+"连接]
- {small_tf}背驰类型：[标准趋势背驰/趋势背驰/盘整背驰/无]

示例：
- "红色的本级别类2卖预期 + 橙色的次级别1卖预期"
- "红色的本级别2卖预期"
- "蓝色的大级别2卖 + 红色的本级别1卖 + 橙色的次级别1卖"
- "无"（如果右侧区域没有任何标注）

### 第二步：【回顾走势】
根据识别出的所有可见买卖点，描述当前走势状态：

**如果有多个标注**：
- 卖点优先级：大级别 > 本级别 > 次级别
- 只用最高级别的标注来描述走势

**根据最高级别标注判断**：
| 最高级别 | 标注示例 | 走势描述 |
|---------|---------|---------|
| 大级别 | 蓝色的大级别2卖 | 价格处于下跌/回调阶段，正在向下离开中枢或笔 |
| 本级别 | 红色的本级别2卖 | 价格处于下跌/回调阶段，正在向中枢回归或笔 |
| 次级别 | 橙色的次级别1卖 | 价格处于小级别回调/反弹阶段 |

### 第三步：【多周期共振判断】

**首先统计各周期卖点/买点**：
- 统计{main_tf}、{mid_tf}、{small_tf}各有什么卖点/买点
- 卖点：3卖 > 2卖 > 1卖（优先级）
- 买点：3买 > 2买 > 1买（优先级）
- "预期"是未确认信号

**做多条件（满足A+B+C）**：
- A. {main_tf}有买点（3买/2买/1买/底背驰，非预期优先）
- B. {mid_tf}有买点配合
- C. {small_tf}有买点或底背驰（入场触发）

**做空条件（满足A+B+C）**：
- A. {main_tf}有卖点（3卖/2卖/1卖/顶背驰，非预期优先）
- B. {mid_tf}有卖点配合
- C. {small_tf}有卖点或顶背驰（入场触发）

**观望条件**：
- 不满足做多条件 且 不满足做空条件

## 输出格式
必须是JSON格式：
{{
    "周期分析": {{
        "{main_tf}可见标注": "列出所有右侧可见标注",
        "{mid_tf}可见标注": "列出所有右侧可见标注",
        "{small_tf}可见标注": "列出所有右侧可见标注",
        "{small_tf}背驰类型": "标准趋势背驰/趋势背驰/盘整背驰/无",
        "走势描述": "综合所有标注描述当前走势"
    }},
    "技术指标": {{
        "RSI": "RSI当前数值和是否超买超卖",
        "均线排列": "均线多头/空头/缠绕状态",
        "MACD": "MACD位置和动能分析"
    }},
    "共振判断": {{
        "多周期状态": "多头共振/空头共振/无共振",
        "方向确认": "做多/做空/观望",
        "理由": "综合{main_tf}、{mid_tf}、{small_tf}的卖点/买点情况"
    }},
    "决策": "强烈买入/试探买入/观望/试探卖出/强烈卖出",
    "趋势方向": "上涨/下跌/震荡",
    "入场价": 当前价格,
    "止损价": 止损价格,
    "T1止盈价": 止盈价格1（盈亏比1:1.5）,
    "T2止盈价": 止盈价格2（继续持有）
}}

## 重要规则
1. **右侧区域所有标注都要识别并列出**
2. **卖点优先级**：3卖 > 2卖 > 1卖（非预期优先）
3. **买点优先级**：3买 > 2买 > 1买（非预期优先）
4. **不做主观推断**，没有标注就是"无"
5. **先识别所有标注，再判断最高级别，最后综合共振**
6. **背驰类型决定开仓强度**：
   - "标准趋势背驰"（有中枢的趋势背驰）→ 最强，可能反向一段，出现3类买卖点才是真正反转
   - "趋势背驰" → 中等，可能反向一段
   - "盘整背驰" → 较弱，可能反向一笔
   - "无" → 没有背驰，观望

7. **背驰不代表反转**：
   - 盘整背驰 → 可能反向一笔（幅度小）
   - 趋势背驰 → 可能反向一段（幅度大）
   - 趋势背驰+出现3类买卖点 → 才是真正反转！

**图表布局说明**：
- 左侧 = {small_tf}周期（小图）
- 右上 = {mid_tf}周期（中图）
- 右下 = {main_tf}周期（大图）
"""

# 兼容旧代码
ANALYSIS_PROMPT = get_analysis_prompt("XAUUSD")

# --- 工具函数 ---
# --- Google Gemini 视觉模型支持 ---
def analyze_with_gemini(image_path, prompt=None):
    """使用 Gemini 分析图片"""
    try:
        with open(image_path, 'rb') as f:
            img_b64 = base64.b64encode(f.read()).decode()
        
        api_key = getattr(config, 'GEMINI_API_KEY', '')
        model = getattr(config, 'GEMINI_MODEL', 'gemini-2.5-flash')
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        # 如果没有传入prompt，使用默认的
        if prompt is None:
            prompt = ANALYSIS_PROMPT
        
        logger.info("正在使用 Gemini 分析...")
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/png", "data": img_b64}}
                ]
            }]
        }
        
        resp = requests.post(url, json=payload, timeout=90)
        
        if resp.status_code == 200:
            result = resp.json()
            if "candidates" in result:
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                # 清理 markdown 格式
                text = text.replace("```json", "").replace("```", "").strip()
                return text
        else:
            logger.error(f"Gemini API 错误: {resp.status_code} - {resp.text[:200]}")
            return None
            
    except Exception as e:
        logger.error(f"Gemini 分析失败: {e}")
        return None



def get_doubao_client():
    """获取火山引擎 OpenAI 兼容客户端"""
    api_url = getattr(config, 'LOGIC_API_URL', 'https://ark.cn-beijing.volcen.com/api/v3')
    return OpenAI(
        api_key=config.LOGIC_API_KEY,
        base_url=api_url,
    )

def get_qwen_client():
    """获取通义千问 OpenAI 兼容客户端"""
    api_url = getattr(config, 'QWEN_API_URL', 
              getattr(config, 'VISION_API_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1'))
    api_key = getattr(config, 'QWEN_API_KEY', 
             getattr(config, 'VISION_API_KEY', ''))
    return OpenAI(
        api_key=api_key,
        base_url=api_url,
    )

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# --- Playwright 截图 ---

def _take_single_snapshot_page(context, url, filename, timeout=120):
    """截图函数"""
    page = context.new_page()
    logger.info(f"打开页面: {url}")
    page.goto(url, timeout=timeout * 1000)
    logger.info("等待页面渲染 (10s)...")
    time.sleep(10)
    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'screenshots', filename)
    page.screenshot(path=output_path)
    logger.info(f"截图保存: {filename}")
    page.close()
    return output_path

import asyncio
from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=2)

def capture_multi_timeframe(base_url, symbol, timeframes=["1", "5", "25"]):
    """单张多周期截图"""
    # 在线程池中运行同步的playwright代码，避免阻塞asyncio事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_capture_multi_timeframe_async(base_url, symbol, timeframes))
    finally:
        loop.close()

async def _capture_multi_timeframe_async(base_url, symbol, timeframes=["1", "5", "25"]):
    """异步版本的截图函数"""
    timestamp = int(time.time())
    logger.info(f"触发单张多周期截图: {symbol}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--start-maximized"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=3)
        
        if config.TRADINGVIEW_COOKIE:
            await context.add_cookies([{
                "name": "sessionid",
                "value": config.TRADINGVIEW_COOKIE,
                "domain": ".tradingview.com",
                "path": "/"
            }])
            
        page = await context.new_page()
        logger.info(f"打开页面: {base_url}")
        await page.goto(base_url, timeout=240 * 1000, wait_until="domcontentloaded")
        # 等待图表容器出现
        try:
            await page.wait_for_selector(".chart-container", timeout=60000)
        except:
            pass
        await asyncio.sleep(10)  # 等待页面渲染
        
        filename = f"{symbol.replace('/','_')}_multi_{timestamp}.png"
        output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'screenshots', filename)
        await page.screenshot(path=output_path, timeout=120000)
        logger.info(f"多周期截图保存: {filename}")
        await browser.close()
        
    return [output_path]

def capture_single_snapshot(chart_url, ticker):
    """单周期截图"""
    # 在线程池中运行同步的playwright代码
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_capture_single_snapshot_async(chart_url, ticker))
    finally:
        loop.close()

async def _capture_single_snapshot_async(chart_url, ticker):
    """异步版本的单周期截图"""
    timestamp = int(time.time())
    filename = f"{ticker}_{timestamp}.png"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--start-maximized"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=3)
        
        if config.TRADINGVIEW_COOKIE:
            await context.add_cookies([{
                "name": "sessionid",
                "value": config.TRADINGVIEW_COOKIE,
                "domain": ".tradingview.com",
                "path": "/"
            }])
            
        page = await context.new_page()
        logger.info(f"打开页面: {chart_url}")
        await page.goto(chart_url, timeout=180 * 1000, wait_until="domcontentloaded")
        try:
            await page.wait_for_selector(".chart-container", timeout=60000)
        except:
            pass
        await asyncio.sleep(10)  # 等待页面渲染
        
        output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'screenshots', filename)
        await page.screenshot(path=output_path, timeout=120000)
        logger.info(f"单周期截图保存: {filename}")
        await browser.close()
        
    return output_path

# --- AI 调用 ---

def analyze_multi_images(image_paths, ticker="XAUUSD"):
    """视觉分析"""
    results = {}
    
    # 获取对应品种的Prompt
    prompt = get_analysis_prompt(ticker)
    
    provider = getattr(config, 'VISION_MODEL_PROVIDER', 'doubao').lower()
    
    # Gemini 模式
    if provider == 'gemini':
        model = getattr(config, 'GEMINI_MODEL', 'gemini-2.5-flash')
        logger.info(f"使用 Google Gemini 视觉模型: {model}")
        
        for path in image_paths:
            logger.info(f"分析图片: {os.path.basename(path)}")
            gemini_result = analyze_with_gemini(path, prompt)
            if gemini_result:
                results["analysis"] = gemini_result
                logger.info("Gemini 分析完成")
            else:
                results["analysis"] = '{"周期分析":{"25分钟可见标注":"无","5分钟可见标注":"无","1分钟可见标注":"无"}}'
    
    # 通义千问模式
    elif provider == 'qwen':
        client = get_qwen_client()
        model_id = getattr(config, 'VISION_ENDPOINT_ID', 'qwen3-vl-plus')
        logger.info(f"使用通义千问视觉模型: {model_id}")
        
        for path in image_paths:
            base64_image = encode_image(path)
            response = client.chat.completions.create(
                model=model_id,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ANALYSIS_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]
                }]
            )
            results["analysis"] = response.choices[0].message.content
    
    # 火山引擎模式 (默认)
    else:
        client = get_doubao_client()
        model_id = getattr(config, 'VISION_ENDPOINT_ID', config.VISION_ENDPOINT_ID)
        logger.info(f"使用火山引擎视觉模型: {model_id}")
        
        for path in image_paths:
            base64_image = encode_image(path)
            response = client.chat.completions.create(
                model=model_id,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ANALYSIS_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]
                }]
            )
            results["analysis"] = response.choices[0].message.content
        
    return results

def make_resonance_decision(signal_data, vision_results):
    """逻辑决策"""
    logger.info("正在进行多周期共振思考...")
    
    try:
        analysis_text = vision_results.get('analysis', '')
        
        # 查找JSON内容
        json_match = re.search(r'\{[\s\S]*\}', analysis_text)
        if json_match:
            result_json = json_match.group()
            return result_json
        else:
            logger.error("无法解析分析结果")
            return '{"决策":"观望","理由":"分析结果解析失败"}'
        
    except Exception as e:
        logger.error(f"决策处理失败: {e}")
        return f'{{"决策":"观望","理由":"处理错误: {str(e)}"}}'

def send_alert(text, image_paths=[], ai_report=""):
    """发送企微通知"""
    logger.info(f"准备发送通知: {text[:50]}...")
    
    if not config.WECHAT_WEBHOOK_URL:
        logger.warning("未配置企业微信 Webhook")
        return
    
    session = requests.Session()
    session.trust_env = False
    
    full_text = text + "\n\nAI分析报告:\n" + ai_report
    try:
        resp = session.post(config.WECHAT_WEBHOOK_URL, json={"msgtype": "text", "text": {"content": full_text}})
        logger.info(f"企微文本响应: {resp.status_code}")
    except Exception as e:
        logger.error(f"企微文本发送失败: {e}")
    
    for path in image_paths:
        try:
            with open(path, "rb") as f:
                content = f.read()
            base64_data = base64.b64encode(content).decode('utf-8')
            md5 = hashlib.md5(content).hexdigest()
            resp = session.post(config.WECHAT_WEBHOOK_URL, json={
                "msgtype": "image",
                "image": {"base64": base64_data, "md5": md5}
            })
            logger.info(f"企微图片 {os.path.basename(path)} 响应: {resp.status_code}")
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"发图失败 {os.path.basename(path)}: {e}")
