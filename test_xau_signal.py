#!/usr/bin/env python3
"""
测试脚本：触发 XAU 信号进行分析
用法: python test_xau_signal.py
"""

import requests
import json
import sys

# 配置
WEBHOOK_URL = "http://127.0.0.1:8000/webhook"  # 修改为实际地址

# XAUUSD 测试信号
XAU_SIGNAL = {
    "symbol": "XAUUSD",
    "ticker": "XAUUSD",
    "signal": "BUY",  # 或 SELL
    "level": "1m",
    "price": 2645.50,  # 当前价格
    "chart_url": "https://cn.tradingview.com/chart/"
}

def trigger_signal(signal_data):
    """发送 webhook 信号"""
    print(f"🚀 触发信号: {signal_data['symbol']} {signal_data['signal']} @ {signal_data['price']}")
    print(f"📡 目标: {WEBHOOK_URL}")
    print(f"📦 数据: {json.dumps(signal_data, indent=2)}")
    print("-" * 50)
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=signal_data,
            timeout=30
        )
        print(f"📊 响应状态: {response.status_code}")
        print(f"📋 响应内容: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("🔔 XAUUSD 信号测试")
    print("=" * 50)
    
    # 检查是否指定了参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "buy":
            XAU_SIGNAL["signal"] = "BUY"
        elif sys.argv[1] == "sell":
            XAU_SIGNAL["signal"] = "SELL"
    
    # 触发信号
    success = trigger_signal(XAU_SIGNAL)
    
    print("=" * 50)
    if success:
        print("✅ 信号发送成功！等待 AI 分析...")
    else:
        print("❌ 信号发送失败，请检查服务是否运行")
    print("=" * 50)
