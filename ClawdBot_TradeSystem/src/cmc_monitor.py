# -*- coding: utf-8 -*-
"""
CoinMarketCap 监控模块
- BTC 价格监控
- 热点新闻追踪
- 价格异动提醒
"""

import requests
import time
import json
from datetime import datetime
import logging

logger = logging.getLogger("ClawBot")

# CoinGecko 免费 API（无需密钥）
COINGECKO_URL = "https://api.coingecko.com/api/v3"

def get_btc_price():
    """获取 BTC 价格（从 CoinGecko）"""
    try:
        url = f"{COINGECKO_URL}/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true&include_market_cap=true"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if "bitcoin" in data:
                btc = data["bitcoin"]
                return {
                    "price": btc.get("usd", 0),
                    "change_24h": btc.get("usd_24h_change", 0),
                    "volume_24h": btc.get("usd_24h_vol", 0),
                    "market_cap": btc.get("usd_market_cap", 0)
                }
    except Exception as e:
        logger.warning(f"获取 BTC 价格失败: {e}")
    return None

def get_top_cryptos(limit=10):
    """获取市值前10加密货币（从 CoinGecko）"""
    try:
        url = f"{COINGECKO_URL}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page={limit}&page=1&sparkline=false"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            cryptos = []
            for item in data:
                cryptos.append({
                    "name": item.get("name"),
                    "symbol": item.get("symbol").upper(),
                    "price": item.get("current_price", 0),
                    "change_24h": item.get("price_change_percentage_24h", 0),
                    "market_cap": item.get("market_cap", 0)
                })
            return cryptos
    except Exception as e:
        logger.warning(f"获取加密货币列表失败: {e}")
    return []

def check_price_alert():
    """检查价格异动，返回需要提醒的内容"""
    alerts = []
    
    btc_data = get_btc_price()
    if btc_data and btc_data["price"] > 0:
        # 检测 24h 涨跌异常
        if abs(btc_data["change_24h"]) > 5:  # 24h 涨跌超 5%
            alerts.append({
                "type": "btc_movement",
                "title": "BTC 价格异动",
                "content": f"BTC 24h 涨跌幅: {btc_data['change_24h']:+.2f}%"
            })
    
    return alerts

def get_market_summary():
    """获取市场摘要"""
    btc_data = get_btc_price()
    cryptos = get_top_cryptos(10)
    
    summary = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "btc": btc_data,
        "top_gainers": [c for c in cryptos if c.get("change_24h", 0) > 0][:3],
        "top_losers": [c for c in cryptos if c.get("change_24h", 0) < 0][:3]
    }
    return summary

# 测试
if __name__ == "__main__":
    print("=== CoinMarketCap 监控测试 ===")
    btc = get_btc_price()
    if btc:
        print(f"BTC 价格: ${btc['price']:,.2f}")
        print(f"24h 涨跌: {btc['change_24h']:+.2f}%")
    cryptos = get_top_cryptos(5)
    print(f"\n市值前5:")
    for c in cryptos:
        print(f"  {c['symbol']}: ${c['price']:,.2f} ({c['change_24h']:+.2f}%)")
