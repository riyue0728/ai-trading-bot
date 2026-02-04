# 极简测试 - 完全不依赖 utils/config
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def home():
    return {"status": "ok"}

@app.post("/test")
async def test(body: dict):
    print(f"收到请求: {body}")
    return {"received": body}

if __name__ == "__main__":
    print("启动测试服务器 (端口 5002)...")
    uvicorn.run(app, host="0.0.0.0", port=5002)
