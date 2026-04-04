from __future__ import annotations

import uvicorn
from fastapi import Depends, FastAPI

from app.api.deps import require_api_key
from app.api.routes import router as api_router
from app.config import get_settings
from app.ui.routes import router as ui_router

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Olist AI Data Platform API",
        version="0.1.0",
        description="Trusted analytics and multi-agent orchestration API for Olist dataset.",
    )

    @app.get("/health", dependencies=[Depends(require_api_key)])
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(ui_router)
    app.include_router(api_router)
    return app


app = create_app()


def run_dev() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.app_port, reload=False)


if __name__ == "__main__":
    run_dev()
