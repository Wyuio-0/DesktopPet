"""Native LAN service request framing, pairing lifetimes and credential scope."""

import http.client
import http.server
import io
import json
import socket
import threading
import urllib.error
import urllib.request

import pytest

from pet import sync_service as sync
from pet import sync_crypto as crypto


@pytest.fixture
def manager(tmp_path):
    return sync.PairManager(str(tmp_path / "paired.json"))


def pending(manager, ip="127.0.0.1", client="phone"):
    return manager.create_pending_request(client, "手机", ip, 23334, "123456")


def test_pair_expiry_cleanup_and_no_late_accept(manager):
    req = pending(manager)
    req.created_at -= sync.PAIR_TTL + 1
    assert manager.accept_request(req.request_id) is None
    assert req.event.is_set()
    assert not manager.pending_requests
    assert not manager.paired_devices


def test_pair_acceptance_idempotent_and_credentials_scoped(manager):
    req = pending(manager)
    token = manager.accept_request(req.request_id)
    assert manager.accept_request(req.request_id) == token
    assert manager.is_device_trusted("phone", token)
    assert not manager.is_device_trusted("other-device", token)
    assert not manager.is_device_trusted("", None)
    manager.complete_request(req.request_id)
    assert not manager.pending_requests


def test_pair_queue_and_attempts_are_bounded(manager):
    first = pending(manager)
    with pytest.raises(OverflowError):
        pending(manager)
    manager.reject_request(first.request_id)
    for _ in range(4):
        req = pending(manager)
        manager.reject_request(req.request_id)
    with pytest.raises(OverflowError):
        pending(manager)
    for i in range(sync.MAX_PENDING_PAIRS):
        pending(manager, ip=f"10.0.0.{i}", client=f"phone-{i}")
    with pytest.raises(OverflowError):
        pending(manager, ip="10.0.0.99")
    requests = list(manager.pending_requests.values())
    manager.clear_pending_requests()
    assert not manager.pending_requests
    assert all(req.event.is_set() for req in requests)


@pytest.mark.parametrize("field,value", [("client_id", []), ("client_name", "x" * 129),
                                        ("client_port", -1), ("pin", "123"), ("pin", 123456)])
def test_bad_pair_metadata(manager, field, value):
    args = dict(client_id="phone", client_name="手机", client_ip="127.0.0.1", client_port=23334, pin="123456")
    args[field] = value
    with pytest.raises(ValueError):
        manager.create_pending_request(**args)
    assert not manager.pending_requests


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    service = sync.RhodesSyncService(device_name="security-test", http_port=0, udp_port=0)
    req = pending(service.pair_manager)
    service.secret = crypto.new_secret()
    req.sync_key = service.secret
    service.token = service.pair_manager.accept_request(req.request_id)
    service.pair_manager.complete_request(req.request_id)
    service.start()
    try:
        yield service
    finally:
        service.stop()


def call(service, method="GET", path="/api/info", body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", service.http_port, timeout=3)
    try:
        merged = {"X-Rhodes-Protocol": "2"} if method == "POST" else {}
        merged.update(headers or {})
        conn.request(method, path, body=body, headers=merged)
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


@pytest.mark.parametrize("method,headers", [("GET", {"Origin": "https://evil.example"}),
                                          ("GET", {"Sec-Fetch-Site": "same-site"}), ("OPTIONS", {})])
def test_browser_requests_rejected(service, method, headers):
    status, response_headers, _ = call(service, method, headers=headers)
    assert status == 403
    assert "Access-Control-Allow-Origin" not in response_headers


@pytest.mark.parametrize("length,status", [("-1", 400), ("bad", 400), ("9" * 5000, 413),
                                         (str((sync.MAX_PAIR_BYTES + 16) * 4 // 3 + 2049), 413)])
def test_lengths_rejected_without_reading_body(service, length, status):
    assert call(service, "POST", "/api/pair/request", headers={"Content-Length": length})[0] == status


def test_chunked_and_duplicate_length_rejected(service):
    assert call(service, "POST", "/api/pair/request", headers={"Transfer-Encoding": "chunked"})[0] == 400
    conn = http.client.HTTPConnection("127.0.0.1", service.http_port, timeout=3)
    try:
        conn.putrequest("POST", "/api/pair/request")
        conn.putheader("X-Rhodes-Protocol", "2")
        conn.putheader("Content-Length", "0")
        conn.putheader("Content-Length", "1")
        conn.endheaders()
        assert conn.getresponse().status == 400
    finally:
        conn.close()


@pytest.mark.parametrize("body", [b"{bad", b"[]", b"null", b"\xff"])
def test_json_must_be_complete_utf8_object(service, body):
    assert call(service, "POST", "/api/pair/request", body=body,
                headers={"Content-Type": "application/json"})[0] == 400


def test_truncated_body_rejected(service):
    conn = http.client.HTTPConnection("127.0.0.1", service.http_port, timeout=3)
    try:
        conn.putrequest("POST", "/api/pair/request")
        conn.putheader("X-Rhodes-Protocol", "2")
        conn.putheader("Content-Length", "20")
        conn.putheader("Content-Type", "application/json")
        conn.endheaders()
        conn.send(b"{")
        conn.sock.shutdown(socket.SHUT_WR)
        assert conn.getresponse().status == 400
    finally:
        conn.close()


def test_native_chinese_pairing_clears_request(service):
    service.on_pair_request_callback = lambda req: service.pair_manager.accept_request(req.request_id)
    secret = service.create_pairing_invite()
    payload = {"client_id": "second", "client_name": "中文设备", "client_port": 23334, "pin": "123456"}
    envelope = crypto.make_request(secret, "/api/pair/request", payload, service.secure.epoch)
    status, headers, data = call(service, "POST", "/api/pair/request", body=json.dumps(envelope).encode(), headers={"Content-Type": "application/json"})
    assert status == 200
    result = crypto.read_response(secret, "/api/pair/request", json.loads(data), envelope, status)
    assert result["auth_token"]
    assert result["auth_token"].encode() not in data
    assert not service.pair_manager.pending_requests
    assert headers["Cache-Control"] == "no-store"


def secure_call(service, path, payload):
    payload = dict(payload, _auth_token=service.token)
    envelope = crypto.make_request(service.secret, path, payload, service.secure.epoch)
    status, headers, data = call(service, "POST", path, body=json.dumps(envelope).encode(), headers={"Content-Type": "application/json"})
    return status, crypto.read_response(service.secret, path, json.loads(data), envelope, status)


def test_polling_cannot_retrieve_other_peers_pair_token(service):
    req = pending(service.pair_manager, ip="10.0.0.20", client="remote")
    service.pair_manager.accept_request(req.request_id)
    status, _, body = call(service, path="/api/pair/status?request_id=" + req.request_id)
    assert status == 426
    assert req.auth_token.encode() not in body


def test_legacy_pull_is_blocked_and_encrypted_pull_works(service):
    status, _, body = call(service, "POST", "/api/sync/pull", headers={"Authorization": "Bearer " + service.token})
    assert status == 426
    assert b"schedule" not in body
    status, result = secure_call(service, "/api/sync/pull", {})
    assert status == 200
    assert "schedule" in result


def test_unknown_key_rejected_and_cannot_unpair_other_devices(service):
    assert call(service, "POST", "/api/sync/push", body=b"{}", headers={"Content-Type": "application/json"})[0] == 401
    assert secure_call(service, "/api/pair/unpair", {"device_id": "other"})[0] == 403
    assert secure_call(service, "/api/pair/unpair", {"device_id": "phone"})[0] == 200
    assert not service.pair_manager.is_device_trusted("phone", service.token)


def test_server_instances_do_not_share_identity_or_auth(service, tmp_path):
    other = sync.RhodesSyncService(device_name="other", http_port=0, udp_port=0)
    other.pair_manager = sync.PairManager(str(tmp_path / "other.json"))
    other.start()
    try:
        assert json.loads(call(service)[2])["device_name"] == "security-test"
        assert json.loads(call(other)[2])["device_name"] == "other"
        assert call(other, path="/api/sync/pull", headers={"Authorization": "Bearer " + service.token})[0] == 426
    finally:
        other.stop()


def test_worker_limit_returns_busy_and_recovers(service):
    slots = service.http_server._slots
    for _ in range(16):
        assert slots.acquire(blocking=False)
    try:
        assert call(service)[0] == 503
    finally:
        for _ in range(16):
            slots.release()
    assert call(service)[0] == 200


def test_outgoing_requests_do_not_follow_redirects():
    class Redirect(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:1/credential-leak")
            self.end_headers()
    server = http.server.HTTPServer(("127.0.0.1", 0), Redirect)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/", headers={"Authorization": "Bearer " + sync.secrets.token_urlsafe(32)})
        with pytest.raises(urllib.error.HTTPError) as exc:
            sync._open_sync_request(req, timeout=2)
        assert exc.value.code == 302
    finally:
        server.shutdown()
        server.server_close()


def test_oversized_response_rejected_before_parsing():
    with pytest.raises(ValueError):
        sync._read_sync_json(io.BytesIO(b" " * (crypto.MAX_WIRE + 1)))
