"""NotebookLM Web 版调试服务：独立运行的 Google NotebookLM 课件学研后台。

启动方式：
    python run_web.py
    或在浏览器访问 http://localhost:5050
"""

import asyncio
import concurrent.futures
from contextlib import ExitStack
import json
import mimetypes
import os
import re
import sys
import tempfile
import webbrowser
from urllib.parse import quote

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from aiohttp import web

# 确保能加载项目根目录下的 pet 模块
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from pet.knowledge import KnowledgeBase
from pet.knowledge_paths import InvalidKnowledgePath, course_name, safe_child, validate_name
from pet.ai import AmiyaBrain


from pet.settings import config_dir


def _find_default_char_dir():
    candidates = [
        # 1. onedir 打包态：exe 旁边的 characters/amiya
        os.path.join(os.path.dirname(sys.executable), "characters", "amiya"),
        # 2. 源码根目录
        os.path.join(ROOT_DIR, "characters", "amiya"),
        # 3. 用户数据目录：%APPDATA%\AmiyaPet\characters\amiya
        os.path.join(config_dir(), "characters", "amiya"),
        # 4. PyInstaller _MEIPASS
        os.path.join(getattr(sys, "_MEIPASS", ""), "characters", "amiya"),
        # 5. CWD
        os.path.join(os.getcwd(), "characters", "amiya"),
    ]
    for c in candidates:
        if c and os.path.isdir(c) and os.path.isfile(os.path.join(c, "ai_config.json")):
            return c
    for c in candidates:
        if c and os.path.isdir(c) and os.path.isfile(os.path.join(c, "config.json")):
            return c
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    return os.path.join(ROOT_DIR, "characters", "amiya")


char_dir = _find_default_char_dir()
kb = KnowledgeBase()
brain = AmiyaBrain(char_dir)
brain.knowledge = kb


def set_app_context(app_brain=None, app_kb=None):
    """从主程序注入桌宠共享的阿米娅大脑与知识库实例。"""
    global brain, kb
    if app_kb is not None:
        kb = app_kb
    if app_brain is not None:
        brain = app_brain
        if kb is not None:
            brain.knowledge = kb

if getattr(sys, "frozen", False):
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    STATIC_DIR = os.path.join(base_dir, "web", "static")
    if not os.path.isdir(STATIC_DIR):
        STATIC_DIR = os.path.join(os.path.dirname(sys.executable), "web", "static")
else:
    STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


async def handle_index(request):
    """返回 NotebookLM 主页面（禁止浏览器缓存，确保热更与公式解析即刻生效）。"""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.isfile(index_path):
        return web.Response(text="index.html not found", status=404)
    response = web.FileResponse(index_path)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def get_all_courses():
    """整合知识库目录、知识切片索引和课表中的所有已知课程。"""
    c_set = set(kb.get_courses())
    if os.path.isdir(kb.courses_dir):
        for d in os.listdir(kb.courses_dir):
            try:
                path = kb.course_directory(d)
            except InvalidKnowledgePath:
                continue
            if os.path.isdir(path):
                c_set.add(d)

    try:
        from pet.schedule import Schedule
        sched = Schedule()
        for c in sched.courses:
            name = getattr(c, "name", "")
            if name and str(name).strip() and not str(name).lower().endswith(".pdf"):
                c_set.add(str(name).strip())
    except Exception:
        pass

    all_files = kb.get_course_files("__ALL__")
    res = []
    for c in sorted(list(c_set)):
        cnt = sum(1 for f in all_files if f.get("course") == c)
        res.append({
            "name": c,
            "files_count": cnt
        })
    return res


async def handle_stats(request):
    """获取知识库总体统计数据与全量课程列表。"""
    stats = kb.get_stats()
    course_items = get_all_courses()
    stats["courses"] = course_items
    stats["course_count"] = len(course_items)
    return web.json_response(stats)


async def handle_courses(request):
    """获取系统中的所有可用课程列表。"""
    return web.json_response(get_all_courses())


async def handle_create_course(request):
    """在知识库中创建新课程分类。"""
    data = await request.json()
    name = course_name(data.get("name", ""))
    if not name:
        return web.json_response({"success": False, "error": "课程名称不能为空"}, status=400)

    safe_name = name
    cdir = kb.course_directory(name)
    os.makedirs(cdir, exist_ok=True)
    kb.reload()
    return web.json_response({"success": True, "course": safe_name})


async def handle_delete_course(request):
    """从知识库中移除课程分类及其目录。"""
    data = await request.json()
    name = course_name(data.get("name", ""))
    if not name:
        return web.json_response({"success": False, "error": "无效的课程名称"}, status=400)

    import shutil
    safe_name = name
    cdir = kb.course_directory(name)
    # Resolve both targets before deleting either directory.
    digests_cdir = safe_child(kb.folder, "digests", name)
    if os.path.isdir(cdir):
        try:
            shutil.rmtree(cdir)
        except Exception as e:
            return web.json_response({"success": False, "error": f"删除课程目录失败: {e}"}, status=500)

    if os.path.isdir(digests_cdir):
        try:
            shutil.rmtree(digests_cdir)
        except Exception:
            pass

    kb.reload()
    return web.json_response({"success": True, "course": safe_name})


async def handle_move_file(request):
    """更改课件归属的课程（移动课件及对应考纲）。"""
    data = await request.json()
    filename = data.get("filename", "")
    old_course = data.get("source_course") or data.get("old_course") or ""
    new_course = data.get("target_course") or data.get("new_course") or ""

    if not filename:
        return web.json_response({"success": False, "error": "缺少文件名"}, status=400)

    import shutil
    new_c_safe = course_name(new_course)
    new_dir = kb.course_directory(new_c_safe)
    dst_file = kb.document_path(filename, new_c_safe)
    src_file, old_c_safe = kb.find_file(filename, old_course)
    if not src_file:
        return web.json_response({"success": False, "error": f"源文件未找到: {filename}"}, status=404)

    old_digest_path = kb.get_digest_path(filename, old_c_safe)
    new_digest_path = kb.get_digest_path(filename, new_c_safe)
    if os.path.abspath(src_file) != os.path.abspath(dst_file):
        if os.path.exists(dst_file) or os.path.exists(new_digest_path):
            return web.json_response({"success": False, "error": "目标课程已有同名课件或考纲"}, status=409)
        os.makedirs(new_dir, exist_ok=True)
        shutil.move(src_file, dst_file)
    if os.path.isfile(old_digest_path) and os.path.abspath(old_digest_path) != os.path.abspath(new_digest_path):
        os.makedirs(os.path.dirname(new_digest_path), exist_ok=True)
        try:
            shutil.move(old_digest_path, new_digest_path)
        except Exception:
            pass

    kb.reload()
    return web.json_response({"success": True, "filename": filename, "course": new_c_safe})


async def handle_files(request):
    """获取课件列表，支持按课程过滤。"""
    course = request.query.get("course")
    if course in ("__ALL__", "", None):
        course_filter = None
    elif course == "__GLOBAL__":
        course_filter = "__GLOBAL__"
    else:
        course_filter = course

    files = kb.get_course_files(course_filter)
    for f in files:
        sz = f.get("size", 0)
        sz_kb = sz / 1024
        f["size_str"] = f"{sz_kb/1024:.1f} MB" if sz_kb >= 1024 else f"{sz_kb:.0f} KB"
        f["has_digest"] = kb.has_digest(f["filename"], f.get("course"))
    return web.json_response(files)


def find_file_path(filename, course=None):
    """安全解析指定课件原件在知识库中的绝对路径。"""
    validate_name(filename)
    if not filename.lower().endswith(kb.SUPPORTED_EXTS):
        raise InvalidKnowledgePath("仅支持读取或打开知识库课件格式")
    return kb.find_file(filename, course)[0]


async def handle_raw_file(request):
    """直接按原始 MIME 类型返回课件文件（支持浏览器原生嵌入渲染 PDF、图片与纯文本）。"""
    filename = request.query.get("filename", "").strip()
    course = request.query.get("course", "").strip()
    if not filename:
        return web.Response(text="缺少文件名", status=400)

    file_path = find_file_path(filename, course)
    if not file_path or not os.path.isfile(file_path):
        return web.Response(text="课件原件未找到", status=404)

    ext = os.path.splitext(filename)[1].lower()
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        if ext in (".md", ".markdown"):
            content_type = "text/markdown; charset=utf-8"
        elif ext in (".txt", ".log", ".csv", ".json"):
            content_type = "text/plain; charset=utf-8"
        elif ext == ".pdf":
            content_type = "application/pdf"
        elif ext == ".pptx":
            content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        elif ext == ".docx":
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            content_type = "application/octet-stream"

    response = web.FileResponse(file_path)
    response.content_type = content_type
    encoded_fn = quote(filename)
    response.headers["Content-Disposition"] = f"inline; filename*=UTF-8''{encoded_fn}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


async def handle_file_content(request):
    """获取课件原件解析详情（文本提取、幻灯片切片、元数据等）。"""
    filename = request.query.get("filename", "").strip()
    course = request.query.get("course", "").strip()
    if not filename:
        return web.json_response({"success": False, "error": "缺少文件名"}, status=400)

    file_path = find_file_path(filename, course)
    if not file_path or not os.path.isfile(file_path):
        return web.json_response({"success": False, "error": "课件原件未找到"}, status=404)

    ext = os.path.splitext(filename)[1].lower()
    sz = os.path.getsize(file_path)

    # 提取文本与 PPT 幻灯片分页
    slides = []
    text_content = ""
    try:
        from pet.knowledge import _do_extract_text_from_file
        text_content = _do_extract_text_from_file(file_path)
    except Exception as e:
        text_content = f"提取文本失败: {e}"

    if ext in (".pptx", ".ppt"):
        pages = re.split(r"(?:=== 第 \d+ 页 ===|--- Slide \d+ ---|\[Slide \d+\])", text_content)
        slide_idx = 1
        for p in pages:
            clean_p = p.strip()
            if clean_p:
                slides.append({
                    "slide_num": slide_idx,
                    "content": clean_p
                })
                slide_idx += 1

    return web.json_response({
        "success": True,
        "filename": filename,
        "course": course,
        "ext": ext,
        "size": sz,
        "size_str": f"{sz/(1024*1024):.1f} MB" if sz >= 1024*1024 else f"{sz/1024:.0f} KB",
        "raw_url": f"/api/files/raw?filename={quote(filename)}&course={quote(course or '')}",
        "text_content": text_content,
        "slides": slides,
    })


async def handle_open_external(request):
    """在宿主机上用系统关联的本地软件（如 WPS、Office、Acrobat）直接打开该课件原件。"""
    data = await request.json()
    filename = str(data.get("filename", "")).strip()
    course = str(data.get("course", "")).strip()
    file_path = find_file_path(filename, course)
    if not file_path or not os.path.isfile(file_path):
        return web.json_response({"success": False, "error": "课件原件未找到"}, status=404)

    try:
        os.startfile(file_path)
        return web.json_response({"success": True})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_get_digest(request):
    """获取指定课件的 Markdown 核心考纲。"""
    filename = request.query.get("filename", "")
    course = request.query.get("course", "")
    content = kb.get_digest(filename, course) if kb.has_digest(filename, course) else ""
    return web.json_response({
        "filename": filename,
        "course": course,
        "content": content,
        "has_digest": bool(content and content.strip())
    })


async def handle_save_digest(request):
    """保存/编辑考纲内容。"""
    data = await request.json()
    filename = data.get("filename", "")
    course = data.get("course", "")
    content = data.get("content", "")
    kb.save_digest(filename, course, content)
    return web.json_response({"success": True})


async def handle_delete_file(request):
    """从知识库移除课件。"""
    data = await request.json()
    filename = data.get("filename", "")
    course = data.get("course", "")
    kb.delete_file(filename, course=course)
    return web.json_response({"success": True})


async def handle_upload(request):
    """接收浏览器拖拽或上传的课件并导入知识库（字段顺序无关，精确绑定指定课程）。"""
    reader = await request.multipart()
    course = None
    uploaded_files = []
    # Clean up staged uploads even when later multipart fields are invalid.
    with ExitStack() as staging:
        while True:
            part = await reader.next()
            if part is None:
                break
            if part.name == "course":
                course = course_name(await part.text())
            elif part.name == "file":
                saved_filename = validate_name(part.filename or "uploaded_file")
                temp_dir = staging.enter_context(tempfile.TemporaryDirectory(prefix="amiya_up_"))
                temp_path = safe_child(temp_dir, saved_filename)
                with open(temp_path, "wb") as f:
                    while True:
                        chunk = await part.read_chunk()
                        if not chunk:
                            break
                        f.write(chunk)
                uploaded_files.append((temp_path, saved_filename))

        # Validate every destination before importing the first file.
        kb.course_directory(course)
        for _, filename in uploaded_files:
            kb.document_path(filename, course)

        def do_import_all():
            names = []
            for idx, (temp_path, original_filename) in enumerate(uploaded_files):
                is_last = (idx == len(uploaded_files) - 1)
                ok, count, c_name = kb.import_file(temp_path, course=course, reload_index=is_last)
                if ok:
                    names.append(original_filename)
            return names

        loop = asyncio.get_running_loop()
        import_task = loop.run_in_executor(None, do_import_all)
        try:
            imported_names = await asyncio.shield(import_task)
        except asyncio.CancelledError:
            # The worker still uses the staging files after client disconnect.
            await import_task
            raise

    return web.json_response({
        "success": True,
        "filenames": imported_names,
        "course": course or ""
    })


async def handle_save_note(request):
    """将 AI 问答或学术心得保存为 Markdown 笔记并沉淀至知识库，自动建立切片索引。"""
    try:
        data = await request.json()
        title = str(data.get("title") or "").strip()
        content = str(data.get("content") or "").strip()
        course = str(data.get("course") or "").strip()
        append = bool(data.get("append", False))

        if not content:
            return web.json_response({"success": False, "error": "笔记内容不能为空"}, status=400)

        import datetime
        import re

        if not title:
            now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            title = f"问答笔记_{now_str}"

        safe_title = validate_name(title)
        if not safe_title.lower().endswith(".md"):
            safe_title += ".md"

        safe_course = course_name(course)
        dest_dir = kb.course_directory(safe_course)
        target_path = kb.document_path(safe_title, safe_course)

        os.makedirs(dest_dir, exist_ok=True)

        if append and os.path.isfile(target_path):
            with open(target_path, "a", encoding="utf-8") as f:
                f.write(f"\n\n---\n\n{content}")
        else:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)

        # 重新加载知识库并切片索引
        kb.reload()

        return web.json_response({
            "success": True,
            "filename": safe_title,
            "course": safe_course,
            "path": target_path
        })
    except InvalidKnowledgePath:
        raise
    except Exception as e:
        return web.json_response({"success": False, "error": f"保存笔记失败: {e}"}, status=500)


async def handle_chat(request):
    """真流式向助教提问并返回 RAG 解答（首字秒开，彻底解决大题生成超时问题）。"""
    data = await request.json()
    question = (data.get("question") or "").strip()
    filename = (data.get("filename") or "").strip()
    course = (data.get("course") or "").strip()

    if not question:
        return web.Response(text="博士，请输入您想提问或探讨的问题。", content_type="text/plain; charset=utf-8")

    # 1. 组装针对当前课件/科目的 RAG 权威上下文
    rag_context = ""
    if filename:
        # 优先读取已提炼的考纲结构
        if kb.has_digest(filename, course):
            digest_text = kb.get_digest(filename, course)
            if len(digest_text) > 8000:
                digest_text = digest_text[:8000] + "\n...(考纲篇幅较长，已截取前核心部分)"
            rag_context += f"【课件《{filename}》核心考纲提炼】：\n{digest_text}\n\n"

        # 补充检索该课件最相关的切片
        chunks = kb.retrieve(question, top_k=4, course=course)
        file_chunks = [c for c in chunks if c.get("source") == filename]
        if not file_chunks:
            file_chunks = chunks[:3]
        if file_chunks:
            rag_context += "【课件相关段落摘录】：\n"
            for c in file_chunks:
                rag_context += f"- {c.get('text', '')}\n"
    elif course and course not in ("__ALL__", "__GLOBAL__"):
        chunks = kb.retrieve(question, top_k=4, course=course)
        if chunks:
            rag_context += f"【课程《{course}》相关资料】：\n"
            for c in chunks:
                rag_context += f"- 《{c.get('source', '')}》: {c.get('text', '')}\n"
    else:
        chunks = kb.retrieve(question, top_k=3)
        if chunks:
            rag_context += "【知识库参考资料】：\n"
            for c in chunks:
                rag_context += f"- 《{c.get('source', '')}》: {c.get('text', '')}\n"

    system_content = (
        "你是《明日方舟》中的阿米娅，在此担任博士的大学课程专属研读助教。\n"
        "你温柔、严谨、富有责任心，称呼对方为「博士」，自称「阿米娅」。\n"
        "请结合参考资料与学术专业知识，为博士提供详尽、准确、结构分明的学业解答。\n"
        "要求：\n"
        "1. 使用清晰的 Markdown 排版（标题、加粗、代码块、列表、表格）。\n"
        "2. 【高保真 LaTeX 公式】：数学、物理、理科与工程计算公式必须规范使用标准 LaTeX 格式排版（行内公式用 $公式$，独立行大公式用 $$公式$$），严禁使用粗糙 ASCII 字符拼凑公式，确保矢量符号(\\vec)、微积分、积分号与希腊字母优雅美观。\n"
        "3. 若博士要求出模拟题/自测题：给出高质量期末真题级别题目，并附带分步骤深度解析与标准采分点答案。\n"
        "4. 保持学术严谨与亲切鼓励的语气。"
    )
    if rag_context:
        system_content += f"\n\n权威参考资料：\n{rag_context}"

    msgs = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": question}
    ]

    response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )
    await response.prepare(request)

    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()

    def on_token(delta_str):
        if delta_str:
            loop.call_soon_threadsafe(queue.put_nowait, delta_str)

    def do_stream():
        try:
            last_len = 0
            def on_accum(full_text):
                nonlocal last_len
                delta = full_text[last_len:]
                if delta:
                    last_len = len(full_text)
                    on_token(delta)

            msg = brain._post_stream(msgs, use_tools=False, on_delta=on_accum)
            if last_len == 0:
                content = (msg.get("content") or "").strip() if isinstance(msg, dict) else str(msg or "").strip()
                if content:
                    on_token(content)
        except Exception as e:
            from pet.ai import diagnose_network_error
            target_url = brain.cfg.get("base_url") if brain.has_custom_key else (brain.cfg.get("public_relay_url") or "")
            err_msg = diagnose_network_error(e, url=target_url, has_custom_key=brain.has_custom_key)
            on_token(f"\n\n{err_msg}")
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    stream_future = loop.run_in_executor(None, do_stream)

    while True:
        chunk = await queue.get()
        if chunk is None:
            break
        await response.write(chunk.encode("utf-8"))

    await stream_future
    await response.write_eof()
    return response


async def handle_generate_digest(request):
    """调用大模型深度提炼核心考纲。"""
    data = await request.json()
    filename = data.get("filename", "")
    course = data.get("course", "")

    fp, course = kb.find_file(filename, course)
    if not fp:
        return web.json_response({"success": False, "error": f"源文件未找到: {filename}"}, status=404)

    # 1. 优先直接复用已扫描切片，避免重复 OCR 与解析开销（毫秒级提取）
    existing_chunks = [c["text"] for c in kb.chunks
                       if c.get("source") == filename and c.get("course", "") == course]
    loop = asyncio.get_event_loop()
    if existing_chunks:
        raw_text = "\n\n".join(existing_chunks)
    else:
        from pet import knowledge
        raw_text = await loop.run_in_executor(None, lambda: knowledge.extract_text_from_file(fp))

    if not raw_text or not raw_text.strip():
        return web.json_response({"success": False, "error": "未能从文件中提取出有效文本（课件可能为空或不支持）"}, status=400)

    def do_generate():
        return brain.generate_courseware_digest(raw_text, filename=filename, course=course)

    try:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            digest_text = await loop.run_in_executor(pool, do_generate)
            kb.save_digest(filename, course, digest_text)
            return web.json_response({"success": True, "digest": digest_text})
    except Exception as e:
        from pet import logging as petlog
        from pet.ai import diagnose_network_error
        petlog.warn(f"web: AI 考纲生成失败: {e}")
        target_url = brain.cfg.get("base_url") if brain.has_custom_key else (brain.cfg.get("public_relay_url") or "")
        err_msg = diagnose_network_error(e, url=target_url, has_custom_key=brain.has_custom_key)
        return web.json_response({"success": False, "error": f"考纲提炼失败: {err_msg}"}, status=500)


@web.middleware
async def knowledge_path_errors(request, handler):
    try:
        return await handler(request)
    except InvalidKnowledgePath as exc:
        return web.json_response({"success": False, "error": str(exc)}, status=400)


def make_app():
    # 限制放宽至 1024MB (1GB)，彻底消除大课件上传时的 413 Request Entity Too Large 错误
    app = web.Application(client_max_size=1024 * 1024 * 1024,
                          middlewares=[knowledge_path_errors])
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/stats", handle_stats)
    app.router.add_get("/api/files", handle_files)
    app.router.add_get("/api/courses", handle_courses)
    app.router.add_post("/api/courses/create", handle_create_course)
    app.router.add_post("/api/courses/delete", handle_delete_course)
    app.router.add_post("/api/files/move", handle_move_file)
    app.router.add_get("/api/digest", handle_get_digest)
    app.router.add_post("/api/digest/save", handle_save_digest)
    app.router.add_post("/api/digest/generate", handle_generate_digest)
    app.router.add_post("/api/chat", handle_chat)
    app.router.add_post("/api/upload", handle_upload)
    app.router.add_post("/api/files/delete", handle_delete_file)
    app.router.add_post("/api/notes/save", handle_save_note)
    app.router.add_get("/api/files/raw", handle_raw_file)
    app.router.add_get("/api/files/content", handle_file_content)
    app.router.add_post("/api/files/open_external", handle_open_external)

    if os.path.isdir(STATIC_DIR):
        app.router.add_static("/static/", STATIC_DIR)

    return app


def run(host="127.0.0.1", port=5050, open_browser=True):
    app = make_app()
    url = f"http://{host}:{port}"
    print("\n========================================================")
    print(f"[*] Google NotebookLM Web 调试工作台已启动！")
    print(f"[*] 访问地址: {url}")
    print(f"[*] 可在网页中实时调试字号、主题配色、三栏比例与考纲排版")
    print("========================================================\n")
    if open_browser:
        webbrowser.open(url)
    web.run_app(app, host=host, port=port)


if __name__ == "__main__":
    run()
