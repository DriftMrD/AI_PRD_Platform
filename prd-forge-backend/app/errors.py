"""集中错误码常量模块。

所有路由层 / 适配器层统一从此处取错误码字符串，禁止散落硬编码。
错误事件经全局 handler 转换为 SSE `error` 事件，HTTP 状态码仍为 200。
"""

# 成功 / 流程码
OK = "OK"

# 文件相关
INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
FILE_TOO_LARGE = "FILE_TOO_LARGE"
FILE_PARSE_FAILED = "FILE_PARSE_FAILED"

# LLM 相关
LLM_AUTH = "LLM_AUTH"
LLM_TIMEOUT = "LLM_TIMEOUT"
LLM_UPSTREAM = "LLM_UPSTREAM"

# 客户端 / 系统
CLIENT_DISCONNECTED = "CLIENT_DISCONNECTED"
INTERNAL = "INTERNAL"

# 暴露的 9 个错误码（含 OK）
ALL_CODES: tuple[str, ...] = (
    OK,
    INVALID_FILE_TYPE,
    FILE_TOO_LARGE,
    FILE_PARSE_FAILED,
    LLM_AUTH,
    LLM_TIMEOUT,
    LLM_UPSTREAM,
    CLIENT_DISCONNECTED,
    INTERNAL,
)


class AppError(Exception):
    """统一应用异常。

    Attributes:
        code: 错误码常量（来自本模块）。
        message: 人类可读描述。
        retriable: 是否建议前端允许重试。
    """

    def __init__(self, code: str, message: str, retriable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retriable = retriable

    def to_dict(self) -> dict[str, object]:
        """转换为 SSE error 事件 data 字段。"""
        return {"code": self.code, "message": self.message, "retriable": self.retriable}
