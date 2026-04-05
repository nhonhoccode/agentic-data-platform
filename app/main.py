from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from starlette.staticfiles import StaticFiles

from app.api.deps import ensure_api_security_config, require_api_key
from app.api.routes import router as api_router
from app.api.v2.routes import router as api_v2_router
from app.config import get_settings
from app.db.client import DatabaseClient
from app.ui.routes import router as ui_router

settings = get_settings()
STATIC_DIR = Path(__file__).resolve().parent / "ui" / "static"


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        ensure_api_security_config()
        yield

    app = FastAPI(
        title="Olist AI Data Platform API",
        version="0.1.0",
        description="Trusted analytics and multi-agent orchestration API for Olist dataset.",
        lifespan=lifespan,
    )

    app.mount("/ui/static", StaticFiles(directory=str(STATIC_DIR)), name="ui-static")

    @app.get("/health/liveness")
    def liveness() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/readiness")
    def readiness() -> dict[str, str]:
        try:
            db = DatabaseClient()
            db.run_system_query("SELECT 1 AS ok")
            return {"status": "ready"}
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=f"Not ready: {exc}") from exc

    @app.get("/health", dependencies=[Depends(require_api_key)])
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(ui_router)
    app.include_router(api_router)
    app.include_router(api_v2_router)
    return app


app = create_app()


def run_dev() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.app_port, reload=False)


if __name__ == "__main__":
    run_dev()
