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

_SERVER_STARTED = False
_SERVER_LOCK = threading.Lock()
_LOOP = None
_RUNNER = None
_SITE = None
_SERVER_THREAD = None


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


def ensure_server_running(host: str = "127.0.0.1", port: int = 5050, brain=None, kb=None) -> bool:
    """确保 NotebookLM 后台 Web 服务正在运行（线程内免依赖托管）。"""
    global _SERVER_STARTED, _SERVER_THREAD
    if is_server_listening(host, port):
        if brain or kb:
            try:
                import web.server as ws
                ws.set_app_context(brain, kb)
            except Exception:
                pass
        _SERVER_STARTED = True
        return True

    with _SERVER_LOCK:
        if is_server_listening(host, port):
            if brain or kb:
                try:
                    import web.server as ws
                    ws.set_app_context(brain, kb)
                except Exception:
                    pass
            _SERVER_STARTED = True
            return True

        def _run_server():
            global _LOOP, _RUNNER, _SITE
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                _LOOP = loop

                from aiohttp import web
                from web.server import make_app, set_app_context

                if brain or kb:
                    set_app_context(brain, kb)

                app = make_app()
                runner = web.AppRunner(app)
                loop.run_until_complete(runner.setup())
                _RUNNER = runner

                site = web.TCPSite(runner, host, port)
                loop.run_until_complete(site.start())
                _SITE = site

                petlog.log(f"web_launcher: NotebookLM Web 服务已就绪 -> http://{host}:{port}")
                loop.run_forever()
            except Exception as e:
                petlog.warn(f"web_launcher: 后台启动 NotebookLM 服务失败: {e}")
            finally:
                _LOOP = None
                _RUNNER = None
                _SITE = None

        server_thread = threading.Thread(
            target=_run_server,
            name="NotebookLMWebDaemon",
            daemon=True
        )
        _SERVER_THREAD = server_thread
        server_thread.start()

        # 等待服务端口就绪（最多 2 秒）
        for _ in range(20):
            time.sleep(0.1)
            if is_server_listening(host, port):
                _SERVER_STARTED = True
                return True

        return False


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
                    loop.stop()

                f = asyncio.run_coroutine_threadsafe(_shutdown(), loop)
                try:
                    f.result(timeout=timeout)
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
    ensure_server_running(host, port, brain=brain, kb=kb)

    params = {}
    if course and str(course).strip() and course != "__ALL__":
        params["course"] = str(course).strip()
    if filename and str(filename).strip():
        params["file"] = str(filename).strip()
    params["_t"] = int(time.time())

    query = urllib.parse.urlencode(params)
    url = f"http://{host}:{port}/?{query}"

    try:
        webbrowser.open(url)
    except Exception as e:
        petlog.warn(f"web_launcher: 无法自动打开系统浏览器: {e}")

    return url
