import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app.database import create_db_and_tables, engine
from app.env import load_default_env_files
from app.routers import admin, ai, benefits, deals, price_reports, stations
from app.seed import seed_database


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Load local .env, initialize SQLite schema, and seed Gdansk sample data on startup."""
    load_default_env_files()
    create_db_and_tables(engine)
    with Session(engine) as session:
        seed_database(session)
    yield


def _get_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def create_app(*, enable_lifespan: bool = True) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Gdansk Fuel Deals API",
        version="0.1.0",
        lifespan=lifespan if enable_lifespan else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(stations.router)
    app.include_router(benefits.router)
    app.include_router(price_reports.router)
    app.include_router(deals.router)
    app.include_router(ai.router)
    app.include_router(admin.router)

    return app


app = create_app()
