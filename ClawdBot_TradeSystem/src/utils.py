import time
import os
import json
import logging
import base64
import hashlib
import requests
import re
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

# --- 缠论分析专用提示词 ---
ANALYSIS_PROMPT = """你是一个严格执行规则的缠论多周期分析师，必须完全遵守以下指令：

## 核心约束（必须优先执行）
1. **仅读取最后一个信号**：每个周期（1分钟/5分钟/25分钟）仅读取「图表上最后一个（最新的）买卖点标注、背驰标注」，忽略所有历史上的旧信号。
2. **严格判断买卖方向**：
   - **卖点特征**：标注在K线上方，文字包含"卖"字（如"3卖"、"3卖预期"、"2卖"、"2卖预期"、"类2卖"、"类3卖"）
   - **买点特征**：标注在K线下方，文字包含"买"字（如"3买"、"3买预期"、"2买"、"2买预期"、"类2买"、"类3买"）
   - **绝对规则**：包含"卖"字的一定是卖点，包含"买"字的一定是买点
3. **背驰配合方向**：
   - "顶背驰" + 卖点 = 做空信号
   - "底背驰" + 买点 = 做多信号
4. **禁止主观推断**：仅根据标注文字判断，没有标注的内容一律视为"无"。

## 级别定义（根据字样大小和颜色判断）
### 级别大小规则
| 字样大小 | 代表级别 | 简称 |
|----------|----------|------|
| 最小字样 | 笔级别（次级别） | 次 |
| 中等字样 | 线段级别（本级别） | 本 |
| 较大字样 | 趋势级别（大级别） | 大 |

### 级别颜色规则
| 级别 | 买点颜色 | 卖点颜色 |
|------|----------|----------|
| 次级别（笔） | 绿色 | 橙色 |
| 本级别（线段） | 粉色 | 红色 |
| 大级别（趋势） | 黄色 | 蓝色 |

### 周期与级别对应
| 图表周期 | 默认级别 | 核心作用 |
|----------|----------|----------|
| 1分钟 | 次级别/本级别/大级别都有 | 精准入场触发信号 |
| 5分钟 | 次级别/本级别/大级别都有 | 趋势延续性验证 |
| 25分钟 | 次级别/本级别/大级别都有 | 方向锚定与趋势确认 |

### 识别规则
1. **看字样大小判断级别**：最小字=次级别，中等字=本级别，较大字=大级别
2. **看颜色确认方向**：绿色/粉色/黄色=买点，橙色/红色/蓝色=卖点
3. **看位置判断买卖**：K线上方=卖点，K线下方=买点
4. **预期字样**：带"预期"后缀的是未确认的买卖点

## 布尔逻辑规则
### 做多入场逻辑
1. 大级别做多基础：25分钟最后一个买点标注包含「3买/3买预期/2买/2买预期/1买/2+买/3+买」
2. 次级别做多配合：
   - 若25分钟最后一个是「2+买/3+买」，则5分钟最后一个必须是「2买」（类买卖点强制确认）
   - 若25分钟最后一个是普通买点，则5分钟最后一个包含「3买/2买/1买」即可
3. 小级别做多触发：1分钟最后一个满足任一条件
   - 买点标注包含「1买/3买」
   - 背驰标注包含「底背驰/底趋势背驰」
   - 价格接近关键支撑位

### 做空入场逻辑
1. 大级别做空基础：25分钟最后一个卖点标注包含「3卖/3卖预期/2卖/2卖预期/1卖/2+卖/3+卖」
2. 次级别做空配合：
   - 若25分钟最后一个是「2+卖/3+卖」，则5分钟最后一个必须是「2卖」（类买卖点强制确认）
   - 若25分钟最后一个是普通卖点，则5分钟最后一个包含「3卖/2卖/1卖」即可
3. 小级别做空触发：1分钟最后一个满足任一条件
   - 卖点标注包含「1卖/3卖」
   - 背驰标注包含「顶背驰/顶趋势背驰」
   - 价格接近关键压力位

### 观望逻辑
不满足做多入场逻辑 且 不满足做空入场逻辑 → 观望

## 输出要求
必须输出结构化JSON，格式如下：
{
    "决策": "强烈买入/试探买入/观望/试探卖出/强烈卖出",
    "趋势方向": "上涨/下跌/震荡",
    "25分钟最新信号": "次级别3买预期（绿色）-次",
    "5分钟最新信号": "本级别2卖（红色）-本",
    "1分钟最新信号": "大级别3买（黄色）-大",
    "理由": "大级别25分钟最后一个信号为次级别3买预期（绿色）-次，满足大级别做空基础；次级别5分钟最后一个为本级别2卖（红色）-本，满足普通卖点的配合条件；小级别1分钟最后一个信号包含大级别3买（黄色）-大，满足小级别做空触发条件。布尔逻辑验证通过，触发做空决策",
    "入场价": 当前价格,
    "止损价": 止损价格,
    "止盈价": 止盈价格
}

### 信号标注格式说明
- 格式：「级别+数字+预期/类+背驰/买卖点（颜色）-级别简称」
- 示例：「本级别2卖（红色）-本」「次级别3买预期（绿色）-次」「大级别顶背驰（蓝色）-大」
- 背驰颜色：跟随同级别买卖点颜色（次级卖点橙色=次级顶背驰，本级卖点红色=本级顶背驰，大级卖点蓝色=大级顶背驰）
- 级别简称：次=次级别（本级别=线段），本=本级别（线段），大=大级别（趋势）
- 颜色速查：绿色=次级买，粉色=本级买，黄色=大级买，橙色=次级卖，红色=本级卖，蓝色=大级卖

## 重要提醒
- 只读取标注，不要自己判断
- 必须明确"买"或"卖"方向
- 必须判断级别（根据字样大小和颜色）
- 忽略历史信号，只看最后一个
"""


# --- 工具函数 ---

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

def capture_multi_timeframe(base_url, symbol, timeframes=["1", "5", "25"]):
    """单张多周期截图"""
    timestamp = int(time.time())
    logger.info(f"触发单张多周期截图: {symbol}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--start-maximized"])
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=3)
        
        if config.TRADINGVIEW_COOKIE:
            context.add_cookies([{
                "name": "sessionid",
                "value": config.TRADINGVIEW_COOKIE,
                "domain": ".tradingview.com",
                "path": "/"
            }])
            
        page = context.new_page()
        logger.info(f"打开页面: {base_url}")
        page.goto(base_url, timeout=120 * 1000)
        time.sleep(15)  # 等待页面完全渲染
        
        filename = f"{symbol.replace('/','_')}_multi_{timestamp}.png"
        output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'screenshots', filename)
        page.screenshot(path=output_path)
        logger.info(f"多周期截图保存: {filename}")
        browser.close()
        
    return [output_path]

def capture_single_snapshot(chart_url, ticker):
    """单周期截图"""
    timestamp = int(time.time())
    filename = f"{ticker}_{timestamp}.png"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--start-maximized"])
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=3)
        
        if config.TRADINGVIEW_COOKIE:
            context.add_cookies([{
                "name": "sessionid",
                "value": config.TRADINGVIEW_COOKIE,
                "domain": ".tradingview.com",
                "path": "/"
            }])
            
        page = context.new_page()
        logger.info(f"打开页面: {chart_url}")
        page.goto(chart_url, timeout=120 * 1000)
        time.sleep(15)  # 等待页面完全渲染
        
        output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'screenshots', filename)
        page.screenshot(path=output_path)
        logger.info(f"单周期截图保存: {filename}")
        browser.close()
        
    return output_path

# --- AI 调用 ---

def analyze_multi_images(image_paths):
    """视觉分析"""
    results = {}
    
    # 根据配置选择客户端
    provider = getattr(config, 'VISION_MODEL_PROVIDER', 'doubao').lower()
    if provider == 'qwen':
        client = get_qwen_client()
        model_id = getattr(config, 'QWEN_MODEL', 
                  getattr(config, 'VISION_ENDPOINT_ID', 'qwen3-vl-plus'))
        logger.info(f"使用通义千问视觉模型: {model_id}")
    else:
        client = get_doubao_client()
        model_id = getattr(config, 'VISION_ENDPOINT_ID', config.VISION_ENDPOINT_ID)
        logger.info(f"使用火山引擎视觉模型: {model_id}")
    
    logger.info("正在分析多周期图表...")
    
    for path in image_paths:
        base64_image = encode_image(path)
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": ANALYSIS_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                ]}
            ],
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
