from fastapi import FastAPI, Request, BackgroundTasks
from pydantic import BaseModel
import uvicorn
import time
import json
import logging
from . import config, utils

app = FastAPI()
logger = utils.logger

# 信号缓存 (V2.0 去重)
SIGNAL_CACHE = {}

def process_signal_background(data):
    """
    后台任务：处理信号的耗时操作（截图、AI分析）
    """
    try:
        ticker = data.get('symbol', data.get('ticker', 'Unknown'))
        signal = data.get('signal', 'Unknown')
        level = data.get('level', '1m')
        price = data.get('price')
        chart_url = data.get('chart_url', "https://cn.tradingview.com/chart/")
        
        logger.info(f"⚙️ 开始后台处理: {ticker} {level} {signal}")
        
        # 1. 立即发送通知：信号已接收
        try:
            utils.send_alert(f"🚀 信号触发: {ticker} {level} {signal} @ {price}", [], "")
        except Exception as e:
            logger.warning(f"初始通知失败: {e}")
        
        # 2. 多周期截图
        screenshot_paths = []
        if level == "1m":
            logger.info("⚡ 触发 1m/5m/25m 多周期共振分析...")
            screenshot_paths = utils.capture_multi_timeframe(chart_url, ticker, ["1", "5", "25"])
        else:
            logger.info("⚡ 触发单周期分析...")
            path = utils.capture_single_snapshot(chart_url, ticker)
            screenshot_paths = [path]
            
        if not screenshot_paths:
            logger.error("❌ 截图失败")
            return
        
        # 3. AI 双脑分析
        vision_results = utils.analyze_multi_images(screenshot_paths)
        decision_json = utils.make_resonance_decision(data, vision_results)
        
        # 4. 发送最终报告
        utils.send_alert(
            f"✅ AI 分析完成 ({len(screenshot_paths)}周期共振)", 
            screenshot_paths, 
            decision_json
        )
        
        logger.info(f"✅ 后台处理完成: {ticker}")
        
    except Exception as e:
        logger.error(f"❌ 后台处理异常: {e}", exc_info=True)

@app.get("/")
def home():
    return {"status": "running", "system": "ClawdBot Multi-Axis Trade System"}

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """
    ClawdBot 标准 Webhook 接收端点
    """
    try:
        raw_body = await request.body()
        data = json.loads(raw_body)
        
        ticker = data.get('symbol', data.get('ticker', 'Unknown'))
        signal = data.get('signal', 'Unknown')
        level = data.get('level', '1m')
        price = data.get('price')
        
        logger.info(f"📩 收到信号: {ticker} | {level} | {signal}")
        
        # 1. 信号去重 (V2.0)
        dedup_key = f"{ticker}_{signal}_{level}_{int(float(price or 0))}"
        now = time.time()
        if dedup_key in SIGNAL_CACHE and now - SIGNAL_CACHE[dedup_key] < config.SIGNAL_DUPLICATE_TIME:
            logger.warning(f"🚫 拦截重复信号: {dedup_key}")
            return {"status": "ignored", "msg": "Duplicate"}
        SIGNAL_CACHE[dedup_key] = now
        
        # 2. 将所有处理（包括通知）加入后台任务
        # 注意：不在这里调用 send_alert，因为它会阻塞 async 函数
        background_tasks.add_task(process_signal_background, data)
        
        return {"status": "accepted", "msg": "Signal processing in background"}
        
    except Exception as e:
        logger.error(f"❌ 系统异常: {e}")
        return {"status": "error", "msg": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host=config.FASTAPI_HOST, port=config.FASTAPI_PORT)
