import requests

print("测试极简 FastAPI...")
resp = requests.post("http://127.0.0.1:5002/test", json={"hello": "world"})
print(f"响应状态: {resp.status_code}")
print(f"响应内容: {resp.json()}")
