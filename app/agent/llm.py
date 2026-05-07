from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import get_settings


@lru_cache(maxsize=1)
def get_chat_llm() -> Any | None:
    settings = get_settings()
    provider = settings.llm_provider.strip().lower()

    if provider in {"", "none", "off", "disabled"}:
        return None

    if provider == "gemini" and settings.gemini_api_key:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.model_api_base or "gemini-2.5-flash",
            google_api_key=settings.gemini_api_key,
            temperature=settings.temperature,
        )

    if provider == "deepseek" and settings.deepseek_api_key:
        from langchain_openai import ChatOpenAI

        kwargs: dict[str, Any] = {
            "model": settings.model_api_base or "deepseek-v4-flash",
            "api_key": settings.deepseek_api_key,
            "base_url": "https://api.deepseek.com/v1",
            "temperature": settings.temperature,
            "timeout": 30,
            "max_retries": 1,
        }
        if not settings.llm_enable_thinking:
            kwargs["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": False},
            }
        return ChatOpenAI(**kwargs)

    if provider == "openrouter" and settings.openrouter_api_key:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openrouter_model,
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=settings.temperature,
            default_headers={
                "HTTP-Referer": "https://github.com/maximus-nhon/agentic-data-platform",
                "X-Title": "Olist AI Data Platform",
            },
        )

    if provider in {"self_host", "openai_compatible"}:
        if not (settings.openai_api_key and settings.base_url and settings.model_api_base):
            return None

        from langchain_openai import ChatOpenAI

        kwargs: dict[str, Any] = {
            "model": settings.model_api_base,
            "api_key": settings.openai_api_key,
            "base_url": settings.base_url,
            "temperature": settings.temperature,
        }
        if not settings.llm_enable_thinking:
            kwargs["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": False},
            }
        return ChatOpenAI(**kwargs)

    if provider == "openai" and settings.openai_api_key:
        from langchain_openai import ChatOpenAI

        kwargs: dict[str, Any] = {
            "model": settings.openai_model or "gpt-4o-mini",
            "api_key": settings.openai_api_key,
            "temperature": settings.temperature,
        }
        if settings.base_url:
            kwargs["base_url"] = settings.base_url
        return ChatOpenAI(**kwargs)

    return None


def llm_invoke_text(prompt: str) -> str | None:
    llm = get_chat_llm()
    if llm is None:
        return None
    try:
        response = llm.invoke(prompt)
        content = getattr(response, "content", "")
        return str(content).strip() if content else None
    except Exception:  # noqa: BLE001
        return None
