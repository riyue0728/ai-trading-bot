# 最简化测试：直接使用 Flask 而不是 FastAPI
import sys
sys.path.insert(0,  '.')

from flask import Flask, request, jsonify
import json
import time
from src import config, utils

app = Flask(__name__)
SIGNAL_CACHE = {}

@app.route('/')
def home():
    return jsonify({"status": "running", "system": "Simple Test Server"})

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    ticker = data.get('ticker', 'Unknown')
    signal = data.get('signal', 'Unknown')
    level = data.get('level', '1m')
    price = data.get('price', 0)
    
    utils.logger.info(f"📩 收到信号: {ticker} | {level} | {signal}")
    
    # 去重
    dedup_key = f"{ticker}_{signal}_{level}_{int(float(price or 0))}"
    now = time.time()
    if dedup_key in SIGNAL_CACHE and now - SIGNAL_CACHE[dedup_key] < 120:
        return jsonify({"status": "ignored", "msg": "Duplicate"})
    SIGNAL_CACHE[dedup_key] = now
    
    # 立即返回成功（不等待）
    utils.logger.info("✅ 信号已接受，后台处理中...")
    
    return jsonify({"status": "accepted", "msg": "Processing"})

if __name__ == '__main__':
    print("✅ Flask 简易服务器启动 (端口 8000)")
    app.run(host='0.0.0.0', port=8000, debug=False)
