from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
settings = get_settings()


def ensure_api_security_config() -> None:
    if settings.is_non_dev and not settings.has_secure_api_key:
        raise RuntimeError("APP_API_KEY is insecure for non-dev environment.")


def require_api_key(
    api_key: str | None = Security(api_key_header),
) -> None:
    try:
        ensure_api_security_config()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    if not settings.app_api_key:
        return

    if api_key != settings.app_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
