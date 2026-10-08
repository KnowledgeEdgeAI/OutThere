class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)

    def as_dict(self) -> dict:
        result = {"code": self.code, "message": self.message}
        if self.code == "rate_limited":
            result["retry_after_ms"] = 60000
        return result
