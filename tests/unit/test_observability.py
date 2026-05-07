import os

import pytest


@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    for key in [
        "LANGSMITH_TRACING",
        "LANGCHAIN_TRACING_V2",
        "LANGSMITH_API_KEY",
        "LANGCHAIN_API_KEY",
        "LANGSMITH_PROJECT",
        "LANGCHAIN_PROJECT",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_configure_langsmith_disabled_returns_false(monkeypatch):
    from app.config import get_settings
    from app.observability import configure_langsmith

    get_settings.cache_clear()
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGSMITH_API_KEY", "")
    assert configure_langsmith() is False
    assert "LANGSMITH_API_KEY" not in os.environ or not os.environ["LANGSMITH_API_KEY"]


def test_configure_langsmith_no_key_returns_false(monkeypatch):
    from app.config import get_settings
    from app.observability import configure_langsmith

    get_settings.cache_clear()
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "")
    assert configure_langsmith() is False


def test_configure_langsmith_enabled_sets_env(monkeypatch):
    from app.config import get_settings
    from app.observability import configure_langsmith

    get_settings.cache_clear()
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key-123")
    monkeypatch.setenv("LANGSMITH_PROJECT", "test-project")
    assert configure_langsmith() is True
    assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"
    assert os.environ.get("LANGCHAIN_API_KEY") == "test-key-123"
    assert os.environ.get("LANGCHAIN_PROJECT") == "test-project"
