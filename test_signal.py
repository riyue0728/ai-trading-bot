import requests
import json

# 模拟 TradingView 发出的信号
payload = {
    "signal": "Test_Buy_Signal_1",
    "price": 2050.5,
    "level": "5m",
    "ticket": "XAUUSD",
    "chart_url": "https://cn.tradingview.com/chart/PP8uCQUu/"
}

print("🚀 正在模拟 TradingView 发送信号...")
try:
    # 禁用代理 (防止 502 错误)
    session = requests.Session()
    session.trust_env = False
    
    response = session.post("http://127.0.0.1:5001/webhook", json=payload)
    print(f"✅ 发送成功! 状态码: {response.status_code}")
    print(f"📩 服务器回复: {response.text}")
except Exception as e:
    print(f"❌ 发送失败: {e}")
    print("请检查 trade_bot.py 是否正在运行!")
