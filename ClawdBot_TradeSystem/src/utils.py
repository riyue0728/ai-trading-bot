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
ANALYSIS_PROMPT = """## 🎯 核心任务：按图片位置顺序输出，不许打乱

**图片位置 → 字段顺序（严格对应，不许改变）：**
┌─────────┬─────────┐
│ 1分钟   │ 5分钟   │  ← JSON 字段顺序：1分钟 → 5分钟 → 25分钟
│  (左)   │  (右上) │
├─────────┼─────────┤
│         │ 25分钟  │
│         │  (右下) │
└─────────┴─────────┘

**JSON 格式（字段顺序=图片位置顺序）：**
{
    "周期分析": {
        "1分钟可见标注": "左侧区域",
        "5分钟可见标注": "右上方区域",
        "25分钟可见标注": "右下方区域"
    }
}

**🚫 禁止**：25分钟放在第一个字段
**✅ 必须**：1分钟 → 5分钟 → 25分钟

---

## 分析步骤

### 第一步：识别【所有可见买卖点】
对每个周期（1分钟、5分钟、25分钟）：

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

### 第二步：共振判断

**做多条件（满足A+B+C）**：
- A. 1分钟有买点
- B. 5分钟有买点配合
- C. 25分钟有买点

**做空条件（满足A+B+C）**：
- A. 1分钟有卖点
- B. 5分钟有卖点配合
- C. 25分钟有卖点

---

## 最终输出格式
```json
{
    "周期分析": {
        "1分钟可见标注": "[必须第一个]",
        "5分钟可见标注": "[必须第二个]",
        "25分钟可见标注": "[必须第三个]",
        "走势描述": "..."
    },
    "共振判断": {...},
    "决策": "...",
    "趋势方向": "...",
    "入场价": 0,
    "止损价": 0,
    "止盈价": 0
}
```
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
