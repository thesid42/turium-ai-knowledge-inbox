import contextlib
import logging
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette import status

from app.config import Settings, create_settings, get_settings
from app.db import init_schema
from app.errors import AppError
from app.logging_config import request_id_var, setup_logging
from app.providers.factory import build_providers
from app.routers import health_router, ingest_router, items_router, query_router
from app.schemas import ErrorResponse

# Context variable for request ID
_request_id_var: ContextVar[str] = request_id_var


def create_app(settings: Settings | None = None, embedding_provider=None, chat_provider=None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: create DB parent dir and init schema
        from app.db import get_connection
        conn = get_connection(settings)
        try:
            init_schema(conn)
        finally:
            conn.close()

        # Build providers if not injected
        if embedding_provider is None or chat_provider is None:
            emb, chat = build_providers(settings)
            app.state.embedding_provider = emb
            app.state.chat_provider = chat
        else:
            app.state.embedding_provider = embedding_provider
            app.state.chat_provider = chat_provider

        logger.info("Application startup complete")
        yield
        # Shutdown
        logger.info("Application shutdown")

    app = FastAPI(
        title="Turium API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Override Settings dependency for tests
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings

    # CORS - permissive for dev
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID middleware
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        _request_id_var.set(request_id)

        import time
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = int((time.perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = request_id

        logger = logging.getLogger("turium.request")
        logger.info(
            "Request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    # Exception handlers
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error={"code": exc.code, "message": exc.message, "details": exc.details}).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        errors = []
        for err in exc.errors():
            errors.append({
                "loc": list(err["loc"]),
                "msg": err["msg"],
                "type": err["type"],
            })
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(error={"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": errors}}).model_dump(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        # Map common HTTP status codes to our error codes
        code_map = {
            404: "NOT_FOUND",
            405: "INTERNAL_ERROR",  # Method not allowed - not in spec, treat as internal
        }
        error_code = code_map.get(exc.status_code, "INTERNAL_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error={"code": error_code, "message": exc.detail, "details": None}).model_dump(),
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        logger = logging.getLogger("turium.error")
        logger.exception("Unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(error={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": None}).model_dump(),
        )

    # Include routers
    app.include_router(health_router)
    app.include_router(ingest_router)
    app.include_router(items_router)
    app.include_router(query_router)

    return app


# Module-level app for uvicorn
app = create_app()