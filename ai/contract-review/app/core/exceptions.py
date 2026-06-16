class AppError(Exception):
    def __init__(self, message: str, code: str = "app_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, code="not_found")


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(message, code="validation_error")


class AnalysisError(AppError):
    def __init__(self, message: str):
        super().__init__(message, code="analysis_error")
