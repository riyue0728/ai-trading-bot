import requests
import json

url = "http://127.0.0.1:5001/webhook"

# 测试：XAUUSD 25m 次级别底盘整背驰
payload = {
    "ticker": "XAUUSD",
    "signal": "次级别底盘整背驰",  # 次级别背驰类型
    "level": "25m",
    "price": 2696.3,  # 更新价格
    "chart_url": "https://cn.tradingview.com/chart/PP8uCQUu/"
}

print("=" * 70)
print("=== 测试场景：XAUUSD（黄金）25分钟 - 次级别底盘整背驰 ===")
print("=" * 70)
print(f"标的: {payload['ticker']}")
print(f"信号类型: {payload['signal']}")
print(f"级别: {payload['level']}")
print(f"价格: ${payload['price']}")
print(f"图表: {payload['chart_url']}")
print("=" * 70)
print("\n📖 知识库参考：")
print("- 次级别 = 笔级别")
print("- 盘整背驰 = 区间震荡后的MACD柱体衰减")
print("- 判断标准：MACD柱体值对比")
print("=" * 70)

try:
    # 禁用代理
    session = requests.Session()
    session.trust_env = False
    
    print("\n🚀 发送信号...")
    response = session.post(url, json=payload, timeout=60)
    
    print(f"\n✅ HTTP 状态码: {response.status_code}")
    
    if response.status_code == 200:
        resp_data = response.json()
        print(f"\n📨 服务器响应:")
        print(json.dumps(resp_data, indent=2, ensure_ascii=False))
    else:
        print(f"\n响应内容: {response.text}")
        
except requests.Timeout:
    print("\n⏰ 请求超时（正常现象）")
    print("服务器正在后台处理：")
    print("  1. Playwright 截图")
    print("  2. Doubao-1.6-Vision 分析图表")
    print("  3. DeepSeek-V3 决策")
    print("  4. 发送企业微信")
    print("\n请等待约30-40秒，检查企业微信通知...")
    
except Exception as e:
    print(f"\n❌ 请求失败: {e}")

print("\n" + "=" * 70)
