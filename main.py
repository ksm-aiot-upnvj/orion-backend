from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import AsyncSessionLocal, Base, engine, get_db
from config.config import settings
from routes.auth_routes import router as auth_router
from routes.member_routes import router as member_router
from routes.registration_routes import router as registration_router
from utils.seed import seed_database


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
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API v1 Router with /orion/api/v1 prefix
api_v1_router = APIRouter(prefix=settings.API_V1_STR)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(registration_router)
api_v1_router.include_router(member_router)

# Mount both prefixed and root routers for maximum compatibility
app.include_router(api_v1_router)
app.include_router(auth_router)
app.include_router(registration_router)
app.include_router(member_router)


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
