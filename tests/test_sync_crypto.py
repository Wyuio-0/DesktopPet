"""AEAD envelope and encrypted PC-to-PC regression tests."""
import json
import time
from pathlib import Path

import pytest

from pet import sync_crypto as crypto
from pet import sync_service as sync


def test_envelope_vectors():
    rows = (Path(__file__).parent / "fixtures/sync_v2_vectors.tsv").read_text(encoding="utf-8").splitlines()[1:]
    for line in rows:
        secret, path, direction, epoch, identity, stamp, status, nonce, ciphertext, plain = line.split("\t")
        envelope = dict(v=2, kid=crypto.key_id(secret), epoch=epoch, id=identity, ts=int(stamp), s=int(status), nonce=nonce, ct=ciphertext)
        assert crypto.open_envelope(secret, path, envelope, direction) == json.loads(crypto.unb64(plain))


def test_tampering_reflection_expiry_and_response_binding():
    secret = crypto.new_secret()
    server = crypto.SecureSync()
    path = "/api/clipboard"
    request = crypto.make_request(secret, path, {"text": "中文私密内容"}, server.epoch)
    assert server.accept(secret, path, request)["text"] == "中文私密内容"
    with pytest.raises(crypto.InvalidEnvelope): server.accept(secret, path, request)
    with pytest.raises(crypto.InvalidEnvelope): crypto.SecureSync().accept(secret, path, request)
    with pytest.raises(crypto.InvalidEnvelope): crypto.open_envelope(secret, "/api/status", request, "request")
    with pytest.raises(crypto.InvalidEnvelope): crypto.open_envelope(secret, path, request, "response")
    with pytest.raises(crypto.InvalidEnvelope): crypto.open_envelope(crypto.new_secret(), path, request, "request")
    for field, value in (("ts", request["ts"] + 1), ("s", 200), ("kid", crypto.new_secret()),
                         ("nonce", crypto.b64(bytes(12))), ("id", crypto.b64(bytes(16)))):
        with pytest.raises(crypto.InvalidEnvelope):
            crypto.open_envelope(secret, path, dict(request, **{field: value}), "request")
    ciphertext = bytearray(crypto.unb64(request["ct"])); ciphertext[-1] ^= 1
    with pytest.raises(crypto.InvalidEnvelope): crypto.open_envelope(secret, path, dict(request, ct=crypto.b64(ciphertext)), "request")
    stale = dict(request, ts=int(time.time()) - 121)
    stale = crypto.seal(secret, path, {}, stale, "request", 0)
    with pytest.raises(crypto.InvalidEnvelope): server.accept(secret, path, stale)
    response = crypto.seal(secret, path, {"status": "ok"}, request, "response", 200)
    assert crypto.read_response(secret, path, response, request, 200)["status"] == "ok"
    with pytest.raises(crypto.InvalidEnvelope): crypto.read_response(secret, path, response, request, 403)
    another = crypto.make_request(secret, path, {}, server.epoch)
    with pytest.raises(crypto.InvalidEnvelope): crypto.read_response(secret, path, response, another, 200)


def test_invitation_and_replay_capacity_are_bounded():
    server = crypto.SecureSync()
    secret = server.create_invite()
    assert server.invite_secret(crypto.key_id(secret)) == secret
    assert server.claim_invite(secret, "first")
    assert not server.claim_invite(secret, "second")
    server.release_invite(secret, "second")
    assert not server.claim_invite(secret, "second")
    server.release_invite(secret, "first")
    assert server.claim_invite(secret, "second")
    server.consume_invite(secret)
    assert server.invite_secret(crypto.key_id(secret)) is None
    expired = server.create_invite(); server.invite = (expired, time.monotonic() - 1)
    assert server.invite_secret(crypto.key_id(expired)) is None
    server.seen = {str(i): time.monotonic() + 240 for i in range(4096)}
    envelope = crypto.make_request(secret, "/api/status", {}, server.epoch)
    with pytest.raises(crypto.InvalidEnvelope): server.accept(secret, "/api/status", envelope)


@pytest.fixture
def pair(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    client = sync.RhodesSyncService("Client", http_port=0, udp_port=0)
    receiver = sync.RhodesSyncService("Receiver", http_port=0, udp_port=0)
    client.device_id, receiver.device_id = "client", "receiver"
    client.pair_manager = sync.PairManager(str(tmp_path / "client.json"))
    receiver.pair_manager = sync.PairManager(str(tmp_path / "receiver.json"))
    client.start(); receiver.start()
    receiver.on_pair_request_callback = lambda request: receiver.pair_manager.accept_request(request.request_id)
    try:
        yield client, receiver
    finally:
        client.stop(); receiver.stop()


def test_real_encrypted_pair_and_bidirectional_clipboard(pair, monkeypatch):
    client, receiver = pair
    captures = []
    original = sync._open_sync_request
    def observe(request, timeout):
        if request.data: captures.append((request.data, str(request.headers)))
        return original(request, timeout)
    monkeypatch.setattr(sync, "_open_sync_request", observe)
    secret = receiver.create_pairing_invite()
    ok, _, result = client.request_pair("127.0.0.1", receiver.http_port, pairing_secret=secret)
    assert ok
    token = result["auth_token"]
    received = []
    receiver.on_clipboard_callback = lambda text, title: received.append(text)
    assert client.send_clipboard("127.0.0.1", receiver.http_port, token, "中文私密资料")
    assert received == ["中文私密资料"]
    reverse = []
    client.on_clipboard_callback = lambda text, title: reverse.append(text)
    assert receiver.send_clipboard("127.0.0.1", client.http_port, token, "反向加密快传")
    assert reverse == ["反向加密快传"]
    for body, headers in captures:
        assert secret.encode() not in body and token.encode() not in body
        assert "中文私密资料".encode() not in body and "反向加密快传".encode() not in body
        assert token not in headers and "Bearer" not in headers
    assert receiver.secure.invite_secret(crypto.key_id(secret)) is None


def test_old_pair_and_wrong_secret_fail_closed(pair):
    client, receiver = pair
    secret = receiver.create_pairing_invite()
    assert not client.request_pair("127.0.0.1", receiver.http_port, pairing_secret=crypto.new_secret())[0]
    assert not client.send_clipboard("127.0.0.1", receiver.http_port, "legacy-token", "no")
    assert receiver.secure.invite_secret(crypto.key_id(secret)) == secret


def test_network_replay_has_no_duplicate_side_effect(pair):
    import urllib.error
    import urllib.request
    client, receiver = pair
    secret = receiver.create_pairing_invite()
    ok, _, result = client.request_pair("127.0.0.1", receiver.http_port, pairing_secret=secret)
    assert ok
    received = []
    receiver.on_clipboard_callback = lambda text, title: received.append(text)
    envelope = crypto.make_request(secret, "/api/clipboard", {"text": "once", "_auth_token": result["auth_token"]}, receiver.secure.epoch)
    def send():
        request = urllib.request.Request(f"http://127.0.0.1:{receiver.http_port}/api/clipboard", data=json.dumps(envelope).encode(),
            headers={"Content-Type": "application/json", "X-Rhodes-Protocol": "2"})
        return sync._open_sync_request(request, timeout=2)
    with send() as response: assert response.status == 200
    with pytest.raises(urllib.error.HTTPError) as exc: send()
    assert exc.value.code == 401 and received == ["once"]
