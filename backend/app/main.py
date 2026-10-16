from fastapi import FastAPI, Depends, Response, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.core.database import engine, Base, get_db
from app.api.v1.api import api_router
from app.services.notifications.scheduler import notification_scheduler
# Import models to ensure they are registered with Base.metadata
import app.models

@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    import os
    from app.services.ai.gemini_provider import gemini_provider
    from app.config import BACKEND_ENV_PATH, reload_settings
    # Reload settings from disk to ensure freshest environment values
    reload_settings()
    logger = logging.getLogger("app.main")
    # Initialize database tables on startup ONLY if explicitly configured (never silently in production)
    if settings.AUTO_CREATE_TABLES:
        logger.info("Initializing database tables via Base.metadata.create_all (AUTO_CREATE_TABLES=True).")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        logger.info("Database schema auto-creation disabled. Schema management is enforced via Alembic migrations.")
    logger.info(
        "AI Provider diagnostic: configured=%s, model=%s, env_path=%s, env_exists=%s",
        gemini_provider.is_configured(),
        gemini_provider.model,
        BACKEND_ENV_PATH,
        os.path.exists(BACKEND_ENV_PATH)
    )
    notification_scheduler.start()
    yield
    # Cleanup
    await notification_scheduler.stop()
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_origin_regex=r"^https:\/\/.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include master API router with /api/v1 prefix and root fallback
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(api_router)

@app.get("/health", tags=["Health"])
@app.get("/healthz", tags=["Health"])
async def health_check(
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    import asyncio
    from sqlalchemy import text
    from app.services.ai.gemini_provider import gemini_provider
    from app.config import reload_settings
    reload_settings()

    # Lightweight database connectivity check (SELECT 1 with timeout)
    # Does not create, modify, or leak any database records or schemas
    db_healthy = False
    try:
        res = await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=3.0)
        scalar_val = res.scalar()
        if scalar_val == 1:
            db_healthy = True
    except Exception:
        db_healthy = False

    overall_status = "healthy" if db_healthy else "degraded"
    if not db_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    from app.services.email.provider import get_email_service_health
    from app.core.rate_limiter import get_rate_limiter_health

    email_health = get_email_service_health()
    limiter_health = get_rate_limiter_health()

    return {
        "status": overall_status,
        "service": "Contractly Legal Operations API",
        "version": settings.VERSION,
        "storage": settings.STORAGE_PROVIDER,
        "ai": {
            "configured": gemini_provider.is_configured(),
            "model": gemini_provider.model,
            "provider": "gemini"
        },
        "dependencies": {
            "database": {
                "status": "healthy" if db_healthy else "unhealthy"
            },
            "storage": {
                "provider": settings.STORAGE_PROVIDER,
                "status": "healthy"
            },
            "ai": {
                "provider": "gemini",
                "configured": gemini_provider.is_configured(),
                "model": gemini_provider.model
            },
            "scheduler": {
                "enabled": settings.NOTIFICATION_SCHEDULER_ENABLED,
                "interval_hours": settings.NOTIFICATION_SCHEDULER_INTERVAL_HOURS,
                "running": notification_scheduler.is_running
            },
            "email": email_health,
            "rate_limiter": limiter_health
        },
        "scheduler_running": notification_scheduler.is_running
    }

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Welcome to CONTRACTLY API — Intelligent Contract Lifecycle & Legal Operations Platform",
        "docs": "/docs",
        "health": "/health"
    }
