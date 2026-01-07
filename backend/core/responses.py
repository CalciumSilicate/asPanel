"""统一 API 响应结构"""
from typing import Any, Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""
    ok: bool = True
    data: Optional[T] = None
    error: Optional[dict] = None
    message: Optional[str] = None


class ErrorDetail(BaseModel):
    """错误详情"""
    code: str
    message: str
    field: Optional[str] = None


def success(data: Any = None, message: str = None) -> dict:
    """返回成功响应"""
    response = {"ok": True}
    if data is not None:
        response["data"] = data
    if message:
        response["message"] = message
    return response


def error(code: str, message: str, status_code: int = 400) -> dict:
    """返回错误响应（用于 HTTPException 的 detail）"""
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message
        }
    }


# 常用错误码
class ErrorCodes:
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
