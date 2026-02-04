# 502 错误根本原因与解决方案

## 问题现象
- ClawdBot_TradeSystem 目录下的所有 POST 请求返回 502 Bad Gateway
- 原版 jiqiren 目录下的相同代码工作正常
- 服务器启动成功但请求无法到达

## 根本原因
**Windows 系统代理拦截了 POST 请求！**

Python 的 `requests` 库默认会读取系统环境变量中的代理设置（`HTTP_PROXY`, `HTTPS_PROXY`），
当系统配置了代理但代理服务不可用时，所有请求都会被发送到代理服务器，导致 502 错误。

## 解决方案
在所有使用 `requests.post()` 的地方，禁用环境代理：

```python
# 错误的写法（会读取系统代理）
response = requests.post(url, json=data)

# 正确的写法（禁用代理）
session = requests.Session()
session.trust_env = False  # 关键！
response = session.post(url, json=data)
```

## 验证
修复后：
- ✅ 测试脚本成功发送请求
- ✅ 服务器成功接收处理
- ✅ Playwright 启动截图
- ✅ AI 分析正常工作
- ✅ 企业微信通知发送成功

## 已修复的文件
1. `simple_test.py` - 添加 `session.trust_env = False`
2. `test_simulation.py` - 添加 `session.trust_env = False`
3. (原版 `test_signal.py` 早已包含此修复)
