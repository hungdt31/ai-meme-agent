class ApiError(Exception):
    """Lỗi trả cho client dạng {"code", "message"}."""

    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message
