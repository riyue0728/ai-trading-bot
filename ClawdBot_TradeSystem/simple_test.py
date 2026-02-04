import requests
import json

url = "http://127.0.0.1:5001/webhook"

payload = {
    "ticker": "XAUUSD",
    "signal": "底背驰1买",
    "level": "1m",
    "price": 2050,
    "chart_url": "https://cn.tradingview.com/chart/PP8uCQUu/"
}

print(f"发送测试信号到: {url}")
print(f"数据: {payload}")

try:
    # 关键修复：禁用系统代理
    session = requests.Session()
    session.trust_env = False
    
    response = session.post(url, json=payload, timeout=5)
    print(f"\n✅ 响应状态码: {response.status_code}")
    print(f"响应内容: {response.text}")
except Exception as e:
    print(f"\n❌ 请求失败: {e}")
