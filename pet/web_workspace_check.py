"""Isolated acceptance check run inside the actual packaged executable."""

import json
import socket
import traceback
from http.cookiejar import CookieJar
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener


def run(report_path):
    from . import web_launcher
    from .updater import APP_VERSION

    report = {"version": APP_VERSION, "success": False}
    port = None
    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        with patch.object(web_launcher.webbrowser, "open", return_value=True) as browser:
            url = web_launcher.open_notebook_lm(port=port)
            browser.assert_called_once_with(url)
        report["browser_dispatch"] = True
        opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))
        base = f"http://127.0.0.1:{port}"
        with opener.open(base + "/auth", timeout=10) as response:
            assert response.status == 200
            assert b"/auth/session" in response.read()
        try:
            opener.open(base + "/", timeout=10)
            raise AssertionError("Unauthenticated workspace access was allowed")
        except HTTPError as error:
            assert error.code == 401, error.code
        token = parse_qs(urlsplit(url).fragment)["token"][0]
        request = Request(
            base + "/auth/session",
            data=json.dumps({"token": token}).encode(),
            headers={"Origin": base, "Content-Type": "application/json"},
        )
        with opener.open(request, timeout=10) as response:
            assert response.status == 200
        with opener.open(base + "/", timeout=10) as response:
            html = response.read().decode("utf-8")
            assert response.status == 200
            assert "<!doctype html" in html.lower()
            assert "课程" in html
        with opener.open(base + "/api/stats", timeout=10) as response:
            assert isinstance(json.load(response)["courses"], list)
        report.update(success=True, authenticated_html=True, stats_api=True,
                      unauthenticated_rejected=True)
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        if port is not None:
            web_launcher.stop_server(port=port)
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["success"] else 1
