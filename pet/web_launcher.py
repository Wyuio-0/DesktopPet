"""NotebookLM Web 版启动器与服务托管模块。

负责在桌宠运行期间自动托管 Web 服务（后台守护线程运行），
提供一键在默认浏览器打开 Google NotebookLM 课件研读界面的接口，
并支持随时从托盘菜单或桌宠右键菜单手动停止服务、释放端口。
"""

import asyncio
import socket
import sys
import threading
import time
import urllib.parse
import webbrowser

from . import logging as petlog
from web.security import ACCESS_KEY, local_host

_SERVER_STARTED = False
_SERVER_LOCK = threading.Lock()
_LOOP = None
_RUNNER = None
_SITE = None
_SERVER_THREAD = None
_ACCESS = None
_WEB_SERVER = None
_SERVER_ADDRESS = None


def is_server_listening(host: str = "127.0.0.1", port: int = 5050) -> bool:
    """检查指定端口是否已在监听。"""
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except (OSError, ConnectionRefusedError):
        return False


def is_running(host: str = "127.0.0.1", port: int = 5050) -> bool:
    """判断 NotebookLM Web 服务是否正在运行。"""
    return is_server_listening(host, port)


def _get_web_server_module():
    """动态获取 web.server 模块，优先读取磁盘上的最新源文件，方便热更新与免重构调试。"""
    import importlib.util
    import os
    import sys

    base_dirs = []
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        base_dirs.extend([exe_dir, os.path.join(exe_dir, '_internal')])
    else:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        base_dirs.append(root_dir)

    for b in base_dirs:
        candidate = os.path.join(b, "web", "server.py")
        if os.path.isfile(candidate):
            try:
                spec = importlib.util.spec_from_file_location("web.server", candidate)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    return mod
            except Exception as e:
                petlog.warn(f"web_launcher: 动态载入外部 {candidate} 失败，回退内建模块: {e}")

    import web.server as ws
    return ws


def ensure_server_running(host: str = "127.0.0.1", port: int = 5050, brain=None, kb=None) -> bool:
    """Start an owned loopback service; never trust another listener on the port."""
    global _SERVER_STARTED, _SERVER_THREAD
    host = local_host(host)
    with _SERVER_LOCK:
        if (_SITE is not None and _SERVER_ADDRESS == (host, port)
                and _SERVER_THREAD and _SERVER_THREAD.is_alive()):
            if brain is not None or kb is not None:
                _WEB_SERVER.set_app_context(brain, kb)
            return True
        if is_server_listening(host, port) or (_SERVER_THREAD and _SERVER_THREAD.is_alive()):
            petlog.warn("web_launcher: 端口已占用或工作台正在启动，请关闭已有服务后重试")
            return False

        ready = threading.Event()

        def _run_server():
            global _LOOP, _RUNNER, _SITE, _ACCESS, _WEB_SERVER, _SERVER_ADDRESS
            loop = asyncio.new_event_loop()
            runner = None
            try:
                asyncio.set_event_loop(loop)
                _LOOP = loop
                from aiohttp import web
                ws = _get_web_server_module()
                if brain is not None or kb is not None:
                    ws.set_app_context(brain, kb)
                app = ws.make_app()
                runner = web.AppRunner(app, access_log=None)
                loop.run_until_complete(runner.setup())
                site = web.TCPSite(runner, host, port)
                loop.run_until_complete(site.start())
                _RUNNER, _SITE = runner, site
                _ACCESS, _WEB_SERVER = app[ACCESS_KEY], ws
                _SERVER_ADDRESS = (host, port)
                ready.set()
                petlog.log("web_launcher: NotebookLM 本机服务已就绪")
                loop.run_forever()
            except Exception as e:
                petlog.warn(f"web_launcher: 后台启动 NotebookLM 服务失败: {e}")
            finally:
                try:
                    if runner:
                        loop.run_until_complete(runner.cleanup())
                finally:
                    loop.close()
                    _LOOP = _RUNNER = _SITE = None
                    _ACCESS = _WEB_SERVER = _SERVER_ADDRESS = None
                    ready.set()

        _SERVER_THREAD = threading.Thread(target=_run_server, name="NotebookLMWebDaemon", daemon=True)
        _SERVER_THREAD.start()
        ready.wait(timeout=6)
        _SERVER_STARTED = _SITE is not None and _SERVER_ADDRESS == (host, port)
        return _SERVER_STARTED


def stop_server(timeout: float = 2.0, host: str = "127.0.0.1", port: int = 5050) -> bool:
    """优雅停止 NotebookLM Web 服务并释放端口。

    Returns:
        bool: 服务是否已成功停止并释放端口。
    """
    global _SERVER_STARTED, _LOOP, _RUNNER, _SITE, _SERVER_THREAD
    with _SERVER_LOCK:
        if not is_server_listening(host, port) and not (_SERVER_THREAD and _SERVER_THREAD.is_alive()):
            _SERVER_STARTED = False
            _LOOP = None
            _RUNNER = None
            _SITE = None
            _SERVER_THREAD = None
            return True

        petlog.log("web_launcher: 正在停止 NotebookLM Web 服务...")
        loop = _LOOP
        runner = _RUNNER

        if loop and loop.is_running():
            try:
                async def _shutdown():
                    if runner:
                        try:
                            await runner.cleanup()
                        except Exception:
                            pass

                f = asyncio.run_coroutine_threadsafe(_shutdown(), loop)
                try:
                    f.result(timeout=timeout)
                    loop.call_soon_threadsafe(loop.stop)
                except Exception as e:
                    petlog.warn(f"web_launcher: cleanup runner 异常: {e}")
                    loop.call_soon_threadsafe(loop.stop)
            except Exception as e:
                petlog.warn(f"web_launcher: 停止事件循环异常: {e}")

        if _SERVER_THREAD and _SERVER_THREAD.is_alive():
            _SERVER_THREAD.join(timeout=timeout)

        _SERVER_STARTED = False
        _LOOP = None
        _RUNNER = None
        _SITE = None
        _SERVER_THREAD = None

        # 验证端口是否释放
        time.sleep(0.15)
        stopped = not is_server_listening(host, port)
        if stopped:
            petlog.log("web_launcher: NotebookLM Web 服务已成功停止并释放端口。")
        else:
            petlog.warn("web_launcher: Web 服务停止后端口仍处于占用状态。")
        return stopped


def open_notebook_lm(course: str = None, filename: str = None, host: str = "127.0.0.1", port: int = 5050, brain=None, kb=None) -> str:
    """确保 Web 服务运行，并在默认浏览器中打开 NotebookLM 研读工作台。

    Args:
        course: 可选，聚焦研读的课程名称
        filename: 可选，聚焦打开的课件文件名
        host: 服务地址
        port: 服务端口
        brain: 可选，注入主程序 AmiyaBrain 实例
        kb: 可选，注入主程序 KnowledgeBase 实例

    Returns:
        打开的网页 URL
    """
    host = local_host(host)
    if not ensure_server_running(host, port, brain=brain, kb=kb):
        raise RuntimeError("网页工作台启动失败：端口可能被其他程序占用")

    params = {}
    if course and str(course).strip() and course != "__ALL__":
        params["course"] = str(course).strip()
    if filename and str(filename).strip():
        params["file"] = str(filename).strip()
    params["_t"] = int(time.time())

    with _SERVER_LOCK:
        if _ACCESS is None or _SERVER_ADDRESS != (host, port):
            raise RuntimeError("网页工作台已停止，请重试")
        url = _ACCESS.launch_url(host, port, params)

    try:
        webbrowser.open(url)
    except Exception as e:
        petlog.warn(f"web_launcher: 无法自动打开系统浏览器: {e}")

    return url
