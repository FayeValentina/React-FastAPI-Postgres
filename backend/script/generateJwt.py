import base64
import json
import hmac
import hashlib
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta

class JWTProcessor:
    """
    JWT处理器类，用于生成和验证JWT令牌
    
    主要功能：
    1. 生成JWT令牌
    2. 验证JWT令牌
    3. 支持令牌过期时间设置
    4. 提供令牌解码功能
    """
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        """
        初始化JWT处理器
        
        Args:
            secret_key: 用于签名的密钥
            algorithm: 签名算法，默认为HS256
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        
    def _encode_base64url(self, data: bytes) -> str:
        """
        将数据进行Base64URL编码
        
        Args:
            data: 要编码的字节数据
            
        Returns:
            编码后的字符串
        """
        return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')
    
    def _decode_base64url(self, data: str) -> bytes:
        """
        对Base64URL编码的数据进行解码
        
        Args:
            data: Base64URL编码的字符串
            
        Returns:
            解码后的字节数据
        """
        padding = '=' * (4 - len(data) % 4)
        return base64.urlsafe_b64decode(data + padding)
    
    def _create_header(self) -> str:
        """
        创建JWT头部
        
        Returns:
            Base64URL编码的头部
        """
        header = {
            "alg": self.algorithm,
            "typ": "JWT"
        }
        return self._encode_base64url(json.dumps(header).encode('utf-8'))
    
    def _create_payload(self, data: Dict, expires_in: Optional[int] = None) -> str:
        """
        创建JWT载荷
        
        Args:
            data: 要包含在载荷中的数据
            expires_in: 过期时间（秒），None表示永不过期
            
        Returns:
            Base64URL编码的载荷
        """
        payload = data.copy()
        
        if expires_in is not None:
            exp_time = datetime.utcnow() + timedelta(seconds=expires_in)
            payload['exp'] = int(exp_time.timestamp())
            
        return self._encode_base64url(json.dumps(payload).encode('utf-8'))
    
    def _create_signature(self, header_b64: str, payload_b64: str) -> str:
        """
        创建JWT签名
        
        Args:
            header_b64: Base64URL编码的头部
            payload_b64: Base64URL编码的载荷
            
        Returns:
            Base64URL编码的签名
        """
        message = f"{header_b64}.{payload_b64}"
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return self._encode_base64url(signature)
    
    def generate_token(self, data: Dict, expires_in: Optional[int] = None) -> str:
        """
        生成JWT令牌
        
        Args:
            data: 要包含在令牌中的数据
            expires_in: 过期时间（秒），None表示永不过期
            
        Returns:
            JWT令牌字符串
        """
        header_b64 = self._create_header()
        payload_b64 = self._create_payload(data, expires_in)
        signature_b64 = self._create_signature(header_b64, payload_b64)
        
        return f"{header_b64}.{payload_b64}.{signature_b64}"
    
    def verify_token(self, token: str) -> Tuple[bool, Optional[Dict]]:
        """
        验证JWT令牌
        
        Args:
            token: JWT令牌字符串
            
        Returns:
            (是否有效, 载荷数据（如果有效）)
        """
        try:
            # 1. 分解令牌
            header_b64, payload_b64, received_signature = token.split('.')
            
            # 2. 验证签名
            expected_signature = self._create_signature(header_b64, payload_b64)
            if received_signature != expected_signature:
                return False, None
            
            # 3. 解码载荷
            payload = json.loads(self._decode_base64url(payload_b64))
            
            # 4. 检查是否过期
            if 'exp' in payload:
                exp_time = datetime.fromtimestamp(payload['exp'])
                if exp_time < datetime.utcnow():
                    return False, None
                
            return True, payload
            
        except Exception as e:
            return False, None
    
    def decode_token(self, token: str) -> Optional[Dict]:
        """
        解码JWT令牌（不验证签名）
        
        Args:
            token: JWT令牌字符串
            
        Returns:
            载荷数据（如果解码成功）
        """
        try:
            _, payload_b64, _ = token.split('.')
            return json.loads(self._decode_base64url(payload_b64))
        except Exception:
            return None

# 使用示例
if __name__ == "__main__":
    # 创建JWT处理器实例
    jwt_processor = JWTProcessor(secret_key="your-256-bit-secret")
    
    # 生成令牌（1小时后过期）
    data = {
        "user_id": 123,
        "role": "admin",
        "username": "张三"
    }
    token = jwt_processor.generate_token(data, expires_in=7200)
    print("生成的JWT令牌:", token)
    
    # 验证令牌
    is_valid, payload = jwt_processor.verify_token(token)
    if is_valid:
        print("令牌验证成功!")
        print("载荷数据:", payload)
    else:
        print("令牌无效!")
    
    # 仅解码令牌（不验证签名）
    decoded_payload = jwt_processor.decode_token(token)
    print("解码的载荷:", decoded_payload)