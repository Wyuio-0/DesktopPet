"""NotebookLM Web Launcher 与启停控制单元测试。"""

import time
from pet import web_launcher


def test_web_launcher_lifecycle():
    test_port = 5058
    assert not web_launcher.is_server_listening(port=test_port)

    # 1. 启动
    started = web_launcher.ensure_server_running(port=test_port)
    assert started
    assert web_launcher.is_server_listening(port=test_port)
    assert web_launcher.is_running(port=test_port)

    # 2. 幂等再次启动
    again = web_launcher.ensure_server_running(port=test_port)
    assert again

    # 3. 停止并验证端口释放
    stopped = web_launcher.stop_server(port=test_port)
    assert stopped
    assert not web_launcher.is_server_listening(port=test_port)
    assert not web_launcher.is_running(port=test_port)


def test_web_courses_and_upload_api():
    import asyncio
    from aiohttp.test_utils import TestClient, TestServer
    from web.server import make_app

    async def _run():
        app = make_app()
        client = TestClient(TestServer(app))
        await client.start_server()

        # 1. 验证课程统计包含全部课表课程
        res = await client.get("/api/stats")
        data = await res.json()
        assert "courses" in data
        assert len(data["courses"]) >= 9

        # 2. 验证创建课程接口
        res = await client.post("/api/courses/create", json={"name": "测试自动化科目"})
        c_data = await res.json()
        assert c_data.get("success") is True

        # 3. 验证课程文件筛选
        res = await client.get("/api/files?course=测试自动化科目")
        files = await res.json()
        assert isinstance(files, list)

        await client.close()

    asyncio.run(_run())

