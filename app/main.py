import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api import certificates_router, health_router, jobs_router
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Bulk Certificate Generator API",
    version="1.0.0",
    description="Interview-ready API for asynchronous bulk certificate PDF generation.",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(health_router)
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(certificates_router, prefix="/api/v1")


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": "Invalid request data", "errors": exc.errors()})


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API error: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
