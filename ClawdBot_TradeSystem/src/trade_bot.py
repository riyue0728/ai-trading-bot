from fastapi import FastAPI, Request, BackgroundTasks
from pydantic import BaseModel
import uvicorn
import time
import json
import logging
import os
from . import config, utils
from . import signal_tracker

app = FastAPI()
logger = utils.logger

# 信号缓存 (V2.0 去重)
SIGNAL_CACHE = {}

# 多品种周期配置
TICKER_CONFIG = {
    "XAUUSD": {
        "name": "黄金",
        "timeframes": ["1", "5", "25"],  # 1分钟、5分钟、25分钟
        "main_timeframe": "25",  # 主周期
        "trigger_levels": ["1m", "5m", "25m", "1", "5"]  # 触发层级
    },
    "BTCUSD": {
        "name": "比特币",
        "timeframes": ["5", "25", "120"],  # 5分钟、25分钟、2小时
        "main_timeframe": "120",  # 主周期 2小时
        "trigger_levels": ["5m", "25m", "2h", "5", "25", "120"]  # 触发层级
    }
}

def get_ticker_config(ticker):
    """获取品种配置"""
    # 尝试精确匹配或模糊匹配
    for key in TICKER_CONFIG:
        if key in ticker.upper() or ticker.upper() in key:
            return TICKER_CONFIG[key]
    # 默认返回黄金配置
    return TICKER_CONFIG["XAUUSD"]

def get_timeframes_for_ticker(ticker):
    """获取品种对应的周期列表"""
    config = get_ticker_config(ticker)
    return config["timeframes"]

# 预测记录文件
PREDICTION_FILE = os.path.join(os.path.dirname(__file__), '..', 'prediction.json')

def load_prediction():
    """加载上次预测"""
    if os.path.exists(PREDICTION_FILE):
        try:
            with open(PREDICTION_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return None

def save_prediction(prediction):
    """保存当前预测"""
    with open(PREDICTION_FILE, 'w') as f:
        json.dump(prediction, f, ensure_ascii=False)

def verify_prediction(current_price):
    """验证上次预测是否准确"""
    prev = load_prediction()
    if not prev:
        return None, "首次测试，无历史对比"
    
    prev_price = prev.get('price')
    prev_direction = prev.get('direction')
    prev_decision = prev.get('decision')
    
    if not prev_price:
        return None, "上次预测无价格数据"
    
    # 计算价格变化
    price_change = current_price - prev_price
    price_change_pct = (price_change / prev_price) * 100
    
    # 判断方向
    if price_change > 0:
        actual_direction = "上涨"
    elif price_change < 0:
        actual_direction = "下跌"
    else:
        actual_direction = "震荡"
    
    # 判断预测是否准确
    direction_correct = (actual_direction == prev_direction)
    
    if direction_correct:
        accuracy = "✅ 准确"
    else:
        accuracy = "❌ 不准确"
    
    result = {
        "prev_price": prev_price,
        "prev_direction": prev_direction,
        "prev_decision": prev_decision,
        "current_price": current_price,
        "actual_direction": actual_direction,
        "price_change": round(price_change, 2),
        "price_change_pct": round(price_change_pct, 2),
        "accuracy": accuracy
    }
    
    return result, f"{accuracy} | 方向: {prev_direction}→{actual_direction} | 涨跌: {price_change:+.2f}"

def process_signal_background(data):
    """
    后台任务：处理信号的耗时操作（截图、AI分析、自动验证）
    """
    try:
        ticker = data.get('symbol', data.get('ticker', 'Unknown'))
        signal = data.get('signal', 'Unknown')
        level = data.get('level', '1m')
        # 去掉level中的m后缀，例如 "120m" -> "120"
        level_clean = level.replace('m', '') if level else '1'
        price = data.get('price')
        chart_url = data.get('chart_url', config.get_chart_url(ticker))
        
        logger.info(f"⚙️ 开始后台处理: {ticker} {level} {signal}")
        
        # 0. 检查是否有历史预测需要验证
        verification_result = None
        if price and float(price) > 0:
            # 使用传入的价格或从视觉分析中提取
            pass
        
        # 1. 立即发送通知：信号已接收
        try:
            utils.send_alert(f"🚀 信号触发: {ticker} {level} {signal}", [], "")
        except Exception as e:
            logger.warning(f"初始通知失败: {e}")
        
        # 2. 多周期截图
        screenshot_paths = []
        
        # 获取该品种的周期配置
        ticker_config = get_ticker_config(ticker)
        timeframes = ticker_config["timeframes"]
        main_tf = ticker_config["main_timeframe"]
        
        logger.info(f"⚡ {ticker} 周期配置: {timeframes}")
        
        # 根据触发层级和品种配置决定截图周期
        trigger_levels = ticker_config["trigger_levels"]
        # 检查level是否在trigger_levels中（支持 "120m" 或 "120" 格式）
        level_match = level_clean in trigger_levels or level in trigger_levels
        if level_match:
            # 多周期共振分析
            logger.info(f"⚡ 触发多周期共振分析: {timeframes}")
            screenshot_paths = utils.capture_multi_timeframe(chart_url, ticker, timeframes)
        else:
            logger.info("⚡ 触发单周期分析...")
            path = utils.capture_single_snapshot(chart_url, ticker)
            screenshot_paths = [path]
            
        if not screenshot_paths:
            logger.error("❌ 截图失败")
            return
        
        # 3. AI 双脑分析
        vision_results = utils.analyze_multi_images(screenshot_paths, ticker)
        decision_json = utils.make_resonance_decision(data, vision_results)
        
        # 4. 提取当前价格
        current_price = None
        try:
            # 尝试从决策结果中提取价格
            import re
            price_match = re.search(r'"entry_price":\s*([\d.]+)', decision_json)
            if price_match:
                current_price = float(price_match.group(1))
        except:
            pass
        
        # 5. 保存当前预测
        prediction = {
            "timestamp": time.time(),
            "price": current_price,
            "decision": decision_json
        }
        save_prediction(prediction)
        
        # 6. 验证上次预测（如果有）
        if current_price:
            verification_result, verification_msg = verify_prediction(current_price)
        
        # 7. 发送最终报告（含验证结果）
        alert_text = f"✅ AI 分析完成 ({len(screenshot_paths)}周期共振)"
        if verification_result:
            alert_text += f"\n\n🔍 上次预测验证:\n{verification_msg}"
        
        utils.send_alert(alert_text, screenshot_paths, decision_json)
        
        # 8. 检查是否开仓
        try:
            # 提取决策结果
            import re
            decision_match = re.search(r'"决策":\s*"([^"]+)"', decision_json)
            ai_decision = decision_match.group(1) if decision_match else ""
            
            # 只处理强烈信号
            if "强烈买入" in ai_decision or "强烈卖出" in ai_decision:
                # 提取价格信息
                entry_match = re.search(r'"入场价":\s*([\d.]+)', decision_json)
                sl_match = re.search(r'"止损价":\s*([\d.]+)', decision_json)
                tp1_match = re.search(r'"T1止盈价":\s*([\d.]+)', decision_json)
                tp2_match = re.search(r'"T2止盈价":\s*([\d.]+)', decision_json)
                
                entry_price = float(entry_match.group(1)) if entry_match else (current_price or 0)
                stop_loss = float(sl_match.group(1)) if sl_match else None
                tp1 = float(tp1_match.group(1)) if tp1_match else None
                tp2 = float(tp2_match.group(1)) if tp2_match else None
                
                # 确定方向
                direction = "long" if "买入" in ai_decision else "short"
                
                # 保存信号
                signal_data = {
                    "ticker": ticker,
                    "direction": direction,
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "tp1": tp1,
                    "tp2": tp2,
                    "status": "pending",
                    "ai_decision": ai_decision,
                    "open_time": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                signal_id = signal_tracker.save_signal(signal_data)
                logger.info(f"📝 强烈信号已记录: {signal_id}")
                
                # 发送开仓成功通知
                emoji = "🟢" if direction == "long" else "🔴"
                msg = f"{emoji} 开仓成功!\n" \
                      f"方向: {'做多' if direction == 'long' else '做空'}\n" \
                      f"入场价: ${entry_price}\n" \
                      f"止损: ${stop_loss}\n" \
                      f"T1: ${tp1}\n" \
                      f"T2: ${tp2}"
                utils.send_alert(msg, screenshot_paths, decision_json)
        except Exception as ex:
            logger.warning(f"⚠️ 开仓处理失败: {ex}")
        
        logger.info(f"✅ 后台处理完成: {ticker}")
        
    except Exception as e:
        logger.error(f"❌ 后台处理异常: {e}", exc_info=True)

@app.get("/")
def home():
    return {"status": "running", "system": "ClawdBot Multi-Axis Trade System"}

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """
    ClawdBot 标准 Webhook 接收端点
    """
    try:
        raw_body = await request.body()
        data = json.loads(raw_body)
        
        ticker = data.get('symbol', data.get('ticker', 'Unknown'))
        signal = data.get('signal', 'Unknown')
        level = data.get('level', '1m')
        price = data.get('price')
        
        logger.info(f"📩 收到信号: {ticker} | {level} | {signal}")
        
        # 1. 信号去重 (V2.0)
        dedup_key = f"{ticker}_{signal}_{level}_{int(float(price or 0))}"
        now = time.time()
        if dedup_key in SIGNAL_CACHE and now - SIGNAL_CACHE[dedup_key] < config.SIGNAL_DUPLICATE_TIME:
            logger.warning(f"🚫 拦截重复信号: {dedup_key}")
            return {"status": "ignored", "msg": "Duplicate"}
        SIGNAL_CACHE[dedup_key] = now
        
        # 2. 将所有处理（包括通知）加入后台任务
        background_tasks.add_task(process_signal_background, data)
        
        return {"status": "accepted", "msg": "Signal processing in background"}
        
    except Exception as e:
        logger.error(f"❌ 系统异常: {e}")
        return {"status": "error", "msg": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host=config.HOST, port=config.PORT)
