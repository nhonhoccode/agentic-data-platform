from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
settings = get_settings()


def require_api_key(
    api_key: str | None = Security(api_key_header),
) -> None:
    if not settings.app_api_key:
        return

    if api_key != settings.app_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
