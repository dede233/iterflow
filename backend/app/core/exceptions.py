class AppError(Exception):
    def __init__(self, code: int, message: str, status_code: int = 400, data=None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data
        super().__init__(message)


class ConflictError(AppError):
    def __init__(self, message: str, data=None, code: int = 40910):
        super().__init__(code, message, 409, data)


class PermissionDenied(AppError):
    def __init__(self, message: str = "无权限执行该操作"):
        super().__init__(40301, message, 403)


class NotFoundError(AppError):
    def __init__(self, message: str = "记录不存在"):
        super().__init__(40401, message, 404)
