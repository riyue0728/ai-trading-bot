# 终极简化：最小测试服务器
from flask import Flask, request
import json

app = Flask(__name__)

@app.route('/')
def home():
    return "OK"

@app.route('/webhook', methods=['POST'])
def webhook():
    print(f"收到请求: {request.get_data()}")
    return {"status": "ok"}, 200

if __name__ == '__main__':
    print("启动最简服务器...")
    app.run(host='0.0.0.0', port=8000, threaded=True)
