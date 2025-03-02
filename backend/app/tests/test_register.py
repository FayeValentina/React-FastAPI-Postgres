import requests
import json

# 测试注册API
url = 'http://localhost:8000/api/v1/auth/register'
data = {
    'username': 'testuser',
    'email': 'testuser@example.com',
    'password': 'test123456',
    'full_name': 'Test User'
}

try:
    print(f"尝试注册: {json.dumps(data)}")
    response = requests.post(url, json=data, timeout=10)
    print(f'状态码: {response.status_code}')
    print(f'响应内容: {response.text}')
except Exception as e:
    print(f'发生错误: {e}') 