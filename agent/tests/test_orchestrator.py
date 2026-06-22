from app import config as app_config
from app import orchestrator


def test_langfuse_callbacks_disabled(monkeypatch):
    monkeypatch.setattr(app_config.Settings, "langfuse_enabled", False)
    assert orchestrator._build_langfuse_callbacks() == []


def test_langfuse_callbacks_missing_keys(monkeypatch):
    monkeypatch.setattr(app_config.Settings, "langfuse_enabled", True)
    monkeypatch.setattr(app_config.Settings, "langfuse_public_key", "")
    monkeypatch.setattr(app_config.Settings, "langfuse_secret_key", "")
    assert orchestrator._build_langfuse_callbacks() == []
