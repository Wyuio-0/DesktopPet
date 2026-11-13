"""Rhodes Sync v2: AES-256-GCM envelopes with request/response binding.

The 32-byte pairing secret is transferred out of band, never over discovery or HTTP.
See docs/sync-v2.md for the language-independent wire format.
"""
import base64
import hashlib
import json
import secrets
import threading
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PROTOCOL = 2
MAX_PLAIN = 4 * 1024 * 1024
MAX_WIRE = (MAX_PLAIN + 16) * 4 // 3 + 2048
PATHS = frozenset(("/api/pair/request", "/api/sync/pull", "/api/sync/push",
                   "/api/clipboard", "/api/status", "/api/pair/unpair"))


class InvalidEnvelope(ValueError):
    pass


def b64(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def unb64(value, length=None):
    if not isinstance(value, str) or len(value) > MAX_WIRE:
        raise InvalidEnvelope("无效的加密消息")
    try:
        data = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, UnicodeError):
        raise InvalidEnvelope("无效的加密消息") from None
    if b64(data) != value or (length is not None and len(data) != length):
        raise InvalidEnvelope("无效的加密消息")
    return data


def new_secret():
    return b64(secrets.token_bytes(32))


def key_id(secret):
    return b64(hashlib.sha256(unb64(secret, 32)).digest())


def pairing_code(secret):
    return f"{int.from_bytes(hashlib.sha256(unb64(secret, 32)).digest()[:4], 'big') % 1000000:06d}"


def _aad(path, envelope, direction):
    if path not in PATHS or not isinstance(envelope, dict):
        raise InvalidEnvelope("无效的加密消息")
    if (type(envelope.get("v")) is not int or envelope["v"] != 2
            or type(envelope.get("ts")) is not int
            or type(envelope.get("s")) is not int):
        raise InvalidEnvelope("无效的加密消息")
    for field, size in (("kid", 32), ("epoch", 32), ("id", 16)):
        unb64(envelope.get(field), size)
    return (f"RhodesSync/2|{direction}|POST|{path}|{envelope['kid']}|"
            f"{envelope['epoch']}|{envelope['id']}|{envelope['ts']}|{envelope['s']}").encode()


def seal(secret, path, payload, context, direction, status):
    envelope = {k: context[k] for k in ("epoch", "id", "ts")}
    envelope.update(v=2, kid=key_id(secret), s=status)
    plain = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    if len(plain) > MAX_PLAIN:
        raise InvalidEnvelope("同步消息过大")
    nonce = secrets.token_bytes(12)
    envelope["nonce"] = b64(nonce)
    envelope["ct"] = b64(AESGCM(unb64(secret, 32)).encrypt(nonce, plain, _aad(path, envelope, direction)))
    return envelope


def open_envelope(secret, path, envelope, direction):
    aad = _aad(path, envelope, direction)
    if envelope["kid"] != key_id(secret):
        raise InvalidEnvelope("加密认证失败")
    try:
        ciphertext = unb64(envelope.get("ct"))
        if not 16 <= len(ciphertext) <= MAX_PLAIN + 16:
            raise InvalidEnvelope("同步消息过大")
        plain = AESGCM(unb64(secret, 32)).decrypt(unb64(envelope.get("nonce"), 12), ciphertext, aad)
        payload = json.loads(plain.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError()
        return payload
    except Exception:
        raise InvalidEnvelope("加密认证失败") from None


def make_request(secret, path, payload, epoch):
    context = {"epoch": epoch, "id": b64(secrets.token_bytes(16)), "ts": int(time.time())}
    return seal(secret, path, payload, context, "request", 0)


def read_response(secret, path, envelope, request, status):
    if (not isinstance(envelope, dict) or envelope.get("s") != status
            or any(envelope.get(k) != request[k] for k in ("epoch", "id", "ts"))):
        raise InvalidEnvelope("响应与请求不匹配")
    return open_envelope(secret, path, envelope, "response")


class SecureSync:
    def __init__(self):
        self.epoch = new_secret()
        self.invite = None
        self.claimed = None
        self.seen = {}
        self.lock = threading.RLock()

    def create_invite(self):
        with self.lock:
            secret = new_secret()
            self.invite = (secret, time.monotonic() + 300)
            self.claimed = None
            return secret

    def invite_secret(self, kid):
        with self.lock:
            if self.invite and self.invite[1] > time.monotonic() and key_id(self.invite[0]) == kid:
                return self.invite[0]
            return None

    def consume_invite(self, secret):
        with self.lock:
            if self.invite and self.invite[0] == secret:
                self.invite = None
                self.claimed = None

    def claim_invite(self, secret, identity):
        with self.lock:
            if self.invite_secret(key_id(secret)) != secret or self.claimed is not None:
                return False
            self.claimed = (secret, identity)
            return True

    def release_invite(self, secret, identity):
        with self.lock:
            if self.claimed == (secret, identity):
                self.claimed = None

    def accept(self, secret, path, envelope):
        payload = open_envelope(secret, path, envelope, "request")
        if (envelope["epoch"] != self.epoch or envelope["s"] != 0
                or abs(time.time() - envelope["ts"]) > 120):
            raise InvalidEnvelope("加密消息已过期")
        with self.lock:
            now = time.monotonic()
            self.seen = {k: expiry for k, expiry in self.seen.items() if expiry > now}
            identity = (envelope["kid"], envelope["id"])
            if identity in self.seen or len(self.seen) >= 4096:
                raise InvalidEnvelope("拒绝重复或过量请求")
            self.seen[identity] = now + 241
        return payload
