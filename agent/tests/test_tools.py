import pytest

import app.tools as tools


def test_list_workspace_rejects_non_existent(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "WORKSPACE", tmp_path.resolve())
    assert "does not exist" in tools.list_workspace("missing")


def test_workspace_traversal_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "WORKSPACE", tmp_path.resolve())
    with pytest.raises(ValueError):
        tools._ensure_workspace_path("../etc/passwd")
