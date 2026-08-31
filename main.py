import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config.config import settings
from config.db import AsyncSessionLocal, Base, engine, get_db
from routes.auth_routes import router as auth_router
from routes.member_routes import router as member_router
from routes.registration_routes import router as registration_router
from routes.upload_routes import router as upload_router
from utils.seed import seed_database

logger = logging.getLogger("orion.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize / create DB tables with UUIDv7
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Safe dev seed
    if settings.DEBUG:
        async with AsyncSessionLocal() as session:
            await seed_database(session)

    yield
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
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
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https: blob:; "
            "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 https://*; "
            "frame-ancestors 'none';"
        )
    return response


# 2. CORS configuration (environment-aware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)


# 3. Global Exception Handlers (Prevent stack trace & raw query leaks in production)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "message": "Format data permintaan tidak valid."},
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
    logger.error("Unhandled server exception: %s", exc, exc_info=True)
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


# API v1 Router with /orion/api/v1 prefix
api_v1_router = APIRouter(prefix=settings.API_V1_STR)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(registration_router)
api_v1_router.include_router(member_router)
api_v1_router.include_router(upload_router)

# Mount both prefixed and root routers for maximum compatibility
app.include_router(api_v1_router)
app.include_router(auth_router)
app.include_router(registration_router)
app.include_router(member_router)
app.include_router(upload_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "orion-backend",
        "version": settings.VERSION,
        "api_prefix": settings.API_V1_STR,
    }


@app.get(f"{settings.API_V1_STR}/health", tags=["Health"])
async def api_health_check():
    return {
        "status": "healthy",
        "service": "orion-backend",
        "version": settings.VERSION,
    }


@app.get("/db-test", tags=["Health"])
async def db_test(session: AsyncSession = Depends(get_db)):
    result = await session.execute(text("SELECT 1"))
    return {"status": "connected", "result": result.scalar()}
