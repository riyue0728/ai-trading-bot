# HEARTBEAT.md

# 缠机智投群自动监控

## 任务：每分钟主动检查群消息

**重要**：不依赖@触发，主动轮询群消息历史

### 频率
每1分钟检查一次

### 处理流程
1. 调用 sessions_history 获取群最新消息（limit=50）
2. 识别包含 "AI 分析完成" 的消息
3. 提取JSON格式的分析报告
4. 保存到 ai_analysis_summary.md
5. 下载并保存关联的截图

### 已知限制
- WeCom可能不传递机器人@AI的消息
- 如未收到，自动轮询作为备选方案
- ⚠️ 当前无法通过 sessions_history 访问企微群会话（只有私聊session可见）

### 保存路径
- 截图: `ai-trading-bot/ClawdBot_TradeSystem/screenshots/fuwguan/`
- 报告: `ai_analysis_summary.md`

### 状态
- [x] 已配置主动轮询
- [x] 代码已修复（save_to_summary 调用）
- [x] 服务已重启
- [x] 2026-05-16: 发现 sessions_history 无法访问企微群会话，仅能监控私聊

---
