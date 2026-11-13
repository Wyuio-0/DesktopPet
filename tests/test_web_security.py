"""Exercise authentication together with host and browser-origin enforcement."""

import asyncio
import socket
from types import SimpleNamespace
from urllib.parse import urlsplit, parse_qs

import pytest
from aiohttp import CookieJar
from aiohttp.test_utils import TestClient, TestServer

from web.security import ACCESS_KEY, LocalWebAccess, base_url, local_host


@pytest.fixture
def server_module(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    from web import server
    from pet.knowledge import KnowledgeBase
    monkeypatch.setattr(server, "kb", KnowledgeBase(str(tmp_path / "knowledge"), use_embed=False))
    return server


async def login(client, app):
    origin = str(client.make_url("/")).rstrip("/")
    url = app[ACCESS_KEY].launch_url("127.0.0.1", client.port)
    token = parse_qs(urlsplit(url).fragment)["token"][0]
    response = await client.post("/auth/session", json={"token": token}, headers={"Origin": origin})
    assert response.status == 200
    return origin, token, response


@pytest.mark.parametrize("path", ["/", "/api/stats", "/api/files", "/api/files/raw?filename=secret.md", "/static/index.html"])
def test_read_endpoints_require_session(server_module, path):
    async def run():
        async with TestClient(TestServer(server_module.make_app())) as client:
            assert (await client.get(path)).status == 401
    asyncio.run(run())


def test_browser_login_cookie_and_api_access(server_module):
    async def run():
        app = server_module.make_app()
        async with TestClient(TestServer(app), cookie_jar=CookieJar(unsafe=True)) as client:
            response = await client.get("/auth")
            html = await response.text()
            assert response.status == 200
            assert "history.replaceState" in html
            assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
            origin, token, response = await login(client, app)
            cookie = next(iter(response.cookies.values()))
            assert cookie["httponly"]
            assert cookie["samesite"] == "Strict"
            assert cookie["max-age"] == "43200"
            assert cookie.value != token
            assert token not in str(response.headers)
            assert (await client.get("/api/stats")).status == 200
            assert (await client.get("/")).status == 200
            response = await client.post("/api/courses/create", json={"name": "数学"}, headers={"Origin": origin})
            assert response.status == 200
            assert response.headers["Cache-Control"] == "no-store"
            assert response.headers["Referrer-Policy"] == "no-referrer"
            assert (await client.post("/api/courses/delete", json={"name": "数学"}, headers={"Origin": origin})).status == 200
            client.session.cookie_jar.clear()
            # A launch token is one-use and never works as a query-string API credential.
            assert (await client.post("/auth/session", json={"token": token}, headers={"Origin": origin})).status == 401
            assert (await client.get("/api/stats", params={"token": token})).status == 401
    asyncio.run(run())


@pytest.mark.parametrize("headers", [
    {"Origin": "https://evil.example"}, {"Origin": "null"},
    {"Origin": "http://127.0.0.1:1"}, {"Origin": "http://localhost:1"},
    {"Origin": "http://user@127.0.0.1:1"},
    {"Sec-Fetch-Site": "cross-site"}, {"Sec-Fetch-Site": "same-site"},
    {"Host": "evil.example"}, {"Host": "127.0.0.1:1"},
    {"Host": "127.0.0.1:bad"}, {"Host": "127.0.0.1:80/path"},
])
def test_cross_origin_and_bad_hosts_rejected_even_with_cookie(server_module, headers):
    async def run():
        app = server_module.make_app()
        async with TestClient(TestServer(app), cookie_jar=CookieJar(unsafe=True)) as client:
            await login(client, app)
            assert (await client.get("/api/stats", headers=headers)).status == 403
    asyncio.run(run())


def test_posts_require_origin_and_session(server_module):
    async def run():
        app = server_module.make_app()
        async with TestClient(TestServer(app), cookie_jar=CookieJar(unsafe=True)) as client:
            origin = str(client.make_url("/")).rstrip("/")
            assert (await client.post("/api/courses/delete", json={"name": "数学"}, headers={"Origin": origin})).status == 401
            await login(client, app)
            assert (await client.post("/api/courses/create", json={"name": "数学"})).status == 403
            assert not server_module.os.path.exists(server_module.kb.course_directory("数学"))
    asyncio.run(run())


@pytest.mark.parametrize("payload", [{}, {"token": "invalid"}, {"token": []}, ["invalid"]])
def test_invalid_bootstrap_tokens(server_module, payload):
    async def run():
        async with TestClient(TestServer(server_module.make_app())) as client:
            origin = str(client.make_url("/")).rstrip("/")
            assert (await client.post("/auth/session", json=payload, headers={"Origin": origin})).status == 401
    asyncio.run(run())


def test_tokens_expire_and_are_not_shared_between_servers(monkeypatch):
    from web import security
    now = [1000.0]
    monkeypatch.setattr(security, "time", SimpleNamespace(monotonic=lambda: now[0]))
    access = LocalWebAccess()
    token = access.launch_url("127.0.0.1", 5050).split("#token=")[1]
    assert len(token) >= 43
    now[0] += 301
    assert access.consume(token) is None
    token = access.launch_url("127.0.0.1", 5050).split("#token=")[1]
    session = access.consume(token)
    assert access.consume(token) is None
    assert access.valid_session(session)
    assert not LocalWebAccess().valid_session(session)
    now[0] += 12 * 3600 + 1
    assert not access.valid_session(session)
    for _ in range(100):
        access.launch_url("127.0.0.1", 5050)
    assert len(access.launch_tokens) == 32


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.20", "example.com"])
def test_do_not_bind_to_lan(server_module, monkeypatch, host):
    monkeypatch.setattr(server_module.web, "run_app", lambda *a, **kw: pytest.fail("must not bind"))
    with pytest.raises(ValueError):
        server_module.run(host=host)
    from pet import web_launcher
    with pytest.raises(ValueError):
        web_launcher.ensure_server_running(host=host)


def test_ipv6_urls():
    assert base_url("::1", 5050) == "http://[::1]:5050"
    assert local_host("localhost") == "127.0.0.1"


def test_launcher_does_not_trust_another_listener(monkeypatch):
    from pet import web_launcher
    monkeypatch.setattr(web_launcher.webbrowser, "open", lambda _: pytest.fail("must not open an unowned service"))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        port = sock.getsockname()[1]
        assert not web_launcher.ensure_server_running(port=port)
        with pytest.raises(RuntimeError):
            web_launcher.open_notebook_lm(port=port)


def test_launcher_opens_authenticated_workspace(server_module, monkeypatch):
    from pet import web_launcher
    monkeypatch.setattr(web_launcher, "_get_web_server_module", lambda: server_module)
    opened = []
    monkeypatch.setattr(web_launcher.webbrowser, "open", opened.append)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    try:
        url = web_launcher.open_notebook_lm(course="数学", filename="lecture.md", port=port, kb=server_module.kb)
        assert opened == [url]
        parsed = urlsplit(url)
        assert parsed.path == "/auth"
        assert parse_qs(parsed.query)["course"] == ["数学"]
        assert "token" not in parsed.query

        async def run():
            from aiohttp import ClientSession
            origin = f"http://127.0.0.1:{port}"
            async with ClientSession(cookie_jar=CookieJar(unsafe=True)) as client:
                response = await client.post(origin + "/auth/session", json={"token": parse_qs(parsed.fragment)["token"][0]}, headers={"Origin": origin})
                assert response.status == 200
                assert (await client.get(origin + "/api/stats")).status == 200
        asyncio.run(run())
    finally:
        assert web_launcher.stop_server(port=port)
