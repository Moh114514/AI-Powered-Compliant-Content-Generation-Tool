"""统一响应封装：{success, data, message, request_id, error_code}。"""
import uuid
import datetime


def ok(data: any = None, message: str | None = None) -> dict:
    return {
        "success": True,
        "data": data,
        "message": message,
        "request_id": uuid.uuid4().hex[:16],
    }


def fail(message: str, error_code: str = "INTERNAL_ERROR", data: any = None) -> dict:
    return {
        "success": False,
        "data": data,
        "message": message,
        "error_code": error_code,
        "request_id": uuid.uuid4().hex[:16],
    }


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")
