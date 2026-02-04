import requests
import json
import time

# 目标地址 (ClawdBot V2.0 默认端口 5001)
WEBHOOK_URL = "http://127.0.0.1:5001/webhook"

def send_test_signal(ticker="XAUUSD", signal="1buy", level="1m", price=2050):
    payload = {
        "ticker": ticker,
        "signal": signal,
        "level": level,    # 1m 会触发多周期截图, 5m 只会触发单图
        "price": price,
        "chart_url": "https://cn.tradingview.com/chart/PP8uCQUu/"  # 你的真实图表地址
    }
    
    print(f"🚀 发送模拟信号: {payload} -> {WEBHOOK_URL}")
    try:
        # 关键修复：禁用系统代理避免 502
        session = requests.Session()
        session.trust_env = False
        
        resp = session.post(WEBHOOK_URL, json=payload, timeout=60)
        print(f"✅ 从服务器收到响应 ({resp.status_code}):")
        try:
            print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
        except:
            print(resp.text)
    except Exception as e:
        print(f"❌ 发送失败: {e}")

if __name__ == "__main__":
    # 测试 1: 发送 1m 信号 (应该触发 3张截图)
    print("\n=== 测试场景 1: 1m 多周期共振 ===")
    send_test_signal(level="1m", signal="底背驰1买")
    
    # 测试 2: 发送重复信号 (应该被去重拦截)
    print("\n=== 测试场景 2: 重复信号去重 ===")
    time.sleep(1)
    send_test_signal(level="1m", signal="底背驰1买") 
