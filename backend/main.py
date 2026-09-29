from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from backend.admin.router import router as admin_router
from backend.auth.google_router import router as google_router
from backend.auth.router import router as auth_router
from backend.config import get_settings
from backend.db.session import DbSession, get_engine
from backend.errors import register_error_handlers
from backend.org.invite_router import router as invitations_router
from backend.org.router import router as org_router

API_PREFIX = "/api"


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Gatewise API",
        version="0.1.0",
        description="Authentication, organizations and role-based access control.",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
        lifespan=lifespan,
        debug=not settings.is_production,
    )
    register_error_handlers(app)
    for router in (auth_router, google_router, org_router, invitations_router, admin_router):
        app.include_router(router, prefix=API_PREFIX)

    @app.get(f"{API_PREFIX}/health", tags=["system"])
    async def health(db: DbSession) -> dict:
        result = await db.execute(text("select current_database(), version()"))
        database, version = result.one()
        return {
            "status": "ok",
            "database": database,
            "postgres": version.split(" on ")[0],
            "environment": settings.environment,
        }

    return app


app = create_app()
