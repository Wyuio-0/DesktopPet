"""NotebookLM Web Launcher 与启停控制单元测试。"""

import time
import pytest
from pet import web_launcher


@pytest.fixture(autouse=True)
def isolated_knowledge(tmp_path, monkeypatch):
    """Web API tests must never write to the user's default knowledge folder."""
    # Earlier UI tests may start the process-wide service on its default port.
    # Close that owned instance before testing a different port.
    web_launcher.stop_server()
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    from pet.knowledge import KnowledgeBase
    from web import server
    monkeypatch.setattr(server, "kb", KnowledgeBase(str(tmp_path / "knowledge"), use_embed=False))
    try:
        yield
    finally:
        web_launcher.stop_server()


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
    from aiohttp import CookieJar
    from aiohttp.test_utils import TestClient, TestServer
    from web.server import make_app
    from web.security import ACCESS_KEY

    async def _run():
        app = make_app()
        server = TestServer(app)
        async with TestClient(server, cookie_jar=CookieJar(unsafe=True)) as client:
            client.session.headers["Origin"] = str(client.make_url("/")).rstrip("/")
            url = app[ACCESS_KEY].launch_url("127.0.0.1", client.port)
            res = await client.post("/auth/session", json={"token": url.split("#token=")[1]})
            assert res.status == 200
            # 1. 验证课程统计结构
            res = await client.get("/api/stats")
            data = await res.json()
            assert "courses" in data
            assert isinstance(data["courses"], list)

            # 2. 验证创建课程接口
            res = await client.post("/api/courses/create", json={"name": "测试自动化科目"})
            c_data = await res.json()
            assert c_data.get("success") is True

            # 3. 验证课程统计包含新创建的课程
            res = await client.get("/api/stats")
            data = await res.json()
            course_names = [c["name"] for c in data.get("courses", [])]
            assert "测试自动化科目" in course_names

            # 4. 验证课程文件筛选
            res = await client.get("/api/files?course=测试自动化科目")
            files = await res.json()
            assert isinstance(files, list)

            # 5. 验证保存 AI 问答笔记沉淀到本地知识库接口
            note_payload = {
                "title": "问答笔记_自动化测试知识点",
                "content": "# 测试问答\n\n## 问\n什么是回归测试？\n\n## 答\n回归测试是软件测试的一种。",
                "course": "测试自动化科目",
                "append": False
            }
            res = await client.post("/api/notes/save", json=note_payload)
            n_data = await res.json()
            assert n_data.get("success") is True
            assert n_data.get("filename") == "问答笔记_自动化测试知识点.md"

            # 6. 验证新保存的笔记已存在于该课程的知识库课件列表中
            res = await client.get("/api/files?course=测试自动化科目")
            updated_files = await res.json()
            file_names = [f["filename"] for f in updated_files]
            assert "问答笔记_自动化测试知识点.md" in file_names

            # 7. 验证课件原件原格式流式读取接口 (/api/files/raw)
            res = await client.get("/api/files/raw?filename=问答笔记_自动化测试知识点.md&course=测试自动化科目")
            assert res.status == 200
            assert "text/markdown" in res.headers.get("Content-Type", "")
            raw_text = await res.text()
            assert "什么是回归测试？" in raw_text

            # 8. 验证课件原件详情解析接口 (/api/files/content)
            res = await client.get("/api/files/content?filename=问答笔记_自动化测试知识点.md&course=测试自动化科目")
            assert res.status == 200
            c_info = await res.json()
            assert c_info.get("success") is True
            assert c_info.get("ext") == ".md"
            assert "回归测试" in c_info.get("text_content", "")

            # 9. 清理测试课程分类及测试文件
            await client.post("/api/courses/delete", json={"name": "测试自动化科目"})

    asyncio.run(_run())

