"""Regression coverage for installed workspace overrides and browser handoff."""

import importlib
import sys
from types import SimpleNamespace

import pytest

from pet import web_launcher


@pytest.fixture(autouse=True)
def isolate_workspace_logs(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(web_launcher.petlog, "log", lambda message: None)
    monkeypatch.setattr(web_launcher.petlog, "warn", lambda message: None)
    monkeypatch.setattr(web_launcher.petlog, "error", lambda message: None)


@pytest.mark.parametrize("relative_path", ["web/server.py", "_internal/web/server.py"])
def test_frozen_launcher_ignores_stale_server_beside_executable(
        tmp_path, monkeypatch, relative_path):
    """An upgrade may leave a pre-authentication server.py beside the new exe."""
    install_dir = tmp_path / "installed-pet"
    stale_source = install_dir / relative_path
    stale_source.parent.mkdir(parents=True)
    stale_source.write_text(
        "def make_app():\n    return 'legacy unauthenticated app'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(install_dir / "DesktopPet.exe"))
    canonical_server = SimpleNamespace(ACCESS_KEY=object())
    imports = []

    def import_canonical(name):
        imports.append(name)
        return canonical_server

    monkeypatch.setattr(importlib, "import_module", import_canonical)

    assert web_launcher._get_web_server_module() is canonical_server
    assert imports == ["web.server"]


def test_invalid_app_access_key_is_rejected_before_runner_setup(monkeypatch):
    """A broken app must never briefly expose an unusable HTTP listener."""
    from aiohttp import web

    runner_attempts = []

    def unexpected_runner(*args, **kwargs):
        runner_attempts.append(True)
        raise AssertionError("AppRunner created before access validation")

    monkeypatch.setattr(web_launcher, "is_server_listening", lambda *args, **kwargs: False)
    for attribute in (
        "_SITE", "_SERVER_THREAD", "_LOOP", "_RUNNER", "_ACCESS",
        "_WEB_SERVER", "_SERVER_ADDRESS", "_SERVER_ERROR",
    ):
        monkeypatch.setattr(web_launcher, attribute, None)
    monkeypatch.setattr(web_launcher, "_SERVER_STARTED", False)
    monkeypatch.setattr(
        web_launcher, "_get_web_server_module",
        lambda: SimpleNamespace(ACCESS_KEY=object(), make_app=lambda: {}),
    )
    monkeypatch.setattr(web, "AppRunner", unexpected_runner)

    assert not web_launcher.ensure_server_running(port=5059)
    assert runner_attempts == []


@pytest.fixture
def ready_workspace(monkeypatch):
    launch_url = "http://127.0.0.1:5050/auth#token=test-only-token"
    monkeypatch.setattr(web_launcher, "ensure_server_running", lambda *args, **kwargs: True)
    monkeypatch.setattr(web_launcher, "_SERVER_ADDRESS", ("127.0.0.1", 5050))
    monkeypatch.setattr(
        web_launcher, "_ACCESS",
        SimpleNamespace(launch_url=lambda *args, **kwargs: launch_url),
    )
    return launch_url


def test_browser_rejection_is_reported_as_failure(ready_workspace, monkeypatch):
    """Windows may reject the browser handoff without raising an exception."""
    monkeypatch.setattr(web_launcher.webbrowser, "open", lambda *args, **kwargs: False)

    with pytest.raises(RuntimeError, match="浏览器"):
        web_launcher.open_notebook_lm()


def test_browser_exception_is_reported_as_failure(ready_workspace, monkeypatch):
    def fail_to_open(*args, **kwargs):
        raise OSError("No registered HTTP handler")

    monkeypatch.setattr(web_launcher.webbrowser, "open", fail_to_open)

    with pytest.raises(RuntimeError, match="浏览器"):
        web_launcher.open_notebook_lm()


def test_successful_browser_handoff_uses_authenticated_url(ready_workspace, monkeypatch):
    opened = []

    def open_browser(url, *args, **kwargs):
        opened.append(url)
        return True

    monkeypatch.setattr(web_launcher.webbrowser, "open", open_browser)

    assert web_launcher.open_notebook_lm() == ready_workspace
    assert opened == [ready_workspace]
