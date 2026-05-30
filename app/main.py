from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.staticfiles import StaticFiles

from app.config import get_settings
from app.observability import configure_langsmith

configure_langsmith()

from app.api.deps import ensure_api_security_config, require_api_key  # noqa: E402
from app.api.v2.routes import router as api_v2_router  # noqa: E402
from app.db.client import DatabaseClient  # noqa: E402
from app.ui.routes import router as ui_router  # noqa: E402


# Shared limiter — exported so route modules can attach @limiter.limit(...) deps.
limiter = Limiter(key_func=get_remote_address, default_limits=[])

settings = get_settings()
STATIC_DIR = Path(__file__).resolve().parent / "ui" / "static"
_DIST_INDEX = STATIC_DIR / "dist" / "index.html"


def _spa_index_html() -> str:
    if _DIST_INDEX.exists():
        return _DIST_INDEX.read_text(encoding="utf-8")
    return (
        "<h1>Frontend not built. Run: cd frontend && npm install && npm run build</h1>"
    )


def _ensure_prod_secrets() -> None:
    """Fail-loud at startup if APP_ENV=prod but secrets are still defaults/weak.

    Prevents shipping `admin@123` / `change-me` to production by accident.
    """
    if not settings.is_non_dev:
        return  # dev/test — anything goes
    weak: list[str] = []
    if not settings.has_secure_api_key:
        weak.append("APP_API_KEY")
    if settings.app_admin_password in {"admin@123", "admin", "password", ""}:
        weak.append("APP_ADMIN_PASSWORD")
    if (
        not settings.app_session_secret
        or settings.app_session_secret in {"change-me", "change-me-session-secret"}
    ):
        weak.append("APP_SESSION_SECRET")
    if settings.postgres_password in {"olist", "postgres", "password", ""}:
        weak.append("POSTGRES_PASSWORD")
    if weak:
        raise RuntimeError(
            "APP_ENV=prod but the following secrets are still defaults/weak: "
            + ", ".join(weak)
            + ". Set strong values in .env before starting the server."
        )


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        ensure_api_security_config()
        _ensure_prod_secrets()
        yield

    app = FastAPI(
        title="Olist AI Data Platform API",
        version="0.1.0",
        description="Trusted analytics and multi-agent orchestration API for Olist dataset.",
        lifespan=lifespan,
    )

    # Per-IP rate limiting (slowapi). Routes opt-in via @limiter.limit(...).
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.mount("/ui/static", StaticFiles(directory=str(STATIC_DIR)), name="ui-static")

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def root() -> str:
        # Serve the SPA at the domain root so https://<host>/ lands directly on
        # the chat UI instead of forcing users to type /ui.
        return _spa_index_html()

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
    app.include_router(api_v2_router)
    return app


app = create_app()


def run_dev() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.app_port, reload=False)


if __name__ == "__main__":
    run_dev()
