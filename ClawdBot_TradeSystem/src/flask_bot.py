# ============================================
# ClawdBot Trading Bot - Flask 版本 (兼容 Windows)
# ============================================

from flask import Flask, request, jsonify
import time
import json
import logging
from src import config, utils

app = Flask(__name__)
logger = utils.logger

# 信号缓存 (V2.0 去重)
SIGNAL_CACHE = {}

def is_duplicate_signal(data):
    """
    检查信号是否重复
    """
    try:
        ticker = data.get('ticker', 'unknown')
        level = data.get('level', 'unknown')
        signal = data.get('signal', 'unknown')
        price = int(float(data.get('price', 0)))
        
        key = f"{ticker}_{level}_{signal}_{price}"
        now = time.time()
        
        # 清理过期缓存
        to_remove = [k for k, v in SIGNAL_CACHE.items() if now - v > config.SIGNAL_DUPLICATE_TIME]
        for k in to_remove:
            del SIGNAL_CACHE[k]
        
        if key in SIGNAL_CACHE:
            last_time = SIGNAL_CACHE[key]
            if now - last_time < config.SIGNAL_DUPLICATE_TIME:
                logger.warning(f"🚫 拦截重复信号: {key} (上次触发: {int(now-last_time)}秒前)")
                return True
        
        SIGNAL_CACHE[key] = now
        return False
    except Exception as e:
        logger.error(f"⚠️ 去重逻辑出错: {e}")
        return False

@app.route('/')
def home():
    return jsonify({"status": "running", "system": "ClawdBot Trade System (Flask)"})

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    接收 TradingView 信号
    """
    try:
        data = request.json
        if not data:
            data = json.loads(request.data)
            
        ticker = data.get('symbol', data.get('ticker', 'Unknown'))
        signal = data.get('signal', 'Unknown')
        level = data.get('level', '1m')
        price = data.get('price')
        
        logger.info(f"📩 收到信号: {ticker} | {level} | {signal}")
        
        # 去重
        if is_duplicate_signal(data):
            return jsonify({"status": "ignored", "msg": "Duplicate"}), 200
        
        # 立即返回确认 (Flask 会在后台继续处理)
        # 注意：这里我们用 Flask 的 before_request 模拟异步
        process_signal(data)
        
        return jsonify({"status": "accepted", "msg": "Processing"}), 200
        
    except Exception as e:
        logger.error(f"❌ 系统异常: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 500

def process_signal(data):
    """
    处理信号（Flask 版本 - 同步）
    """
    try:
        ticker = data.get('symbol', data.get('ticker', 'Unknown'))
        signal = data.get('signal', 'Unknown')
        level = data.get('level', '1m')
        price = data.get('price')
        chart_url = data.get('chart_url', "https://cn.tradingview.com/chart/")
        
        # 1. 初始通知
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
        
        logger.info(f"✅ 处理完成: {ticker}")
        
    except Exception as e:
        logger.error(f"❌ 处理异常: {e}", exc_info=True)

if __name__ == '__main__':
    print(f"🚀 ClawdBot 交易系统启动！端口: {config.FASTAPI_PORT}")
    print("📡 Webhook 地址: http://你的IP:{}/webhook".format(config.FASTAPI_PORT))
    app.run(host=config.FASTAPI_HOST, port=config.FASTAPI_PORT, threaded=True)
