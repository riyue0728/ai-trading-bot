@echo off
echo ========================================
echo  ClawdBot 交易系统 V2.0 启动脚本
echo ========================================
echo.

echo [1/3] 检查依赖...
pip install fastapi uvicorn python-dotenv requests playwright >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 依赖安装失败，请检查网络连接
    pause
    exit /b 1
)
echo ✅ 依赖检查完成

echo.
echo [2/3] 启动 FastAPI 服务器 (端口 8000)...
echo 提示: 按 Ctrl+C 可停止服务
echo.
python -m uvicorn src.trade_bot:app --host 0.0.0.0 --port 8000 --reload

pause
