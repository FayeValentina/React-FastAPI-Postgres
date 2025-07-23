import requests
import json

# 测试登录API
url = 'http://localhost:8000/api/v1/auth/login'
data = {
    'username': 'testuser',
    'password': 'test123456',
    'remember_me': True
}

try:
    print(f"尝试登录: {json.dumps(data)}")
    response = requests.post(url, json=data, timeout=10)
    print(f'状态码: {response.status_code}')
    print(f'响应内容: {response.text}')
except Exception as e:
    print(f'发生错误: {e}') 