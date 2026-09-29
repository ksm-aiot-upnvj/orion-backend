import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config.config import settings
from config.db import AsyncSessionLocal, engine, ensure_enums_and_tables, get_db
from routes.auth_routes import router as auth_router
from routes.legacy_routes import router as legacy_router
from routes.log_routes import router as log_router
from routes.member_routes import router as member_router
from routes.registration_routes import router as registration_router
from routes.upload_routes import router as upload_router
from services.storage_service import StorageService
from utils.seed import seed_database

logger = logging.getLogger("orion.api")
templates = Jinja2Templates(directory="templates")


async def purge_staged_uploads_periodically(interval_seconds: int = 3600) -> None:
    """Remove staged uploads (tmp/) that were never saved with a form."""
    storage = StorageService()
    max_age = settings.STAGED_UPLOAD_TTL_HOURS * 3600
    while True:
        try:
            removed = await asyncio.to_thread(storage.purge_stale_staged, max_age)
            if removed:
                logger.info("Purged %d stale staged upload(s)", removed)
        except OSError as e:
            logger.warning("Staged upload purge failed: %s", e)
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize / create DB tables with UUIDv7 and ensure enum types exist
    async with engine.begin() as conn:
        await ensure_enums_and_tables(conn)

    # Safe dev seed
    if settings.DEBUG:
        async with AsyncSessionLocal() as session:
            await seed_database(session)

    purge_task = asyncio.create_task(purge_staged_uploads_periodically())
    yield
    purge_task.cancel()
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    root_path=settings.API_V1_STR,
    redoc_url=None,
    servers=[
        {
            "url": settings.API_V1_STR,
            "description": "Default API Server",
        },
        {
            "url": f"http://localhost:8000{settings.API_V1_STR}",
            "description": "Local Development Server",
        },
        {
            "url": f"http://127.0.0.1:8000{settings.API_V1_STR}",
            "description": "Localhost Server",
        },
    ],
    lifespan=lifespan,
)


# 1. Security Headers Middleware (OWASP Secure Headers Project)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    if "Content-Security-Policy" not in response.headers:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https: blob:; "
            "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 https://*; "
            "frame-ancestors 'none';"
        )
    return response


# 2. Transparent API prefix stripper middleware (handles /orion/api/v1 gracefully)
@app.middleware("http")
async def strip_api_prefix_middleware(request: Request, call_next):
    prefix = settings.API_V1_STR.rstrip("/")
    path = request.scope.get("path", "")
    if path == prefix or path.startswith(prefix + "/"):
        request.scope["path"] = path[len(prefix):] or "/"
        # Keep raw_path in sync, otherwise URLs rebuilt from the scope mix stripped and unstripped paths
        raw_path = request.scope.get("raw_path")
        if raw_path and raw_path.startswith(prefix.encode()):
            request.scope["raw_path"] = raw_path[len(prefix):] or b"/"
    return await call_next(request)


# 3. CORS configuration (environment-aware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins(),
    allow_origin_regex=settings.get_allowed_origin_regex(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)


from fastapi.encoders import jsonable_encoder


# 4. Global Exception Handlers (Prevent stack trace & raw query leaks in production)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(exc.errors()), "message": "Format data permintaan tidak valid."},
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error("Database error occurred: %s", exc, exc_info=settings.DEBUG)
    error_message = str(exc) if settings.DEBUG else "Terjadi kesalahan operasi database internal."
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": error_message, "error_code": "DB_ERROR"},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled server exception: %s", exc)
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )
    detail_msg = str(exc) if settings.DEBUG else "Terjadi kesalahan internal pada server. Silakan hubungi pengurus."
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": detail_msg, "error_code": "INTERNAL_SERVER_ERROR"},
    )


# Mount routers directly following Smart Hydroponic architecture:
# In OpenAPI schema, endpoints are clean (e.g. /auth/login, /audit-logs/)
# while the server base URL is /orion/api/v1.
# Legacy URL redirects first, so old paths like /members/count are not captured by /members/{identifier}
app.include_router(legacy_router)
app.include_router(auth_router)
app.include_router(registration_router)
app.include_router(member_router)
app.include_router(upload_router)
app.include_router(log_router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get(f"{settings.API_V1_STR}/", response_class=HTMLResponse, include_in_schema=False)
async def api_landing_page(request: Request):
    api_prefix = settings.API_V1_STR.rstrip("/")
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "title": settings.PROJECT_NAME,
            "description": "Backend API untuk manajemen KSM AIoT Orion.",
            "docs_url": f"{api_prefix}/docs",
            "health_url": f"{api_prefix}/health",
            "api_prefix": api_prefix,
        },
    )


@app.get("/health", tags=["Health"])
@app.get(f"{settings.API_V1_STR}/health", tags=["Health"], include_in_schema=False)
async def health_check():
    return {
        "status": "healthy",
        "service": "orion-backend",
        "version": settings.VERSION,
        "api_prefix": settings.API_V1_STR,
    }


@app.get("/health/db", tags=["Health"])
async def db_test(session: AsyncSession = Depends(get_db)):
    result = await session.execute(text("SELECT 1"))
    return {"status": "connected", "result": result.scalar()}
