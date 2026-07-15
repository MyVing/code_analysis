from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


class AppException(Exception):
    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.detail
        super().__init__(self.detail)


class ProjectNotFoundError(AppException):
    status_code = 404
    detail = "Project not found"


class TemplateNotFoundError(AppException):
    status_code = 404
    detail = "Template not found"


class SymbolNotFoundError(AppException):
    status_code = 404
    detail = "Symbol not found"


class FileNotFoundError(AppException):
    status_code = 404
    detail = "File not found"


class AnalysisError(AppException):
    status_code = 500
    detail = "Analysis failed"


class AnalysisInProgressError(AppException):
    status_code = 409
    detail = "Analysis already in progress"


class ProjectNotReadyError(AppException):
    status_code = 400
    detail = "Project is not ready"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": exc.errors()})
