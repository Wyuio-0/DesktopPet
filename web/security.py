"""Loopback-only browser sessions for the local courseware workspace."""

import ipaddress
import secrets
import time
import threading
from urllib.parse import urlencode, urlsplit

from aiohttp import web


def local_host(host):
    if host == "localhost":
        return "127.0.0.1"
    if host not in ("127.0.0.1", "::1"):
        raise ValueError("网页工作台仅支持本机访问，请使用 127.0.0.1、localhost 或 ::1")
    return host


def base_url(host, port):
    host = local_host(host)
    return f"http://{'[' + host + ']' if ':' in host else host}:{port}"


class LocalWebAccess:
    def __init__(self):
        self._lock = threading.RLock()
        self.launch_tokens = {}
        self.sessions = {}

    @staticmethod
    def _prune(items, now):
        for key, expiry in list(items.items()):
            if expiry <= now:
                del items[key]

    def launch_url(self, host, port, params=None):
        with self._lock:
            now = time.monotonic()
            self._prune(self.launch_tokens, now)
            while len(self.launch_tokens) >= 32:
                del self.launch_tokens[next(iter(self.launch_tokens))]
            token = secrets.token_urlsafe(32)
            self.launch_tokens[token] = now + 300
            query = "?" + urlencode(params) if params else ""
            return base_url(host, port) + "/auth" + query + "#token=" + token

    def consume(self, token):
        with self._lock:
            if not isinstance(token, str):
                return None
            now = time.monotonic()
            self._prune(self.launch_tokens, now)
            if self.launch_tokens.pop(token, 0) <= now:
                return None
            self._prune(self.sessions, now)
            while len(self.sessions) >= 64:
                del self.sessions[next(iter(self.sessions))]
            session = secrets.token_urlsafe(32)
            self.sessions[session] = now + 12 * 3600
            return session

    def valid_session(self, token):
        with self._lock:
            now = time.monotonic()
            self._prune(self.sessions, now)
            return isinstance(token, str) and self.sessions.get(token, 0) > now


ACCESS_KEY = web.AppKey("local_web_access", LocalWebAccess)


def _authority(value):
    if any(char.isspace() for char in value):
        return None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "http" or parsed.username is not None
                or parsed.password is not None or parsed.path != ""
                or parsed.query or parsed.fragment):
            return None
        return parsed.hostname, parsed.port or 80
    except ValueError:
        return None


def cookie_name(request):
    return "amiya_session_" + str(request.transport.get_extra_info("sockname")[1])


@web.middleware
async def local_session(request, handler):
    authority = _authority("http://" + request.headers.get("Host", ""))
    sockname = request.transport.get_extra_info("sockname")
    peer = request.transport.get_extra_info("peername")
    if (len(request.headers.getall("Host", [])) != 1
            or not authority or authority[0] not in ("127.0.0.1", "localhost", "::1")
            or not sockname or authority[1] != sockname[1]
            or not peer or not ipaddress.ip_address(peer[0]).is_loopback):
        raise web.HTTPForbidden(text="仅允许通过本机地址访问工作台")
    origin = request.headers.get("Origin")
    if (len(request.headers.getall("Origin", [])) > 1
            or (origin is not None and _authority(origin) != authority)
            or request.headers.get("Sec-Fetch-Site", "none") not in ("none", "same-origin")
            or (request.method not in ("GET", "HEAD") and origin is None)):
        raise web.HTTPForbidden(text="拒绝跨站或来源不明的请求")

    public = (request.method in ("GET", "HEAD") and request.path == "/auth"
              or request.method == "POST" and request.path == "/auth/session")
    if not public and not request.app[ACCESS_KEY].valid_session(request.cookies.get(cookie_name(request))):
        raise web.HTTPUnauthorized(text="会话未建立或已过期，请从桌宠菜单重新打开工作台")
    response = await handler(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


async def bootstrap(request):
    nonce = secrets.token_urlsafe(16)
    html = """<!doctype html><html lang="zh"><meta charset="utf-8">
<title>正在打开课件工作台</title><p id="status">正在建立本机会话…</p>
<script nonce="NONCE">
(async () => {
  const token = new URLSearchParams(location.hash.slice(1)).get('token');
  const query = location.search;
  history.replaceState(null, '', '/auth' + query);
  try {
    const response = await fetch('/auth/session', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({token})
    });
    if (!response.ok) throw new Error('expired');
    location.replace('/' + query);
  } catch (_) {
    document.getElementById('status').textContent = '链接已失效，请从桌宠菜单重新打开工作台。';
  }
})();
</script></html>""".replace("NONCE", nonce)
    response = web.Response(text=html, content_type="text/html")
    response.headers["Content-Security-Policy"] = (
        f"default-src 'none'; script-src 'nonce-{nonce}'; connect-src 'self'; frame-ancestors 'none'")
    return response


async def establish_session(request):
    if request.content_type != "application/json":
        raise web.HTTPBadRequest(text="需要 JSON 请求")
    if request.content_length is None or request.content_length > 1024:
        raise web.HTTPBadRequest(text="无效的认证请求大小")
    try:
        data = await request.json()
    except ValueError:
        raise web.HTTPBadRequest(text="无效的认证请求")
    token = data.get("token") if isinstance(data, dict) else None
    access = request.app[ACCESS_KEY]
    session = access.consume(token)
    # An already authenticated browser can reload /auth after its token was consumed.
    if session is None and not access.valid_session(request.cookies.get(cookie_name(request))):
        raise web.HTTPUnauthorized(text="打开链接已失效，请从桌宠菜单重新打开")
    response = web.json_response({"success": True})
    if session:
        response.set_cookie(cookie_name(request), session, httponly=True,
                            samesite="Strict", path="/", max_age=12 * 3600)
    return response
