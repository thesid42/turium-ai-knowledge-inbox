from typing import Any


class AppError(Exception):
    def __init__(self, code: str, status_code: int, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.status_code = status_code
        self.message = message
        self.details = details
        super().__init__(message)


ERROR_CODES: dict[str, tuple[int, str]] = {
    "VALIDATION_ERROR": (422, "Validation error"),
    "NOT_FOUND": (404, "Not found"),
    "DUPLICATE_ITEM": (409, "Duplicate item"),
    "INVALID_URL": (400, "Invalid URL"),
    "BLOCKED_URL": (400, "Blocked URL"),
    "UNSUPPORTED_CONTENT_TYPE": (415, "Unsupported content type"),
    "CONTENT_TOO_LARGE": (413, "Content too large"),
    "FETCH_FAILED": (502, "Fetch failed"),
    "UPSTREAM_AI_ERROR": (502, "Upstream AI error"),
    "INTERNAL_ERROR": (500, "Internal error"),
}


def create_error(code: str, message: str, details: dict[str, Any] | None = None) -> AppError:
    status_code, _ = ERROR_CODES.get(code, (500, "Internal error"))
    return AppError(code=code, status_code=status_code, message=message, details=details)