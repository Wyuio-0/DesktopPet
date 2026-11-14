"""罗德岛跨端协同网络服务（PC ↔ Android 双端局域网互联）。

核心功能：
1. 局域网服务监听（HTTP Server，默认端口 23333，纯标准库实现，零外部依赖）。
2. UDP 局域网设备广播与发现（默认端口 23332，带超时与容错）。
3. 蓝牙式配对握手管理（拒绝静默连接，通过 6 位战术配对码 PIN 与用户显式确认建立受信任互联）。
4. 受信任设备持久化与鉴权校验（paired_devices.json 与 Bearer Token）。
5. 学业数据双向同步引擎（课表 Schedule、考试日程 Tasks/Exams、灵感便签 NotesManager）。
6. 战术快传（跨端剪贴板与长文本投递）。
7. 双端状态感知与广播（专注伴读同步）。
"""

import http.server
import json
import os
import secrets
import hmac
import socket
import socketserver
import threading
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime

from .notes import NotesManager, Note
from .schedule import Schedule, Course
from .settings import config_dir
from .tasks import Tasks, Task
from .sync_crypto import SecureSync, InvalidEnvelope, key_id, pairing_code, make_request, read_response, seal, PATHS, MAX_WIRE

DEFAULT_HTTP_PORT = 23333
DEFAULT_UDP_PORT = 23332
from .updater import APP_VERSION

MAX_REQUEST_BYTES = 4 * 1024 * 1024
MAX_PAIR_BYTES = 4096
MAX_CLIPBOARD_BYTES = 256 * 1024
PAIR_TTL = 30.0
MAX_PENDING_PAIRS = 8
SOCKET_TIMEOUT = 5.0


class _NoSyncRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a paired-device token or a pairing body to another URL.
        return None


def _open_sync_request(req, timeout):
    limit = MAX_WIRE
    if req.data is not None and len(req.data) > limit:
        raise ValueError("同步请求过大")
    # A LAN peer must not receive credentials through system-configured proxies.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoSyncRedirects())
    return opener.open(req, timeout=timeout)


def _read_sync_json(resp):
    body = resp.read(MAX_WIRE + 1)
    if len(body) > MAX_WIRE:
        raise ValueError("同步响应过大")
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("同步响应必须是 JSON 对象")
    return payload


def _paired_devices_path():
    return os.path.join(config_dir(), "paired_devices.json")


def get_local_ips():
    """获取本机所有可用局域网 IPv4 地址。"""
    ips = []
    try:
        host_name = socket.gethostname()
        for ip in socket.gethostbyname_ex(host_name)[2]:
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                ips.append(ip)
    except Exception:
        pass
    if not ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and ip not in ips:
                ips.append(ip)
        except Exception:
            pass
    return ips or ["127.0.0.1"]


class PairRequest:
    """正在等待确认的配对请求。"""
    def __init__(self, request_id, client_id, client_name, client_ip, client_port, pin):
        self.request_id = request_id
        self.client_id = client_id
        self.client_name = client_name
        self.client_ip = client_ip
        self.client_port = client_port
        self.pin = pin
        self.created_at = time.monotonic()
        self.event = threading.Event()
        self.accepted = False
        self.auth_token = None
        self.sync_key = None


class PairManager:
    """配对与受信任设备管理器。"""

    def __init__(self, path=None):
        self.path = path or _paired_devices_path()
        self.paired_devices = {}  # device_id -> {name, token, ip, port, paired_at}
        self.pending_requests = {}  # request_id -> PairRequest
        self.recent_attempts = {}
        self.lock = threading.RLock()
        self.load()

    def load(self):
        with self.lock:
            if not os.path.exists(self.path):
                self.paired_devices = {}
                return
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.paired_devices = json.load(f)
            except Exception:
                self.paired_devices = {}

    def save(self):
        with self.lock:
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                tmp = self.path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.paired_devices, f, ensure_ascii=False, indent=2)
                os.replace(tmp, self.path)
                return True
            except Exception:
                return False

    def is_device_trusted(self, device_id, token):
        if not isinstance(token, str) or not token:
            return False
        with self.lock:
            devices = [self.paired_devices.get(device_id)] if device_id else self.paired_devices.values()
            for d in devices:
                saved = d.get("token") if isinstance(d, dict) else None
                if isinstance(saved, str) and saved and hmac.compare_digest(saved.encode(), token.encode()):
                    return True
        return False

    def get_trusted_devices(self):
        with self.lock:
            return dict(self.paired_devices)

    def create_pending_request(self, client_id, client_name, client_ip, client_port, pin=None):
        with self.lock:
            self._prune_requests()
            if (not isinstance(client_id, str) or not 1 <= len(client_id) <= 128
                    or not isinstance(client_name, str) or not 1 <= len(client_name) <= 128
                    or type(client_port) is not int or not 1 <= client_port <= 65535
                    or (pin not in (None, "") and (not isinstance(pin, str) or len(pin) != 6 or not pin.isascii() or not pin.isdigit()))):
                raise ValueError("无效的配对设备信息或 PIN")
            if (len(self.pending_requests) >= MAX_PENDING_PAIRS
                    or any(r.client_ip == client_ip for r in self.pending_requests.values())):
                raise OverflowError("配对请求过多，请稍后重试")
            attempts = self.recent_attempts.get(client_ip, [])
            if len(attempts) >= 5 or (client_ip not in self.recent_attempts and len(self.recent_attempts) >= 128):
                raise OverflowError("配对请求过于频繁，请稍后重试")
            self.recent_attempts[client_ip] = attempts + [time.monotonic()]
            req_id = secrets.token_urlsafe(24)
            if not pin:
                pin = str(secrets.randbelow(900000) + 100000)
            req = PairRequest(req_id, client_id, client_name, client_ip, client_port, pin)
            self.pending_requests[req_id] = req
            return req

    def get_pending_request(self, req_id):
        with self.lock:
            self._prune_requests()
            return self.pending_requests.get(req_id)

    def _prune_requests(self):
        now = time.monotonic()
        for ip, attempts in list(self.recent_attempts.items()):
            current = [t for t in attempts if now - t < 60]
            if current:
                self.recent_attempts[ip] = current
            else:
                del self.recent_attempts[ip]
        for req_id, req in list(self.pending_requests.items()):
            if now - req.created_at >= PAIR_TTL:
                req.event.set()
                del self.pending_requests[req_id]

    def clear_pending_requests(self):
        with self.lock:
            for req in self.pending_requests.values():
                req.event.set()
            self.pending_requests.clear()

    def complete_request(self, req_id):
        with self.lock:
            self.pending_requests.pop(req_id, None)

    def accept_request(self, req_id):
        with self.lock:
            self._prune_requests()
            req = self.pending_requests.get(req_id)
            if not req:
                return None
            if req.accepted:
                return req.auth_token
            token = "rhodes_" + secrets.token_urlsafe(32)
            req.accepted = True
            req.auth_token = token
            self.paired_devices[req.client_id] = {
                "name": req.client_name,
                "token": token,
                "ip": req.client_ip,
                "port": req.client_port,
                "paired_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            if req.sync_key:
                self.paired_devices[req.client_id].update(sync_key=req.sync_key, protocol=2)
            self.save()
            req.event.set()
            return token

    def reject_request(self, req_id):
        with self.lock:
            req = self.pending_requests.get(req_id)
            if req:
                req.accepted = False
                req.event.set()
                self.pending_requests.pop(req_id, None)

    def unpair_device(self, device_id):
        with self.lock:
            if device_id in self.paired_devices:
                del self.paired_devices[device_id]
                self.save()
                return True
            return False


class DataSyncEngine:
    """学业数据与日程整合引擎。"""

    @staticmethod
    def pack_all_data():
        """打包本地所有学业数据为 JSON 字典。"""
        # 1. 课表
        sched = Schedule()
        sched_data = {
            "term": sched.term,
            "term_start": sched.term_start.isoformat() if sched.term_start else "",
            "sections": sched.sections,
            "remind_minutes": sched.remind_minutes,
            "courses": [
                {
                    "id": c.id,
                    "name": c.name,
                    "weekday": c.weekday,
                    "sec_start": c.sec_start,
                    "sec_end": c.sec_end,
                    "week_start": c.week_start,
                    "week_end": c.week_end,
                    "parity": c.parity,
                    "room": c.room,
                    "teacher": c.teacher,
                    "campus": c.campus,
                    "note": c.note,
                    "custom_time": c.custom_time,
                }
                for c in sched.courses
            ],
            "notes": sched.notes,
        }

        # 2. 考试与任务 (映射为通用 exams 列表与 tasks 列表)
        tasks_mgr = Tasks()
        exams_list = []
        for t in tasks_mgr.items:
            if t.kind == "exam":
                try:
                    exam_time_ms = round(t.due.timestamp() * 1000)
                except Exception:
                    exam_time_ms = int(time.time() * 1000)
                exams_list.append({
                    "id": t.id,
                    "title": t.title,
                    "examTimeMillis": exam_time_ms,
                    "durationMinutes": t.exam_details.get("durationMinutes", 120),
                    "location": t.course or "",
                    "seatNumber": t.exam_details.get("seatNumber", ""),
                    "examType": t.exam_details.get("examType", "闭卷"),
                    "note": t.exam_details.get("note", ""),
                    **({"relatedCourseId": t.exam_details["relatedCourseId"]} if "relatedCourseId" in t.exam_details else {}),
                })

        # 3. 便签
        notes_mgr = NotesManager()
        notes_list = [n.to_dict() for n in notes_mgr.notes]

        return {
            "version": APP_VERSION,
            "timestamp": int(time.time()),
            "schedule": sched_data,
            "exams": exams_list,
            "notes": notes_list,
        }

    @staticmethod
    def apply_data(payload, mode="merge"):
        """将远端数据应用至本地。mode: 'merge' or 'replace'。"""
        results = {"schedule": False, "exams": 0, "notes": 0}

        # 1. 应用课表
        sched_data = payload.get("schedule")
        if isinstance(sched_data, dict):
            sched = Schedule()
            courses = []
            for c in sched_data.get("courses", []):
                try:
                    courses.append(Course(
                        name=c["name"], weekday=c["weekday"],
                        sec_start=c["sec_start"], sec_end=c["sec_end"],
                        week_start=c["week_start"], week_end=c["week_end"],
                        parity=c.get("parity", "all"),
                        room=c.get("room", ""), teacher=c.get("teacher", ""),
                        campus=c.get("campus", ""), note=c.get("note", ""),
                        id=c.get("id"), custom_time=c.get("custom_time", "")))
                except Exception:
                    continue
            
            term_start = None
            ts_str = sched_data.get("term_start", "")
            if ts_str:
                try:
                    from datetime import date
                    term_start = date.fromisoformat(ts_str)
                except Exception:
                    pass

            if mode == "replace" or not sched.courses:
                sched.save(
                    term=sched_data.get("term", sched.term),
                    term_start=term_start or sched.term_start,
                    courses=courses,
                    notes=sched_data.get("notes", sched.notes),
                    sections=sched_data.get("sections", sched.sections)
                )
            else:
                # Stable IDs carry edits; the full placement also recognizes legacy imports.
                def placement(c):
                    return (c.name, c.weekday, c.sec_start, c.sec_end, c.week_start,
                            c.week_end, c.parity, c.custom_time)
                for c in courses:
                    index = next((i for i, old in enumerate(sched.courses) if old.id == c.id), None)
                    if index is None:
                        index = next((i for i, old in enumerate(sched.courses) if placement(old) == placement(c)), None)
                    if index is None:
                        sched.courses.append(c)
                    else:
                        sched.courses[index] = c
                sched.save(
                    term=sched_data.get("term") or sched.term,
                    term_start=term_start or sched.term_start,
                    courses=sched.courses,
                    sections=sched_data.get("sections") or sched.sections
                )
            results["schedule"] = True

        # 2. 应用考试日程
        exams_data = payload.get("exams", [])
        if isinstance(exams_data, list) and exams_data:
            tasks_mgr = Tasks()
            added_count = 0
            for e in exams_data:
                title = e.get("title", "未命名考试")
                try:
                    ms = e.get("examTimeMillis", 0)
                    due_dt = datetime.fromtimestamp(ms / 1000.0) if ms > 0 else datetime.now()
                except Exception:
                    due_dt = datetime.now()
                location = e.get("location", "")
                existing = next((t for t in tasks_mgr.items if t.kind == "exam" and t.id == e.get("id")), None)
                if existing is None:
                    existing = next((t for t in tasks_mgr.items if t.kind == "exam" and t.title == title and t.due == due_dt), None)
                task = Task(
                    title=title,
                    kind="exam",
                    due=due_dt,
                    course=location,
                    remind_min=existing.remind_min if existing else 1440,
                    task_id=e.get("id") or (existing.id if existing else None),
                    done=existing.done if existing else False,
                    exam_details=e
                )
                if existing:
                    tasks_mgr.items[tasks_mgr.items.index(existing)] = task
                else:
                    tasks_mgr.items.append(task)
                added_count += 1
            tasks_mgr.save()
            results["exams"] = added_count

        # 3. 应用便签
        notes_data = payload.get("notes", [])
        if isinstance(notes_data, list) and notes_data:
            notes_mgr = NotesManager()
            existing_notes_map = {n.id: n for n in notes_mgr.notes}
            added_notes = 0
            for nd in notes_data:
                nid = nd.get("id")
                if not nid:
                    continue
                remote_note = Note.from_dict(nd)
                if nid in existing_notes_map:
                    local_note = existing_notes_map[nid]
                    # 若远端较新则更新
                    if remote_note.updated_at > local_note.updated_at:
                        local_note.title = remote_note.title
                        local_note.content = remote_note.content
                        local_note.updated_at = remote_note.updated_at
                        local_note.pinned = remote_note.pinned
                        added_notes += 1
                else:
                    notes_mgr.notes.append(remote_note)
                    added_notes += 1
            notes_mgr.save()
            results["notes"] = added_notes

        return results


class RhodesHttpHandler(http.server.BaseHTTPRequestHandler):
    """处理 Android 与 PC 之间的 HTTP 请求。"""

    @property
    def server_service(self):
        return self.server.server_service

    def setup(self):
        super().setup()
        self.connection.settimeout(SOCKET_TIMEOUT)
        self.secure_context = None
        self.secure_peer_id = ""
        self.secure_payload = {}
        self.invite_claim = None

    def finish(self):
        try:
            super().finish()
        finally:
            if self.invite_claim:
                self.server_service.secure.release_invite(*self.invite_claim)

    def _native_request(self):
        if "Origin" in self.headers or "Sec-Fetch-Site" in self.headers:
            self._send_json(403, {"error": "同步接口仅供原生客户端使用，拒绝浏览器跨站请求"})
            return False
        return True

    def log_message(self, format, *args):
        pass

    def _send_json(self, status_code, data):
        if self.secure_context:
            secret, path, request = self.secure_context
            try:
                data = seal(secret, path, data, request, "response", status_code)
            except InvalidEnvelope:
                status_code = 413
                data = seal(secret, path, {"error": "同步响应过大"}, request, "response", status_code)
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_OPTIONS(self):
        self._send_json(403, {"error": "Browser access is not supported"})

    def _check_auth(self):
        pair_mgr = self.server_service.pair_manager
        return bool(self.secure_peer_id) and pair_mgr.is_device_trusted(self.secure_peer_id, self.secure_payload.get("_auth_token"))

    def do_GET(self):
        if not self._native_request():
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/info":
            info = {
                "device_id": self.server_service.device_id,
                "device_name": self.server_service.device_name,
                "device_type": "pc",
                "http_port": self.server_service.http_port,
                "version": APP_VERSION,
                "paired": len(self.server_service.pair_manager.paired_devices) > 0,
                "protocol": 2,
                "epoch": self.server_service.secure.epoch,
            }
            return self._send_json(200, info)

        if path.startswith("/api/"):
            return self._send_json(426, {"error": "请升级并使用加密同步协议 v2，旧配对需要重新建立"})

        self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        if not self._native_request():
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path not in PATHS or parsed.query:
            return self._send_json(404, {"error": "Not Found"})
        if self.headers.get("X-Rhodes-Protocol") != "2" or "Authorization" in self.headers:
            return self._send_json(426, {"error": "仅支持加密同步协议 v2，请升级并重新配对"})

        lengths = self.headers.get_all("Content-Length", [])
        if "Transfer-Encoding" in self.headers or len(lengths) != 1:
            return self._send_json(400, {"error": "需要单个 Content-Length，不支持分块传输"})
        if not lengths[0].isascii() or not lengths[0].isdigit():
            return self._send_json(400, {"error": "Invalid Content-Length"})
        if len(lengths[0]) > 10:
            return self._send_json(413, {"error": "请求过大"})
        content_length = int(lengths[0])
        limit = MAX_PAIR_BYTES if path == "/api/pair/request" else (MAX_CLIPBOARD_BYTES if path == "/api/clipboard" else MAX_REQUEST_BYTES)
        if content_length > (limit + 16) * 4 // 3 + 2048:
            return self._send_json(413, {"error": "请求过大"})
        if content_length and self.headers.get_content_type() != "application/json":
            return self._send_json(415, {"error": "需要 application/json"})
        post_data = b""
        if content_length > 0:
            try:
                post_data = self.rfile.read(content_length)
            except (TimeoutError, OSError):
                return self._send_json(408, {"error": "请求读取超时"})
            if len(post_data) != content_length:
                return self._send_json(400, {"error": "请求体不完整"})

        payload = {}
        if post_data:
            try:
                payload = json.loads(post_data.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return self._send_json(400, {"error": "无效的 JSON"})
        if not isinstance(payload, dict):
            return self._send_json(400, {"error": "JSON 必须是对象"})
        envelope = payload
        kid = envelope.get("kid")
        secret = None
        if path == "/api/pair/request":
            secret = self.server_service.secure.invite_secret(kid)
        else:
            for device_id, device in self.server_service.pair_manager.get_trusted_devices().items():
                if device.get("protocol") == 2 and device.get("sync_key") and key_id(device["sync_key"]) == kid:
                    secret = device["sync_key"]
                    self.secure_peer_id = device_id
                    break
        try:
            if secret is None:
                raise InvalidEnvelope()
            payload = self.server_service.secure.accept(secret, path, envelope)
        except (InvalidEnvelope, TypeError, ValueError):
            return self._send_json(401, {"error": "加密认证失败，请重新配对"})
        self.secure_context = (secret, path, envelope)
        self.secure_payload = payload
        if path == "/api/pair/request":
            if not self.server_service.secure.claim_invite(secret, envelope["id"]):
                return self._send_json(429, {"error": "配对密钥正在使用或已失效"})
            self.invite_claim = (secret, envelope["id"])
        if len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()) > limit:
            return self._send_json(413, {"error": "请求过大"})

        # ── 1. 蓝牙式显式配对握手接口（无需事前 Token）─────────────────────
        if path == "/api/pair/request":
            client_id = payload.get("client_id", "")
            client_name = payload.get("client_name", "未知设备")
            client_ip = self.client_address[0]
            client_port = payload.get("client_port", DEFAULT_HTTP_PORT + 1)
            pin = pairing_code(secret)

            if not client_id:
                return self._send_json(400, {"error": "Missing client_id"})

            # 创建待确认请求
            try:
                req = self.server_service.pair_manager.create_pending_request(
                    client_id=client_id, client_name=client_name, client_ip=client_ip,
                    client_port=client_port, pin=pin)
            except ValueError as exc:
                return self._send_json(400, {"error": str(exc)})
            except OverflowError as exc:
                return self._send_json(429, {"error": str(exc)})

            # 触发 UI 确认回调（弹窗或桌面气泡通知）
            req.sync_key = secret
            if self.server_service.on_pair_request_callback:
                try:
                    self.server_service.on_pair_request_callback(req)
                except Exception:
                    pass

            # 同步等待用户点击确认，最多等待 30 秒
            accepted = req.event.wait(timeout=PAIR_TTL)
            self.server_service.pair_manager.complete_request(req.request_id)
            if accepted and req.accepted:
                self.server_service.secure.consume_invite(secret)
                return self._send_json(200, {
                    "status": "accepted",
                    "auth_token": req.auth_token,
                    "device_name": self.server_service.device_name,
                    "device_id": self.server_service.device_id
                })
            else:
                self.server_service.pair_manager.reject_request(req.request_id)
                return self._send_json(403, {
                    "status": "rejected",
                    "error": "配对请求被拒绝或超时未确认"
                })

        # ── 2. 以下接口严格要求已配对 Token ────────────────────────────────
        if not self._check_auth():
            return self._send_json(401, {"error": "Unauthorized. 请先完成终端配对确认。"})

        if path == "/api/sync/pull":
            data = DataSyncEngine.pack_all_data()
            return self._send_json(200, data)

        if path == "/api/sync/push":
            mode = payload.get("mode", "merge")
            result = DataSyncEngine.apply_data(payload, mode=mode)
            if self.server_service.on_data_synced_callback:
                try:
                    self.server_service.on_data_synced_callback(result)
                except Exception:
                    pass
            return self._send_json(200, {"status": "ok", "result": result})

        if path == "/api/clipboard":
            text = payload.get("text", "")
            title = payload.get("title", "来自对端终端")
            if text and self.server_service.on_clipboard_callback:
                try:
                    self.server_service.on_clipboard_callback(text, title)
                except Exception:
                    pass
            return self._send_json(200, {"status": "ok"})

        if path == "/api/status":
            event = payload.get("event", "")
            data = payload.get("data", {})
            if self.server_service.on_status_callback:
                try:
                    self.server_service.on_status_callback(event, data)
                except Exception:
                    pass
            return self._send_json(200, {"status": "ok"})

        if path == "/api/pair/unpair":
            device_id = payload.get("device_id", "")
            token = self.secure_payload.get("_auth_token")
            if not isinstance(device_id, str) or not self.server_service.pair_manager.is_device_trusted(device_id, token):
                return self._send_json(403, {"error": "只能解除自身设备的配对"})
            self.server_service.pair_manager.unpair_device(device_id)
            return self._send_json(200, {"status": "unpaired"})

        self._send_json(404, {"error": "Not Found"})


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 16

    def __init__(self, *args, **kwargs):
        self._slots = threading.BoundedSemaphore(16)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            try:
                # Drain a bounded header before closing. Windows may otherwise
                # reset a connection with unread bytes and hide the 503 reply.
                deadline = time.monotonic() + 0.1
                header = b""
                while b"\r\n\r\n" not in header and len(header) < 16384:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    request.settimeout(remaining)
                    chunk = request.recv(min(4096, 16384 - len(header)))
                    if not chunk:
                        break
                    header += chunk
            except OSError:
                pass
            try:
                request.settimeout(0.1)
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


class RhodesSyncService:
    """罗德岛跨端协同核心服务实例。"""

    def __init__(self, device_name=None, http_port=DEFAULT_HTTP_PORT, udp_port=DEFAULT_UDP_PORT):
        self.device_id = "pc_" + socket.gethostname().replace(" ", "_").lower()[:16]
        self.device_name = device_name or f"博士的 PC ({socket.gethostname()})"
        self.http_port = http_port
        self.udp_port = udp_port

        self.pair_manager = PairManager()
        self.http_server = None
        self.http_thread = None
        self.udp_socket = None
        self.udp_thread = None
        self.running = False
        self.secure = SecureSync()

        self.on_pair_request_callback = None
        self.on_clipboard_callback = None
        self.on_status_callback = None
        self.on_data_synced_callback = None

    def start(self):
        """启动 HTTP 与 UDP 局域网服务。"""
        if self.running:
            return
        self.secure = SecureSync()

        # 1. 启动多线程 HTTP 服务端
        self.http_server = None
        for port in range(self.http_port, self.http_port + 10):
            try:
                self.http_server = ThreadedHTTPServer(("0.0.0.0", port), RhodesHttpHandler)
                self.http_server.server_service = self
                self.http_port = self.http_server.server_address[1]
                break
            except OSError:
                continue

        if self.http_server:
            self.running = True
            self.http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
            self.http_thread.start()
        else:
            raise RuntimeError("无法启动同步服务：没有可用 HTTP 端口")

        # 2. 启动 UDP 发现监听服务
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.udp_socket.bind(("0.0.0.0", self.udp_port))
            self.udp_port = self.udp_socket.getsockname()[1]
            self.udp_socket.settimeout(0.5)
            self.udp_thread = threading.Thread(target=self._udp_listen_loop, daemon=True)
            self.udp_thread.start()
        except Exception:
            pass

    def stop(self):
        """安全停止所有网络监听。"""
        self.running = False
        self.pair_manager.clear_pending_requests()
        if self.http_server:
            try:
                self.http_server.shutdown()
                self.http_server.server_close()
            except Exception:
                pass
        if self.udp_socket:
            try:
                self.udp_socket.close()
            except Exception:
                pass
        for thread in (self.http_thread, self.udp_thread):
            if thread and thread is not threading.current_thread():
                thread.join(timeout=1.0)

    def _udp_listen_loop(self):
        while self.running:
            try:
                data, addr = self.udp_socket.recvfrom(2048)
                if not data:
                    continue
                try:
                    msg = json.loads(data.decode("utf-8"))
                except Exception:
                    continue

                cmd = msg.get("cmd")
                if cmd == "DISCOVER":
                    resp = {
                        "cmd": "DISCOVER_ACK",
                        "device_id": self.device_id,
                        "device_name": self.device_name,
                        "device_type": "pc",
                        "http_port": self.http_port,
                        "version": APP_VERSION,
                    }
                    self.udp_socket.sendto(json.dumps(resp).encode("utf-8"), addr)
            except socket.timeout:
                continue
            except Exception:
                break

    def scan_lan_devices(self, timeout=1.5):
        """主动广播搜索局域网内的所有终端（PC 或 Android）。"""
        discovered = []
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)

        msg = {
            "cmd": "DISCOVER",
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_type": "pc",
            "http_port": self.http_port,
        }
        try:
            sock.sendto(json.dumps(msg).encode("utf-8"), ("255.255.255.255", self.udp_port))
            start_t = time.time()
            while time.time() - start_t < timeout:
                try:
                    data, addr = sock.recvfrom(2048)
                    res = json.loads(data.decode("utf-8"))
                    if res.get("cmd") == "DISCOVER_ACK" and res.get("device_id") != self.device_id:
                        res["ip"] = addr[0]
                        discovered.append(res)
                except socket.timeout:
                    break
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            sock.close()
        return discovered

    def probe_device(self, ip, port=DEFAULT_HTTP_PORT):
        """直连探测指定 IP 与端口的设备信息（解决 AP 隔离问题）。"""
        url = f"http://{ip}:{port}/api/info"
        req = urllib.request.Request(url, headers={"User-Agent": "RhodesSync/1.0"})
        try:
            with _open_sync_request(req, timeout=3.0) as resp:
                if resp.status == 200:
                    data = _read_sync_json(resp)
                    data["ip"] = ip
                    data["http_port"] = port
                    return data
        except Exception:
            return None
        return None

    def create_pairing_invite(self):
        return self.secure.create_invite()

    def _key_for_token(self, token):
        for device in self.pair_manager.get_trusted_devices().values():
            saved = device.get("token")
            if (isinstance(token, str) and isinstance(saved, str) and token
                    and hmac.compare_digest(token.encode(), saved.encode())
                    and device.get("protocol") == 2 and device.get("sync_key")):
                return device["sync_key"]
        raise InvalidEnvelope("旧配对已失效，请使用配对密钥重新配对")

    def _secure_post(self, ip, port, path, payload, secret, token=None, timeout=10):
        # Discovery contains no credentials. A forged epoch can only cause failure.
        info = self.probe_device(ip, port)
        if not info or info.get("protocol") != 2:
            raise InvalidEnvelope("目标设备不支持加密同步 v2，请先升级")
        body = dict(payload)
        if token:
            body["_auth_token"] = token
        envelope = make_request(secret, path, body, info.get("epoch"))
        req = urllib.request.Request(f"http://{ip}:{port}{path}",
            data=json.dumps(envelope, separators=(",", ":")).encode(),
            headers={"Content-Type": "application/json", "X-Rhodes-Protocol": "2"})
        try:
            response = _open_sync_request(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            status = response.code
            result = read_response(secret, path, _read_sync_json(response), envelope, status)
        return status, result

    def request_pair(self, target_ip, target_port, pin=None, pairing_secret=None):
        """The receiving device's random invitation is supplied out of band."""
        try:
            key_id(pairing_secret)
            payload = {"client_id": self.device_id, "client_name": self.device_name,
                       "client_port": self.http_port,
                       "pin": pairing_code(pairing_secret)}
            status, result = self._secure_post(target_ip, target_port, "/api/pair/request",
                                               payload, pairing_secret, timeout=35)
            if status != 200 or result.get("status") != "accepted":
                return False, result.get("error", "配对被拒绝"), None
            token, device_id = result.get("auth_token"), result.get("device_id")
            if not isinstance(token, str) or not token or not isinstance(device_id, str) or not device_id:
                raise InvalidEnvelope("无效的配对响应")
            with self.pair_manager.lock:
                self.pair_manager.paired_devices[device_id] = {
                    "name": result.get("device_name", target_ip), "token": token,
                    "ip": target_ip, "port": target_port, "sync_key": pairing_secret,
                    "protocol": 2, "paired_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                self.pair_manager.save()
            return True, "加密配对成功！", result
        except Exception:
            return False, "加密配对失败：请确认两端已升级、配对密钥正确且未过期，并在接收端确认。", None

    def send_clipboard(self, target_ip, target_port, token, text, title=None):
        try:
            status, _ = self._secure_post(target_ip, target_port, "/api/clipboard",
                {"text": text, "title": title or self.device_name, "timestamp": int(time.time())},
                self._key_for_token(token), token, timeout=5)
            return status == 200
        except Exception:
            return False

    def sync_pull(self, target_ip, target_port, token):
        try:
            status, payload = self._secure_post(target_ip, target_port, "/api/sync/pull", {}, self._key_for_token(token), token)
            if status != 200:
                return False, payload.get("error", "拉取失败")
            return True, DataSyncEngine.apply_data(payload, mode="merge")
        except Exception:
            return False, "加密拉取失败，请检查连接或重新配对"

    def sync_push(self, target_ip, target_port, token, mode="merge"):
        try:
            payload = DataSyncEngine.pack_all_data()
            payload["mode"] = mode
            status, result = self._secure_post(target_ip, target_port, "/api/sync/push", payload, self._key_for_token(token), token)
            return status == 200, result.get("result") if status == 200 else result.get("error", "推送失败")
        except Exception:
            return False, "加密推送失败，请检查连接或重新配对"

    def broadcast_status(self, event, data=None):
        for device in self.pair_manager.get_trusted_devices().values():
            if device.get("protocol") != 2:
                continue
            def send_status(peer=dict(device)):
                try:
                    self._secure_post(peer["ip"], peer["port"], "/api/status",
                        {"event": event, "data": data or {}, "timestamp": int(time.time())},
                        peer["sync_key"], peer["token"], timeout=3)
                except Exception:
                    pass
            threading.Thread(target=send_status, daemon=True).start()


_GLOBAL_SYNC_SERVICE = None


def get_sync_service():
    global _GLOBAL_SYNC_SERVICE
    if _GLOBAL_SYNC_SERVICE is None:
        _GLOBAL_SYNC_SERVICE = RhodesSyncService()
    return _GLOBAL_SYNC_SERVICE
