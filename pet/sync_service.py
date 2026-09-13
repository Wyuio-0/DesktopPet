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
import random
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

DEFAULT_HTTP_PORT = 23333
DEFAULT_UDP_PORT = 23332
APP_VERSION = "1.9.0"


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
        self.created_at = time.time()
        self.event = threading.Event()
        self.accepted = False
        self.auth_token = None


class PairManager:
    """配对与受信任设备管理器。"""

    def __init__(self, path=None):
        self.path = path or _paired_devices_path()
        self.paired_devices = {}  # device_id -> {name, token, ip, port, paired_at}
        self.pending_requests = {}  # request_id -> PairRequest
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
        with self.lock:
            dev = self.paired_devices.get(device_id)
            if dev and dev.get("token") == token:
                return True
            # Also check if token matches any trusted device
            for d in self.paired_devices.values():
                if d.get("token") == token:
                    return True
        return False

    def get_trusted_devices(self):
        with self.lock:
            return dict(self.paired_devices)

    def create_pending_request(self, client_id, client_name, client_ip, client_port, pin=None):
        with self.lock:
            req_id = uuid.uuid4().hex[:8]
            if not pin:
                pin = f"{random.randint(100000, 999999)}"
            req = PairRequest(req_id, client_id, client_name, client_ip, client_port, pin)
            self.pending_requests[req_id] = req
            return req

    def get_pending_request(self, req_id):
        with self.lock:
            return self.pending_requests.get(req_id)

    def accept_request(self, req_id):
        with self.lock:
            req = self.pending_requests.get(req_id)
            if not req:
                return None
            token = "rhodes_" + uuid.uuid4().hex
            req.accepted = True
            req.auth_token = token
            self.paired_devices[req.client_id] = {
                "name": req.client_name,
                "token": token,
                "ip": req.client_ip,
                "port": req.client_port,
                "paired_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
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
                    exam_time_ms = int(t.due.timestamp() * 1000)
                except Exception:
                    exam_time_ms = int(time.time() * 1000)
                exams_list.append({
                    "id": t.id,
                    "title": t.title,
                    "examTimeMillis": exam_time_ms,
                    "durationMinutes": 120,
                    "location": t.course or "",
                    "seatNumber": "",
                    "examType": "闭卷",
                    "note": "",
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
                        campus=c.get("campus", ""), note=c.get("note", "")))
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
                # 合并模式：按名称+星期+节次去重
                existing_keys = {(c.name, c.weekday, c.sec_start) for c in sched.courses}
                for c in courses:
                    if (c.name, c.weekday, c.sec_start) not in existing_keys:
                        sched.courses.append(c)
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
            existing_exam_titles = {t.title for t in tasks_mgr.items if t.kind == "exam"}
            added_count = 0
            for e in exams_data:
                title = e.get("title", "未命名考试")
                if mode == "merge" and title in existing_exam_titles:
                    continue
                try:
                    ms = e.get("examTimeMillis", 0)
                    due_dt = datetime.fromtimestamp(ms / 1000.0) if ms > 0 else datetime.now()
                except Exception:
                    due_dt = datetime.now()
                location = e.get("location", "")
                tasks_mgr.add(
                    title=title,
                    kind="exam",
                    due=due_dt,
                    course=location,
                    remind_min=1440
                )
                added_count += 1
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

    server_service = None  # RhodesSyncService instance

    def log_message(self, format, *args):
        pass

    def _send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def _check_auth(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return False
        token = auth[7:].strip()
        pair_mgr = self.server_service.pair_manager
        return pair_mgr.is_device_trusted("", token)

    def do_GET(self):
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
            }
            return self._send_json(200, info)

        if path == "/api/pair/status":
            query = urllib.parse.parse_qs(parsed.query)
            req_id = query.get("request_id", [""])[0]
            req = self.server_service.pair_manager.get_pending_request(req_id)
            if not req:
                return self._send_json(404, {"error": "Request not found"})
            if req.accepted:
                return self._send_json(200, {
                    "status": "accepted",
                    "auth_token": req.auth_token,
                    "device_name": self.server_service.device_name
                })
            return self._send_json(200, {"status": "pending"})

        if path == "/api/sync/pull":
            if not self._check_auth():
                return self._send_json(401, {"error": "Unauthorized. 请先完成终端配对确认。"})
            data = DataSyncEngine.pack_all_data()
            return self._send_json(200, data)

        self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = b""
        if content_length > 0:
            post_data = self.rfile.read(content_length)

        payload = {}
        if post_data:
            try:
                payload = json.loads(post_data.decode("utf-8"))
            except Exception:
                pass

        # ── 1. 蓝牙式显式配对握手接口（无需事前 Token）─────────────────────
        if path == "/api/pair/request":
            client_id = payload.get("client_id", "")
            client_name = payload.get("client_name", "未知设备")
            client_ip = self.client_address[0]
            client_port = payload.get("client_port", DEFAULT_HTTP_PORT + 1)
            pin = payload.get("pin", "")

            if not client_id:
                return self._send_json(400, {"error": "Missing client_id"})

            # 创建待确认请求
            req = self.server_service.pair_manager.create_pending_request(
                client_id=client_id,
                client_name=client_name,
                client_ip=client_ip,
                client_port=client_port,
                pin=pin
            )

            # 触发 UI 确认回调（弹窗或桌面气泡通知）
            if self.server_service.on_pair_request_callback:
                try:
                    self.server_service.on_pair_request_callback(req)
                except Exception:
                    pass

            # 同步等待用户点击确认，最多等待 30 秒
            accepted = req.event.wait(timeout=30.0)
            if accepted and req.accepted:
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
            self.server_service.pair_manager.unpair_device(device_id)
            return self._send_json(200, {"status": "unpaired"})

        self._send_json(404, {"error": "Not Found"})


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


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

        self.on_pair_request_callback = None
        self.on_clipboard_callback = None
        self.on_status_callback = None
        self.on_data_synced_callback = None

    def start(self):
        """启动 HTTP 与 UDP 局域网服务。"""
        if self.running:
            return
        self.running = True

        # 1. 启动多线程 HTTP 服务端
        RhodesHttpHandler.server_service = self
        for port in range(self.http_port, self.http_port + 10):
            try:
                self.http_server = ThreadedHTTPServer(("0.0.0.0", port), RhodesHttpHandler)
                self.http_port = port
                break
            except OSError:
                continue

        if self.http_server:
            self.http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
            self.http_thread.start()

        # 2. 启动 UDP 发现监听服务
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.udp_socket.bind(("0.0.0.0", self.udp_port))
            self.udp_thread = threading.Thread(target=self._udp_listen_loop, daemon=True)
            self.udp_thread.start()
        except Exception:
            pass

    def stop(self):
        """安全停止所有网络监听。"""
        self.running = False
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
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    data["ip"] = ip
                    data["http_port"] = port
                    return data
        except Exception:
            return None
        return None

    def request_pair(self, target_ip, target_port, pin=None):
        """向目标设备主动发起配对请求，等待对方屏幕确认。"""
        if not pin:
            pin = f"{random.randint(100000, 999999)}"
        url = f"http://{target_ip}:{target_port}/api/pair/request"
        local_ips = get_local_ips()
        payload = {
            "client_id": self.device_id,
            "client_name": self.device_name,
            "client_ip": local_ips[0] if local_ips else "127.0.0.1",
            "client_port": self.http_port,
            "pin": pin
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data_bytes,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        try:
            with urllib.request.urlopen(req, timeout=35.0) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if res.get("status") == "accepted":
                    token = res.get("auth_token")
                    dev_name = res.get("device_name", target_ip)
                    dev_id = res.get("device_id", target_ip)
                    with self.pair_manager.lock:
                        self.pair_manager.paired_devices[dev_id] = {
                            "name": dev_name,
                            "token": token,
                            "ip": target_ip,
                            "port": target_port,
                            "paired_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        self.pair_manager.save()
                    return True, "配对成功并已建立信任！", res
                return False, res.get("error", "配对被拒绝"), res
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                return False, err_body.get("error", f"HTTP {e.code}"), err_body
            except Exception:
                return False, f"配对失败 (HTTP {e.code})", None
        except Exception as e:
            return False, f"连接目标异常: {str(e)}", None

    def send_clipboard(self, target_ip, target_port, token, text, title=None):
        """将剪贴板文本发送给对端设备。"""
        url = f"http://{target_ip}:{target_port}/api/clipboard"
        payload = {
            "text": text,
            "title": title or self.device_name,
            "timestamp": int(time.time())
        }
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {token}"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def sync_pull(self, target_ip, target_port, token):
        """从目标设备拉取学业数据并应用到本地。"""
        url = f"http://{target_ip}:{target_port}/api/sync/pull"
        req = urllib.request.Request(
            url,
            data=b"{}",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {token}"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read().decode("utf-8"))
                    result = DataSyncEngine.apply_data(payload, mode="merge")
                    return True, result
        except Exception as e:
            return False, str(e)
        return False, "拉取失败"

    def sync_push(self, target_ip, target_port, token, mode="merge"):
        """将本地学业数据推送到目标设备。"""
        url = f"http://{target_ip}:{target_port}/api/sync/push"
        payload = DataSyncEngine.pack_all_data()
        payload["mode"] = mode
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {token}"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return True, data.get("result")
        except Exception as e:
            return False, str(e)
        return False, "推送失败"

    def broadcast_status(self, event, data=None):
        """向所有已配对设备广播当前状态（如专注自习开始/结束）。"""
        paired = self.pair_manager.get_trusted_devices()
        payload = {"event": event, "data": data or {}, "timestamp": int(time.time())}
        for dev_id, dev_info in paired.items():
            ip = dev_info.get("ip")
            port = dev_info.get("port")
            token = dev_info.get("token")
            if not ip or not port or not token:
                continue
            url = f"http://{ip}:{port}/api/status"
            try:
                req = urllib.request.Request(
                    url, data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                        "Authorization": f"Bearer {token}"
                    }
                )
                threading.Thread(target=urllib.request.urlopen, args=(req,), kwargs={"timeout": 3.0}, daemon=True).start()
            except Exception:
                pass


_GLOBAL_SYNC_SERVICE = None


def get_sync_service():
    global _GLOBAL_SYNC_SERVICE
    if _GLOBAL_SYNC_SERVICE is None:
        _GLOBAL_SYNC_SERVICE = RhodesSyncService()
    return _GLOBAL_SYNC_SERVICE
