"""玩家绑定验证服务"""
import secrets
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

@dataclass
class BindRequest:
    """绑定请求"""
    user_id: int
    player_name: str
    code: str
    created_at: float
    expires_at: float

class BindVerificationService:
    """玩家绑定验证服务 - 内存存储待验证的绑定请求"""
    
    CODE_LENGTH = 6
    CODE_EXPIRE_SECONDS = 300  # 5分钟过期
    
    def __init__(self):
        self._pending: Dict[str, BindRequest] = {}  # code -> BindRequest
        self._user_codes: Dict[int, str] = {}  # user_id -> code (每用户只能有一个待验证)
    
    def _cleanup_expired(self):
        """清理过期的请求"""
        now = time.time()
        expired_codes = [code for code, req in self._pending.items() if req.expires_at < now]
        for code in expired_codes:
            req = self._pending.pop(code, None)
            if req:
                self._user_codes.pop(req.user_id, None)
    
    def create_bind_request(self, user_id: int, player_name: str) -> str:
        """创建绑定请求，返回验证码"""
        self._cleanup_expired()
        
        # 取消该用户之前的请求
        old_code = self._user_codes.pop(user_id, None)
        if old_code:
            self._pending.pop(old_code, None)
        
        # 生成新验证码
        code = secrets.token_hex(self.CODE_LENGTH // 2).upper()
        now = time.time()
        
        request = BindRequest(
            user_id=user_id,
            player_name=player_name,
            code=code,
            created_at=now,
            expires_at=now + self.CODE_EXPIRE_SECONDS
        )
        
        self._pending[code] = request
        self._user_codes[user_id] = code
        
        return code
    
    def verify_code(self, code: str) -> Optional[Tuple[int, str]]:
        """验证码验证，返回 (user_id, player_name) 或 None"""
        self._cleanup_expired()
        
        code = code.upper().strip()
        request = self._pending.get(code)
        if not request:
            return None
        
        # 验证成功，移除请求
        self._pending.pop(code, None)
        self._user_codes.pop(request.user_id, None)
        
        return (request.user_id, request.player_name)
    
    def get_pending_request(self, user_id: int) -> Optional[BindRequest]:
        """获取用户的待验证请求"""
        self._cleanup_expired()
        code = self._user_codes.get(user_id)
        if code:
            return self._pending.get(code)
        return None
    
    def cancel_request(self, user_id: int) -> bool:
        """取消用户的绑定请求"""
        code = self._user_codes.pop(user_id, None)
        if code:
            self._pending.pop(code, None)
            return True
        return False

# 单例
bind_verification_service = BindVerificationService()
