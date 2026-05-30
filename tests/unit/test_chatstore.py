"""Unit tests for chatstore CRUD + IDOR safety + payload cap.

Uses a tmp data_dir so the production chat.db is never touched.
"""

from __future__ import annotations

import os
from typing import Any

import pytest


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Spin up a chatstore that writes into a tmp directory."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    # Force settings reload so the new DATA_DIR is picked up.
    from app import config

    config.get_settings.cache_clear()  # type: ignore[attr-defined]
    # Reload the module so module-level state (path resolver) uses tmp data_dir.
    import importlib

    from app.ui import chatstore  # noqa: WPS433

    importlib.reload(chatstore)
    return chatstore


def test_create_and_list(store) -> None:
    cid = store.create_conversation("alice", "My chat")
    assert cid
    convs = store.list_conversations("alice")
    assert len(convs) == 1
    assert convs[0]["title"] == "My chat"


def test_idor_rejection(store) -> None:
    cid = store.create_conversation("alice", "secret")
    # Bob should NOT see alice's conversation
    assert store.list_conversations("bob") == []
    assert store.get_conversation("bob", cid) is None
    with pytest.raises(PermissionError):
        store.append_message(cid, "bob", "user", "hello", None)
    assert store.list_messages(cid, "bob") == []


def test_append_and_list_messages_order(store) -> None:
    cid = store.create_conversation("alice", "ordered")
    store.append_message(cid, "alice", "user", "first", None)
    store.append_message(cid, "alice", "assistant", "second", None)
    store.append_message(cid, "alice", "user", "third", None)
    msgs = store.list_messages(cid, "alice", limit=10)
    assert [m["content"] for m in msgs] == ["first", "second", "third"]
    assert msgs[0]["sequence_no"] < msgs[-1]["sequence_no"]


def test_list_messages_returns_last_n(store) -> None:
    cid = store.create_conversation("alice", "long")
    for i in range(30):
        store.append_message(cid, "alice", "user", f"msg-{i:02d}", None)
    last10 = store.list_messages(cid, "alice", limit=10)
    assert len(last10) == 10
    assert last10[0]["content"] == "msg-20"
    assert last10[-1]["content"] == "msg-29"


def test_delete_cascades_messages(store) -> None:
    cid = store.create_conversation("alice", "x")
    store.append_message(cid, "alice", "user", "hi", None)
    assert store.delete_conversation("alice", cid) is True
    assert store.list_messages(cid, "alice") == []


def test_rename_only_if_default(store) -> None:
    cid = store.create_conversation("alice", "New chat")
    # only_if_default succeeds when title is the placeholder
    assert store.rename_conversation("alice", cid, "auto-titled", only_if_default=True)
    # second auto-rename should be a no-op
    assert (
        store.rename_conversation("alice", cid, "another", only_if_default=True)
        is False
    )
    # explicit rename always works
    assert store.rename_conversation("alice", cid, "manual", only_if_default=False)


def test_payload_cap_drops_oversized_blocks(store) -> None:
    cid = store.create_conversation("alice", "x")
    big_data = [{"row": i} for i in range(500)]
    payload: dict[str, Any] = {
        "intent": "sql_query",
        "raw_result": {"data": big_data, "row_count": 500},
        "tool_calls": [{"tool": "t1", "detail": "x" * 5000}],
    }
    store.append_message(cid, "alice", "assistant", "ok", payload)
    msgs = store.list_messages(cid, "alice")
    saved = msgs[0]["payload"] or {}
    raw = saved.get("raw_result", {})
    # data truncated to 50 rows
    assert isinstance(raw.get("data"), list)
    assert len(raw["data"]) <= 50
    # tool_calls detail capped
    tc = saved.get("tool_calls") or []
    assert all(len((c.get("detail") or "")) <= 500 for c in tc if isinstance(c, dict))


def test_search_finds_match(store) -> None:
    cid_a = store.create_conversation("alice", "GMV tháng 5")
    cid_b = store.create_conversation("alice", "doanh thu")
    store.append_message(cid_b, "alice", "user", "hỏi về GMV tăng trưởng", None)
    res = store.search_conversations("alice", "GMV")
    ids = {r["id"] for r in res}
    assert cid_a in ids
    assert cid_b in ids


def test_export_returns_bundle(store) -> None:
    cid = store.create_conversation("alice", "export-me")
    store.append_message(cid, "alice", "user", "hi", None)
    bundle = store.export_conversation("alice", cid)
    assert bundle is not None
    assert bundle["conversation"]["id"] == cid
    assert len(bundle["messages"]) == 1
    # bob cannot export alice's
    assert store.export_conversation("bob", cid) is None
