import requests
import json

url = "http://127.0.0.1:5001/webhook"

# 测试：BTC 25分钟 单段趋势底背驰
payload = {
    "ticker": "BTCUSDT",
    "signal": "本级别顶/底趋势背驰",  # 根据新的读图说明
    "level": "25m",
    "price": 103500,
    "chart_url": "https://cn.tradingview.com/chart/PP8uCQUu/"
}

print("=" * 60)
print("测试场景：BTC 25分钟 单段趋势底背驰")
print("=" * 60)
print(f"发送信号到: {url}")
print(f"数据: {json.dumps(payload, indent=2, ensure_ascii=False)}")
print("=" * 60)

try:
    # 禁用代理
    session = requests.Session()
    session.trust_env = False
    
    response = session.post(url, json=payload, timeout=60)
    print(f"\n✅ HTTP 响应: {response.status_code}")
    print(f"响应内容: {response.text}")
except requests.Timeout:
    print("\n⏰ 请求超时（正常，服务器在后台处理中）")
    print("请检查服务器日志和企业微信通知...")
except Exception as e:
    print(f"\n❌ 请求失败: {e}")
