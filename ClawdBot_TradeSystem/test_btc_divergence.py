import requests
import json

url = "http://127.0.0.1:5001/webhook"

# 测试：BTC 25m 本级别底标准趋势背驰
payload = {
    "ticker": "BTCUSDT",
    "signal": "本级别底标准趋势背驰",  # 根据更新后的精确定义
    "level": "25m",
    "price": 76320.1,
    "chart_url": "https://cn.tradingview.com/chart/PP8uCQUu/"
}

print("=" * 70)
print("📊 测试场景：BTC 25分钟 - 本级别底标准趋势背驰")
print("=" * 70)
print(f"标的: {payload['ticker']}")
print(f"信号类型: {payload['signal']}")
print(f"级别: {payload['level']}")
print(f"价格: {payload['price']}")
print(f"图表: {payload['chart_url']}")
print("=" * 70)

try:
    # 禁用代理
    session = requests.Session()
    session.trust_env = False
    
    response = session.post(url, json=payload, timeout=60)
    print(f"\n✅ HTTP 状态码: {response.status_code}")
    
    if response.status_code == 200:
        resp_data = response.json()
        print(f"响应: {json.dumps(resp_data, indent=2, ensure_ascii=False)}")
    else:
        print(f"响应内容: {response.text}")
        
except requests.Timeout:
    print("\n⏰ 请求超时（服务器正在后台处理）")
    print("这是正常现象，请等待企业微信通知...")
except Exception as e:
    print(f"\n❌ 请求失败: {e}")

print("\n" + "=" * 70)
print("💡 提示：")
print("1. 服务器需要约30-40秒完成截图、AI分析")
print("2. 请检查企业微信群，查看AI的分析报告")
print("3. 服务器日志会显示详细的处理过程")
print("=" * 70)
