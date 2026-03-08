# -*- coding: utf-8 -*-
"""
自动盯盘追踪模块
- 定时检查持仓价格
- 自动标记止盈/止损
- T1 到达时：截图 + AI 分析 1 分钟走势，决定是否继续持有到 T2
- 推送平仓通知
"""

import json
import time
import logging
import base64
from pathlib import Path
from datetime import datetime
import requests
import config

logger = logging.getLogger("ClawBot")

# 记录文件
SIGNALS_FILE = Path(__file__).parent.parent / "signals_history.json"

# GoldAPI 配置
GOLD_API_KEY = "goldapi-bjhc1smldqlqws-io"

# 企业微信通知
WECHAT_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=dbf4f375-3c85-4050-b64d-0f862167be4c"

# AI 配置
GEMINI_API_KEY = "AIzaSyAJYOcBuiwzpVKDSbvNYaJfkywQ8ANXi1U"
GEMINI_MODEL = "gemini-2.5-flash"

def get_xau_price():
    """获取 XAU/USD 当前价格"""
    try:
        url = "https://api.gold-api.com/price/XAU"
        headers = {"Authorization": f"Bearer {GOLD_API_KEY}"}
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return float(data.get('price', 0))
    except Exception as e:
        logger.warning(f"获取价格失败: {e}")
    return None

def notify_wechat(message):
    """发送企业微信通知"""
    try:
        data = {"msgtype": "text", "text": {"content": message}}
        resp = requests.post(WECHAT_WEBHOOK_URL, json=data, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"企微通知失败: {e}")
        return False

def take_screenshot():
    """截图当前图表"""
    try:
        from playwright.sync_api import sync_playwright
        
        chart_url = getattr(config, 'DEFAULT_CHART_URL', 'https://cn.tradingview.com/chart/PP8uCQUu/')
        
        screenshot_path = "/tmp/t1_analysis.png"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(chart_url, timeout=30000)
            page.wait_for_timeout(4000)
            
            # 关闭所有可见弹窗
            popup_selectors = [
                # 文本按钮
                'button:has-text("Accept")', 'button:has-text("Agree")', 
                'button:has-text("Close")', 'button:has-text("OK")',
                'button:has-text("Got it")', 'button:has-text("Dismiss")',
                'button:has-text("No thanks")', 'button:has-text("Later")',
                'button:has-text("Cancel")', 'button:has-text("No")',
                # CSS 选择器
                '.tv-dialog__close', '.tv-dialog__close-button',
                '.tv-popup__close', '.js-close',
                '.apply-common-tooltip__close-btn', '.tv-notification__close',
                '.close-ico', '[aria-label="Close"]',
                '[aria-label="关闭"]', '[data-qa="close_button"]',
                '[data-qa="close"]', '[data-qa="dismiss"]',
                '.getstarted-popup__close', '.onboarding-modal__close',
                '.signup-modal__close', '.tv-promotion-modal__close',
                # Premium 弹窗
                '.tv-premium-modal button', '.tv-special-offer-modal button',
                '[data-modal-id="premium"] button',
                # News 弹窗
                '.tv-newsletter-modal button', '.tv-email-modal button',
                '[data-modal="newsletter"] button',
                # 通用关闭
                '.tv-dialog button', '.tv-popup button',
                '.tv-modal button', '.tv-widget .close',
                'div[class*="close"] button'
            ]
            
            for selector in popup_selectors:
                try:
                    elements = page.query_selector_all(selector)
                    for el in elements[:3]:  # 最多尝试3个
                        if el.is_visible():
                            el.click(timeout=1000)
                            time.sleep(0.3)
                except: pass
            
            time.sleep(2)
            page.screenshot(path=screenshot_path, full_page=True)
            browser.close()
        
        with open(screenshot_path, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        logger.warning(f"截图失败: {e}")
        return None

def analyze_with_gemini_t1(img_b64, direction, entry_price, current_price, tp2):
    """使用 Gemini 分析 T1 到达后的 1 分钟走势"""
    try:
        api_key = GEMINI_API_KEY
        model = GEMINI_MODEL
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        prompt = f"""持仓已达到 T1 止盈目标。请分析当前 1 分钟图表走势，决定是否继续持有到 T2。

**当前持仓信息：**
- 方向: {direction} ({"做多" if direction == "long" else "做空"})
- 入场价: {entry_price}
- 当前价: {current_price}
- T2 目标: {tp2}

**请分析：**
1. 当前 1 分钟走势是否还在延续？
2. 有无反转信号？（顶背驰/底背驰、RSI 超买/超卖、趋势线突破等）
3. 建议：继续持有到 T2，还是现在止盈？

**输出 JSON 格式：**
{{
    "建议": "继续持有到 T2" 或 "现在止盈",
    "原因": "详细说明",
    "信心度": "高/中/低"
}}

只输出 JSON，不要其他文字。"""

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/png", "data": img_b64}}
                ]
            }]
        }
        
        resp = requests.post(url, json=payload, timeout=60)
        if resp.status_code == 200:
            result = resp.json()
            if "candidates" in result:
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                text = text.replace("```json", "").replace("```", "").strip()
                return text
    except Exception as e:
        logger.warning(f"AI 分析失败: {e}")
    return None

def check_and_close_positions():
    """检查所有持仓，判断是否需要平仓"""
    try:
        if not SIGNALS_FILE.exists():
            return
        
        signals = json.loads(SIGNALS_FILE.read_text(encoding='utf-8'))
        
        current_price = get_xau_price()
        if not current_price:
            logger.warning("无法获取当前价格")
            return
        
        logger.info(f"🔔 价格检查: XAU=${current_price:.2f}")
        
        updated = False
        for s in signals:
            if s.get("status") != "pending":
                continue
            
            ticker = s.get("ticker", "XAU")
            direction = s.get("direction")
            entry_price = s.get("entry_price", 0)
            stop_loss = s.get("stop_loss", 0)
            tp1 = s.get("take_profit_1", 0)
            tp2 = s.get("take_profit_2", 0)
            ai_decision = s.get("ai_decision", "")
            just_reached_t1 = s.get("just_reached_t1", False)
            pending_ai_decision = s.get("pending_ai_decision", False)
            
            if not entry_price or entry_price == 0:
                continue
            
            # 计算浮动盈亏
            pnl_pct = round((current_price - entry_price) / entry_price * 100, 2) if direction == "long" else round((entry_price - current_price) / entry_price * 100, 2)
            
            close_reason = None
            close_price = 0
            
            if direction == "long":
                # 做多
                if stop_loss > 0 and current_price <= stop_loss:
                    close_reason = "sl"
                    close_price = stop_loss
                elif tp1 > 0 and current_price >= tp1:
                    if not just_reached_t1:
                        # 首次达到 T1：截图 + AI 分析
                        s["just_reached_t1"] = True
                        s["t1_price"] = tp1
                        s["t1_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        s["pending_ai_decision"] = True  # 标记需要 AI 分析
                        updated = True
                        
                        msg = f"🎯 达到 T1 止盈目标！\n" \
                              f"品种: {ticker}\n" \
                              f"方向: {direction}\n" \
                              f"入场: ${entry_price}\n" \
                              f"当前: ${current_price}\n" \
                              f"T1止盈: ${tp1}\n" \
                              f"T2止盈: ${tp2}\n" \
                              f"浮动盈亏: {pnl_pct:+.2f}%\n" \
                              f"─────────────────\n" \
                              f"⏳ 正在截图 + AI 分析 1 分钟走势..."
                        notify_wechat(msg)
                        logger.info(f"🔔 达到 T1: {ticker}，等待 AI 分析")
                        continue
                    elif pending_ai_decision:
                        # 已标记需要 AI 分析，现在执行
                        s["pending_ai_decision"] = False
                        updated = True
                        
                        # 截图并分析
                        img_b64 = take_screenshot()
                        if img_b64:
                            analysis = analyze_with_gemini_t1(img_b64, direction, entry_price, current_price, tp2)
                            if analysis:
                                try:
                                    import re
                                    suggestion = re.search(r'"建议":\s*"([^"]+)"', analysis)
                                    reason = re.search(r'"原因":\s*"([^"]+)"', analysis)
                                    confidence = re.search(r'"信心度":\s*"([^"]+)"', analysis)
                                    
                                    advice = suggestion.group(1) if suggestion else "继续持有到 T2"
                                    reason_text = reason.group(1) if reason else ""
                                    confidence_text = confidence.group(1) if confidence else "中"
                                    
                                    s["t1_analysis"] = {
                                        "analysis": analysis,
                                        "advice": advice,
                                        "reason": reason_text,
                                        "confidence": confidence_text,
                                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    }
                                    
                                    if "止盈" in advice:
                                        # AI 建议止盈
                                        close_reason = "tp"
                                        close_price = current_price
                                        s["close_reason"] = "t1_ai_close"
                                    else:
                                        # AI 建议继续持有
                                        s["stop_loss"] = entry_price  # 止损移到开仓价
                                        msg = f"🤖 AI 分析结果\n" \
                                              f"建议: {advice}\n" \
                                              f"原因: {reason_text}\n" \
                                              f"信心度: {confidence_text}\n" \
                                              f"─────────────────\n" \
                                              f"✅ 已将止损移到开仓价，继续持有到 T2..."
                                        notify_wechat(msg)
                                        logger.info(f"🔔 AI 分析: {advice}")
                                except Exception as e:
                                    logger.warning(f"解析 AI 分析失败: {e}")
                                    s["stop_loss"] = entry_price
                            else:
                                s["stop_loss"] = entry_price
                        else:
                            s["stop_loss"] = entry_price
                    elif tp2 > 0 and current_price >= tp2:
                        close_reason = "tp"
                        close_price = tp2
                        
            elif direction == "short":
                # 做空
                if stop_loss > 0 and current_price >= stop_loss:
                    close_reason = "sl"
                    close_price = stop_loss
                elif tp1 > 0 and current_price <= tp1:
                    if not just_reached_t1:
                        s["just_reached_t1"] = True
                        s["t1_price"] = tp1
                        s["t1_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        s["pending_ai_decision"] = True
                        updated = True
                        
                        msg = f"🎯 达到 T1 止盈目标！\n" \
                              f"品种: {ticker}\n" \
                              f"方向: {direction}\n" \
                              f"入场: ${entry_price}\n" \
                              f"当前: ${current_price}\n" \
                              f"T1止盈: ${tp1}\n" \
                              f"T2止盈: ${tp2}\n" \
                              f"浮动盈亏: {pnl_pct:+.2f}%\n" \
                              f"─────────────────\n" \
                              f"⏳ 正在截图 + AI 分析 1 分钟走势..."
                        notify_wechat(msg)
                        logger.info(f"🔔 达到 T1: {ticker}，等待 AI 分析")
                        continue
                    elif pending_ai_decision:
                        s["pending_ai_decision"] = False
                        updated = True
                        
                        img_b64 = take_screenshot()
                        if img_b64:
                            analysis = analyze_with_gemini_t1(img_b64, direction, entry_price, current_price, tp2)
                            if analysis:
                                try:
                                    import re
                                    suggestion = re.search(r'"建议":\s*"([^"]+)"', analysis)
                                    reason = re.search(r'"原因":\s*"([^"]+)"', analysis)
                                    confidence = re.search(r'"信心度":\s*"([^"]+)"', analysis)
                                    
                                    advice = suggestion.group(1) if suggestion else "继续持有到 T2"
                                    reason_text = reason.group(1) if reason else ""
                                    confidence_text = confidence.group(1) if confidence else "中"
                                    
                                    s["t1_analysis"] = {
                                        "analysis": analysis,
                                        "advice": advice,
                                        "reason": reason_text,
                                        "confidence": confidence_text,
                                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    }
                                    
                                    if "止盈" in advice:
                                        close_reason = "tp"
                                        close_price = current_price
                                        s["close_reason"] = "t1_ai_close"
                                    else:
                                        s["stop_loss"] = entry_price
                                        msg = f"🤖 AI 分析结果\n" \
                                              f"建议: {advice}\n" \
                                              f"原因: {reason_text}\n" \
                                              f"信心度: {confidence_text}\n" \
                                              f"─────────────────\n" \
                                              f"✅ 已将止损移到开仓价，继续持有到 T2..."
                                        notify_wechat(msg)
                                except Exception as e:
                                    logger.warning(f"解析 AI 分析失败: {e}")
                                    s["stop_loss"] = entry_price
                        else:
                            s["stop_loss"] = entry_price
                    elif tp2 > 0 and current_price <= tp2:
                        close_reason = "tp"
                        close_price = tp2
            
            if close_reason:
                final_pnl = round((close_price - entry_price) / entry_price * 100, 2) if direction == "long" else round((entry_price - close_price) / entry_price * 100, 2)
                
                s["status"] = "closed"
                s["close_reason"] = close_reason
                s["close_price"] = close_price
                s["pnl_pct"] = final_pnl
                s["result_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                updated = True
                
                emoji = "✅" if final_pnl > 0 else "❌"
                reached = "T2" if s.get("just_reached_t1") and s.get("close_reason") == "tp" else ""
                if s.get("close_reason") == "t1_ai_close":
                    reached = "T1_AI止盈"
                msg = f"{emoji} 平仓提醒\n" \
                      f"品种: {ticker}\n" \
                      f"方向: {direction}\n" \
                      f"入场: ${entry_price}\n" \
                      f"平仓: ${close_price}\n" \
                      f"原因: {'止盈' if close_reason == 'tp' else '止损'} {reached}\n" \
                      f"盈亏: {final_pnl:+.2f}%"
                notify_wechat(msg)
                
                logger.info(f"🔔 平仓: {ticker} {direction} @ {entry_price} -> {close_price} ({final_pnl:+.2f}%)")
        
        if updated:
            SIGNALS_FILE.write_text(json.dumps(signals, ensure_ascii=False, indent=2))
            logger.info(f"✅ 更新记录")
            
    except Exception as e:
        logger.error(f"❌ 检查持仓失败: {e}")

def run_monitor():
    """运行一次监控检查"""
    logger.info("🔔 运行自动盯盘检查...")
    check_and_close_positions()

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')    
    if len(sys.argv) > 1 and sys.argv[1] == "daemon":
        while True:
            run_monitor()
            time.sleep(300)
    else:
        run_monitor()
