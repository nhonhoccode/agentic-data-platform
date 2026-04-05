from __future__ import annotations

import pytest

from app.api import deps


def test_ensure_api_security_config_blocks_insecure_non_dev(monkeypatch) -> None:
    monkeypatch.setattr(deps.settings, "app_env", "prod")
    monkeypatch.setattr(deps.settings, "app_api_key", "change-me")

    with pytest.raises(RuntimeError):
        deps.ensure_api_security_config()


def test_ensure_api_security_config_allows_dev(monkeypatch) -> None:
    monkeypatch.setattr(deps.settings, "app_env", "dev")
    monkeypatch.setattr(deps.settings, "app_api_key", "change-me")
    deps.ensure_api_security_config()
