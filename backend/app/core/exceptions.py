from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ProjectNotFoundError(Exception):
    pass


class AnalysisError(Exception):
    pass


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProjectNotFoundError)
    async def project_not_found_handler(request: Request, exc: ProjectNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(AnalysisError)
    async def analysis_error_handler(request: Request, exc: AnalysisError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})
