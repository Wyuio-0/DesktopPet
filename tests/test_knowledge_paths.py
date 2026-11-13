"""File APIs must not read, write, move, delete or launch outside the library."""

import asyncio
import os
import stat
import subprocess
from types import SimpleNamespace

import pytest

from pet.knowledge import KnowledgeBase
from pet.knowledge_paths import InvalidKnowledgePath, safe_child, validate_name


BAD_NAMES = [".", "..", "../secret.md", r"..\secret.md", "/secret.md",
             r"C:\secret.md", r"C:secret.md", r"\\server\share\secret.md",
             "file.md:stream", "file.md.", "file.md ", "NUL", "con.txt",
             "COM1.md", "LPT¹.txt", "bad\x00.md", "bad\n.md"]


@pytest.mark.parametrize("name", BAD_NAMES + [None, 123, ["file.md"]])
def test_reject_nonportable_names(name):
    with pytest.raises(InvalidKnowledgePath):
        validate_name(name)


def test_normal_names_and_course_markers(tmp_path):
    kb = KnowledgeBase(str(tmp_path / "library"), use_embed=False)
    source = tmp_path / "第 1 章.md"
    source.write_text("正常课件", encoding="utf-8")
    assert kb.import_file(str(source), course="高等数学（一）")[0]
    path, course = kb.find_file(source.name, "高等数学（一）")
    assert course == "高等数学（一）"
    assert os.path.isfile(path)
    assert kb.save_digest(source.name, course, "考纲")
    assert kb.get_digest(source.name, course) == "考纲"
    assert kb.delete_file(source.name, course)
    assert not os.path.exists(path)
    for marker in (None, "", "__GLOBAL__", "__ALL__"):
        assert kb.document_path("笔记.md", marker) == str(tmp_path / "library" / "笔记.md")


@pytest.mark.parametrize("operation", ["delete_file", "get_digest_path", "find_file", "document_path"])
@pytest.mark.parametrize("filename", ["../secret.md", "absolute"])
def test_model_methods_protect_outside_files(tmp_path, operation, filename):
    outside = tmp_path / "secret.md"
    outside.write_text("不能修改", encoding="utf-8")
    kb = KnowledgeBase(str(tmp_path / "library"), use_embed=False)
    name = str(outside) if filename == "absolute" else filename
    with pytest.raises(InvalidKnowledgePath):
        getattr(kb, operation)(name)
    assert outside.read_text(encoding="utf-8") == "不能修改"


def test_import_rejects_bad_destination(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("原文件", encoding="utf-8")
    kb = KnowledgeBase(str(tmp_path / "library"), use_embed=False)
    with pytest.raises(InvalidKnowledgePath):
        kb.import_file(str(source), course="..")
    assert not (tmp_path / "library" / source.name).exists()


def test_symlink_is_rejected(tmp_path):
    root = tmp_path / "library"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("私有文件", encoding="utf-8")
    link = root / "link.md"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"OS does not permit symlink creation: {exc}")
    with pytest.raises(InvalidKnowledgePath):
        safe_child(str(root), link.name)


@pytest.mark.skipif(os.name != "nt", reason="Windows directory junction")
def test_windows_junction_is_rejected(tmp_path):
    root = tmp_path / "library"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "courses"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
    if result.returncode:
        pytest.skip(f"OS does not permit junction creation: {result.stderr!r}")
    try:
        with pytest.raises(InvalidKnowledgePath):
            safe_child(str(root), "courses", "数学")
    finally:
        # Only remove this fixture's junction, never its target.
        link.rmdir()
    assert outside.is_dir()


def test_reparse_attribute_is_rejected_without_link_privileges(tmp_path, monkeypatch):
    child = str(tmp_path / "linked")
    original_lstat = os.lstat

    def lstat(path, *args, **kwargs):
        if str(path) == child:
            return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", lstat)
    with pytest.raises(InvalidKnowledgePath):
        safe_child(str(tmp_path), "linked", "file.md")


@pytest.fixture
def library_server(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    from web import server
    kb = KnowledgeBase(str(tmp_path / "library"), use_embed=False)
    monkeypatch.setattr(server, "kb", kb)
    outside = tmp_path / "secret.md"
    outside.write_text("外部文件不能改动", encoding="utf-8")
    (tmp_path / "library" / "keep.md").write_text("内部文件不能误删", encoding="utf-8")
    monkeypatch.setattr(server.os, "startfile", lambda _: pytest.fail("must not launch a file"), raising=False)
    return server, kb, outside


def request(server, method, route, **kwargs):
    from aiohttp import ClientTimeout
    from aiohttp.test_utils import TestClient, TestServer

    async def run():
        async with TestClient(TestServer(server.make_app()), timeout=ClientTimeout(total=10)) as client:
            async with client.request(method, route, **kwargs) as response:
                return response.status, await response.read()
    return asyncio.run(run())


@pytest.mark.parametrize("name", BAD_NAMES + ["_global", "_GLOBAL"])
@pytest.mark.parametrize("action", ["create", "delete"])
def test_course_api_rejects_invalid_names(library_server, name, action):
    server, kb, outside = library_server
    status, _ = request(server, "POST", f"/api/courses/{action}", json={"name": name})
    assert status == 400
    assert outside.exists()
    assert os.path.isfile(kb.document_path("keep.md"))


@pytest.mark.parametrize("route", ["/api/files/delete", "/api/files/move", "/api/files/open_external",
                                  "/api/digest/save", "/api/digest/generate", "/api/chat"])
@pytest.mark.parametrize("filename", ["../secret.md", "absolute", r"..\secret.md", "file.md:stream"])
def test_file_post_apis_reject_escape(library_server, route, filename):
    server, kb, outside = library_server
    name = str(outside) if filename == "absolute" else filename
    status, _ = request(server, "POST", route,
                        json={"filename": name, "question": "总结", "content": "覆盖"})
    assert status == 400
    assert outside.read_text(encoding="utf-8") == "外部文件不能改动"


@pytest.mark.parametrize("route", ["/api/files/raw", "/api/files/content", "/api/digest"])
def test_file_get_apis_reject_escape(library_server, route):
    server, kb, outside = library_server
    status, body = request(server, "GET", route, params={"filename": str(outside)})
    assert status == 400
    assert "外部文件不能改动".encode() not in body


@pytest.mark.parametrize("route,payload", [
    ("/api/files/move", {"filename": "keep.md", "target_course": ".."}),
    ("/api/files/move", {"filename": "keep.md", "source_course": ".."}),
    ("/api/files/delete", {"filename": "keep.md", "course": ".."}),
    ("/api/digest/save", {"filename": "keep.md", "course": "..", "content": "考纲"}),
    ("/api/notes/save", {"title": "../secret", "content": "笔记"}),
    ("/api/notes/save", {"title": "笔记", "content": "笔记", "course": ".."}),
])
def test_write_apis_validate_all_paths(library_server, route, payload):
    server, kb, outside = library_server
    status, _ = request(server, "POST", route, json=payload)
    assert status == 400
    assert os.path.isfile(kb.document_path("keep.md"))
    assert outside.read_text(encoding="utf-8") == "外部文件不能改动"


@pytest.mark.parametrize("filename", ["unsafe.exe", "unsafe.html"])
@pytest.mark.parametrize("route,method", [("/api/files/open_external", "POST"), ("/api/files/raw", "GET")])
def test_do_not_launch_or_serve_active_files(library_server, route, method, filename):
    server, kb, _ = library_server
    with open(kb.document_path(filename), "w", encoding="utf-8") as f:
        f.write("untrusted")
    kwargs = {"json" if method == "POST" else "params": {"filename": filename}}
    assert request(server, method, route, **kwargs)[0] == 400


def test_move_and_notes_normal_flow(library_server):
    server, kb, _ = library_server
    assert request(server, "POST", "/api/notes/save", json={
        "title": "第1章笔记", "course": "数学", "content": "原始笔记"})[0] == 200
    assert request(server, "POST", "/api/digest/save", json={
        "filename": "第1章笔记.md", "course": "数学", "content": "考纲"})[0] == 200
    assert request(server, "POST", "/api/files/move", json={
        "filename": "第1章笔记.md", "source_course": "数学", "target_course": "复习"})[0] == 200
    assert kb.find_file("第1章笔记.md", "复习")[1] == "复习"
    assert kb.get_digest("第1章笔记.md", "复习") == "考纲"
    assert request(server, "GET", "/api/files/raw", params={
        "filename": "第1章笔记.md", "course": "复习"}) == (200, "原始笔记".encode())
    assert request(server, "POST", "/api/courses/delete", json={"name": "复习"})[0] == 200
    assert not os.path.exists(kb.document_path("第1章笔记.md", "复习"))


@pytest.mark.parametrize("bad_field", ["filename", "course"])
def test_upload_rejects_invalid_fields_before_import(library_server, bad_field):
    from aiohttp import FormData
    server, kb, outside = library_server
    form = FormData(quote_fields=False)
    # Put course last to ensure staging a file cannot bypass destination checks.
    form.add_field("file", b"upload", filename="../secret.md" if bad_field == "filename" else "upload.md")
    form.add_field("course", ".." if bad_field == "course" else "数学")
    assert request(server, "POST", "/api/upload", data=form)[0] == 400
    assert outside.read_text(encoding="utf-8") == "外部文件不能改动"
    assert not os.path.exists(kb.document_path("upload.md", "数学"))


def test_upload_normal_flow(library_server):
    from aiohttp import FormData
    server, kb, _ = library_server
    form = FormData(quote_fields=False)
    form.add_field("file", "新课件".encode(), filename="lecture.md")
    form.add_field("course", "数学")
    assert request(server, "POST", "/api/upload", data=form)[0] == 200
    path = kb.document_path("lecture.md", "数学")
    with open(path, encoding="utf-8") as f:
        assert f.read() == "新课件"


def test_move_does_not_overwrite_another_course(library_server):
    server, kb, _ = library_server
    os.makedirs(kb.course_directory("数学"))
    dest = kb.document_path("keep.md", "数学")
    with open(dest, "w", encoding="utf-8") as f:
        f.write("已有课件")
    assert request(server, "POST", "/api/files/move", json={
        "filename": "keep.md", "target_course": "数学"})[0] == 409
    with open(dest, encoding="utf-8") as f:
        assert f.read() == "已有课件"
    assert os.path.isfile(kb.document_path("keep.md"))


@pytest.mark.skipif(os.name != "nt", reason="Windows directory junction")
def test_web_rejects_junction_course(library_server):
    server, kb, outside = library_server
    link = kb.course_directory("linked")
    result = subprocess.run(["cmd", "/c", "mklink", "/J", link, str(outside.parent)], capture_output=True)
    if result.returncode:
        pytest.skip(f"OS does not permit junction creation: {result.stderr!r}")
    try:
        assert request(server, "GET", "/api/files/raw", params={
            "filename": outside.name, "course": "linked"})[0] == 400
        assert request(server, "POST", "/api/courses/delete", json={"name": "linked"})[0] == 400
        assert request(server, "POST", "/api/notes/save", json={
            "title": "secret", "content": "不能覆盖", "course": "linked"})[0] == 400
        assert outside.read_text(encoding="utf-8") == "外部文件不能改动"
    finally:
        os.rmdir(link)
