"""Run native PC/Android acceptance on one authorized device, using isolated app data.

Build with -PsyncAcceptance=true assembleDebug assembleDebugAndroidTest first.
USB ADB tunnels exercise real device code; they do not establish Wi-Fi discovery coverage.
"""
import argparse
import copy
import hmac
import http.server
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "com.amiya.pet.syncacceptance"
RUNNER = "com.amiya.pet.acceptance.SyncAcceptanceRunner"


def fixture():
    return {"schedule": {"term": "Acceptance", "term_start": "2026-09-01", "sections": {"1": "08:07", "2": "09:03"},
            "courses": [{"id": "accept-course", "name": "验收临时活动", "weekday": 2, "sec_start": 1, "sec_end": 2,
                "week_start": 1, "week_end": 16, "parity": "odd", "custom_time": "18:25-19:40", "room": "验收教室", "teacher": "验收教师", "campus": "验收校区", "note": "中文 😀"}]},
            "exams": [{"id": "accept-exam", "title": "验收考试", "examTimeMillis": 1800000001234, "durationMinutes": 75,
                "location": "验收考场", "seatNumber": "7", "examType": "开卷", "note": "允许计算器", "relatedCourseId": "accept-course"}],
            "notes": [{"id": "accept-note", "title": "验收笔记", "content": "跨设备中文与 emoji 😀", "created_at": "2020-01-01 00:00",
                "updated_at": "2025-01-01 00:00", "pinned": True}]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", required=True, type=Path)
    parser.add_argument("--serial")
    parser.add_argument("--aapt", required=True, type=Path)
    parser.add_argument("--app-apk", type=Path, default=ROOT / "android/app/build/outputs/apk/debug/app-debug.apk")
    parser.add_argument("--test-apk", type=Path, default=ROOT / "android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk")
    parser.add_argument("--report", type=Path, default=ROOT / "scratch/android-sync-acceptance.json")
    args = parser.parse_args()

    def run(command, timeout=30):
        result = subprocess.run(list(map(str, command)), capture_output=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[:300])
        return result.stdout.decode("utf-8", errors="replace").strip()

    # Refuse to install any APK targeting the user's normal application.
    app_info = run([args.aapt, "dump", "badging", args.app_apk])
    if not re.search(r"package: name='" + re.escape(PACKAGE) + r"'", app_info):
        raise RuntimeError("App APK is not the isolated syncacceptance variant")
    test_info = run([args.aapt, "dump", "xmltree", args.test_apk, "AndroidManifest.xml"])
    target = re.search(r'android:targetPackage[^=]*="([^"]+)"', test_info)
    if not target or target.group(1) != PACKAGE:
        raise RuntimeError("Instrumentation does not target the isolated app")
    devices = [line.split()[0] for line in run([args.adb, "devices"]).splitlines()[1:] if len(line.split()) >= 2 and line.split()[1] == "device"]
    serial = args.serial or (devices[0] if len(devices) == 1 else None)
    if serial not in devices:
        raise RuntimeError("Select exactly one authorized Android device")

    def adb(*command, timeout=30):
        return run([args.adb, "-s", serial, *command], timeout=timeout)

    device = {key: adb("shell", "getprop", prop) for key, prop in
              (("model", "ro.product.model"), ("manufacturer", "ro.product.manufacturer"),
               ("android", "ro.build.version.release"), ("sdk", "ro.build.version.sdk"))}
    device["kind"] = "emulator" if adb("shell", "getprop", "ro.kernel.qemu") == "1" or serial.startswith("emulator-") else "physical Android"
    print("Device: " + json.dumps(device, ensure_ascii=True), flush=True)
    adb("install", "-r", "-t", str(args.app_apk), timeout=120)
    adb("install", "-r", "-t", str(args.test_apk), timeout=120)
    # Reset only this fixed, independently verified package to make reruns deterministic.
    if adb("shell", "pm", "clear", PACKAGE) != "Success":
        raise RuntimeError("Could not reset the isolated acceptance application")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    report = {"device": device, "transport": "USB ADB forwarded TCP (not Wi-Fi LAN)", "checks": [], "passed": False}
    forwards, reverses = [], []
    control_server = service = None
    with tempfile.TemporaryDirectory(prefix="amiya-device-acceptance-") as data_dir:
        os.environ["APPDATA"] = str(Path(data_dir) / "appdata")
        os.environ["XDG_CONFIG_HOME"] = str(Path(data_dir) / "config")
        for key in list(os.environ):
            if key.startswith("PET_") and key.endswith("_FILE"):
                del os.environ[key]
        sys.path.insert(0, str(ROOT))
        from pet import sync_service as sync
        from pet import sync_crypto
        captured = []
        sensitive = []
        state = {"phone_port": None, "clipboard": []}

        class RecordingReader:
            def __init__(self, reader): self.reader = reader
            def read(self, size=-1):
                data = self.reader.read(size); captured.append(data); return data
            def __getattr__(self, name): return getattr(self.reader, name)

        class RecordingWriter:
            def __init__(self, writer): self.writer = writer
            def write(self, data):
                captured.append(data)
                return self.writer.write(data)
            def __getattr__(self, name): return getattr(self.writer, name)

        class RecordingHandler(sync.RhodesHttpHandler):
            def setup(self):
                super().setup()
                self.wfile = RecordingWriter(self.wfile)
            def do_POST(self):
                self.rfile = RecordingReader(self.rfile)
                if "Authorization" in self.headers:
                    state["plaintext_authorization"] = True
                super().do_POST()

        sync.RhodesHttpHandler = RecordingHandler
        original_open = sync._open_sync_request
        def capture_open(request, timeout):
            if request.data:
                captured.append(request.data)
                if request.get_header("Authorization"):
                    state["plaintext_authorization"] = True
            response = original_open(request, timeout)
            response.read = capture_read(response.read)
            return response
        def capture_read(read):
            def recorded_read(*args, **kwargs):
                data = read(*args, **kwargs)
                captured.append(data)
                return data
            return recorded_read
        sync._open_sync_request = capture_open
        service = sync.RhodesSyncService("Acceptance PC", http_port=0, udp_port=0)
        service.device_id = "acceptance-pc"
        service.on_pair_request_callback = lambda request: (service.pair_manager.accept_request(request.request_id)
            if request.client_id == "acceptance-android" else service.pair_manager.reject_request(request.request_id))
        service.on_clipboard_callback = lambda text, title: state["clipboard"].append(text)
        service.start()
        secret = service.create_pairing_invite(); sensitive.append(secret.encode())
        control_token = secrets.token_urlsafe(32)

        def phone_token():
            record = service.pair_manager.get_trusted_devices().get("acceptance-android")
            if not record: raise RuntimeError("No paired acceptance phone")
            sensitive.extend([record["token"].encode(), record["sync_key"].encode()])
            return record["token"]

        def action(payload):
            name = payload.get("action")
            if name == "phone_port":
                port = payload.get("port")
                if type(port) is not int or not 1 <= port <= 65535: raise ValueError("Invalid phone port")
                if state["phone_port"] is not None:
                    adb("forward", "--remove", "tcp:" + str(state["phone_port"]))
                    forwards.remove(state["phone_port"])
                forwarded = int(adb("forward", "tcp:0", "tcp:" + str(port)))
                state["phone_port"] = forwarded; forwards.append(forwarded)
                with service.pair_manager.lock:
                    record = service.pair_manager.paired_devices.get("acceptance-android")
                    if record:
                        record["ip"] = "127.0.0.1"; record["port"] = forwarded
                        service.pair_manager.save()
                return {"ok": True}
            if name == "seed":
                expected = fixture()
                sync.DataSyncEngine.apply_data(copy.deepcopy(expected), "replace")
                return {"expected": expected}
            if name == "check_clipboard": return {"ok": state["clipboard"] == ["Android 真机中文快传 😀"]}
            if name == "send_clipboard": return {"ok": service.send_clipboard("127.0.0.1", state["phone_port"], phone_token(), "PC 中文快传到真机 😀")}
            if name == "pull_phone": return {"ok": service.sync_pull("127.0.0.1", state["phone_port"], phone_token())[0]}
            if name == "check_pc_data":
                actual, expected = sync.DataSyncEngine.pack_all_data(), fixture()
                def contains(items, wanted):
                    return any(all(item.get(k) == v for k, v in wanted.items()) for item in items)
                ok = (all(actual["schedule"]["sections"].get(k) == v for k, v in expected["schedule"]["sections"].items())
                    and all(contains(actual["schedule"]["courses"], c) for c in expected["schedule"]["courses"])
                    and all(contains(actual["exams"], e) for e in expected["exams"])
                    and all(contains(actual["notes"], n) for n in expected["notes"]))
                return {"ok": ok}
            if name == "push_phone": return {"ok": service.sync_push("127.0.0.1", state["phone_port"], phone_token())[0]}
            if name == "restart_pc": service.stop(); service.start(); return {"ok": True}
            if name == "pair_phone":
                invitation = payload.get("secret"); sensitive.append(invitation.encode())
                return {"ok": service.request_pair("127.0.0.1", state["phone_port"], pairing_secret=invitation)[0]}
            if name in ("new_invite", "expired_invite"):
                invitation = service.create_pairing_invite(); sensitive.append(invitation.encode())
                if name == "expired_invite": service.secure.invite = (invitation, time.monotonic() - 1)
                return {"secret": invitation}
            raise ValueError("Unknown acceptance action")

        class Control(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                try:
                    if "Origin" in self.headers or not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + control_token):
                        self.send_error(403); return
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 4096: self.send_error(413); return
                    result = action(json.loads(self.rfile.read(length)))
                    body = json.dumps(result, ensure_ascii=False).encode()
                    self.send_response(200); self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
                except Exception as exc:
                    state["control_error"] = type(exc).__name__
                    self.send_error(500, "Acceptance control failed")

        try:
            control_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Control)
            threading.Thread(target=control_server.serve_forever, daemon=True).start()
            for port in (service.http_port, control_server.server_port):
                adb("reverse", "tcp:" + str(port), "tcp:" + str(port)); reverses.append(port)
            output = adb("shell", "am", "instrument", "-w", "-r", "-e", "host", "127.0.0.1",
                "-e", "pc_port", str(service.http_port), "-e", "control_port", str(control_server.server_port),
                "-e", "control_token", control_token, "-e", "pairing_secret", secret, PACKAGE + ".test/" + RUNNER, timeout=240)
            summary_line = next((line.split("summary=", 1)[1] for line in output.splitlines() if line.startswith("INSTRUMENTATION_RESULT: summary=")), None)
            if not summary_line: raise RuntimeError("Instrumentation did not return a summary")
            summary = json.loads(summary_line)
            report.update(summary)
            markers = ["Android 真机中文快传 😀".encode(), "PC 中文快传到真机 😀".encode(), "跨设备中文与 emoji 😀".encode()]
            wire_ok = bool(captured) and not state.get("plaintext_authorization") and not any(needle in body for body in captured for needle in sensitive + markers)
            report["checks"].append({"name": "wire_contains_no_test_secrets_or_plaintext", "passed": wire_ok})
            report["passed"] = bool(summary.get("passed")) and wire_ok
            report["wire_chunks_checked"] = len(captured)
            if state.get("control_error"): report["control_error"] = state["control_error"]
        except Exception as exc:
            report["fatal"] = ("Instrumentation timed out" if isinstance(exc, subprocess.TimeoutExpired)
                               else type(exc).__name__ + ": " + str(exc)[:180])
            report["passed"] = False
        finally:
            for port in forwards:
                try: adb("forward", "--remove", "tcp:" + str(port))
                except Exception: pass
            for port in reverses:
                try: adb("reverse", "--remove", "tcp:" + str(port))
                except Exception: pass
            try: adb("shell", "am", "force-stop", PACKAGE)
            except Exception: pass
            if control_server: control_server.shutdown(); control_server.server_close()
            if service: service.stop()
            sync._open_sync_request = original_open
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=True, indent=2), flush=True)
        return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
