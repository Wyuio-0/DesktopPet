"""Knowledge base tests: chunking, multi-format parsing, courseware RAG, retrieval, context injection."""
import io
import os
import zipfile
import pytest

from pet.knowledge import (
    KnowledgeBase,
    _segment,
    _tokenize,
    extract_text_from_file,
    match_course_for_file,
    match_course_from_query,
)
from pet import actions


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def _create_dummy_docx(path, text):
    """创建合法的轻量 .docx 测试文档。"""
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>%s</w:t></w:r></w:p></w:body></w:document>'
    ) % text
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", xml)


def _create_dummy_pptx(path, slides_text):
    """创建合法的轻量 .pptx 测试幻灯片。"""
    with zipfile.ZipFile(path, "w") as z:
        for idx, t in enumerate(slides_text, 1):
            xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
                '<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>%s</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>'
            ) % t
            z.writestr(f"ppt/slides/slide{idx}.xml", xml)


class TestKnowledgeBase:
    def test_load_and_retrieve(self, tmp_path):
        _write(tmp_path, "笔记.txt",
               "二叉树是一种数据结构。\n\n树的遍历有三种：先序、中序、后序。\n\n"
               "排序算法有快速排序。")
        kb = KnowledgeBase(folder=str(tmp_path))
        assert len(kb) == 3
        hits = kb.retrieve("树的遍历", top_k=1)
        assert hits and "遍历" in hits[0]["text"]
        assert hits[0]["source"] == "笔记.txt"

    def test_empty_folder(self, tmp_path):
        kb = KnowledgeBase(folder=str(tmp_path))
        assert len(kb) == 0 and not kb

    def test_context_marks_source(self, tmp_path):
        _write(tmp_path, "a.md", "线性代数：矩阵乘法。")
        kb = KnowledgeBase(folder=str(tmp_path))
        ctx = kb.context("矩阵乘法")
        assert "【a.md】" in ctx and "矩阵乘法" in ctx

    def test_context_empty_when_no_match(self, tmp_path):
        _write(tmp_path, "a.md", "线性代数：矩阵乘法。")
        kb = KnowledgeBase(folder=str(tmp_path))
        assert kb.context("量子力学") == ""

    def test_reload_picks_up_new_files(self, tmp_path):
        kb = KnowledgeBase(folder=str(tmp_path))
        assert len(kb) == 0
        _write(tmp_path, "x.txt", "操作系统：进程调度。")
        kb.reload()
        assert len(kb) == 1

    def test_long_paragraph_segmented(self, tmp_path):
        long_text = "第一句。" * 200   # > max_len(500)
        _write(tmp_path, "long.txt", long_text)
        kb = KnowledgeBase(folder=str(tmp_path))
        assert len(kb) >= 2


class TestHelpers:
    def test_tokenize_cjk_and_english(self):
        toks = _tokenize("Binary tree 二叉树")
        assert "binary" in toks and "tree" in toks and "二" in toks

    def test_tokenize_bigrams(self):
        toks = _tokenize("傅里叶变换")
        assert "傅里" in toks and "里叶" in toks and "变换" in toks

    def test_segment_splits_paragraphs(self):
        chunks = _segment("第一段。\n\n第二段。")
        assert len(chunks) == 2


class TestTfidfRetrieval:
    def test_bigram_beats_unrelated(self, tmp_path):
        """n-gram TF-IDF：主题相关的片段应排在最前。"""
        _write(tmp_path, "a.txt",
               "傅里叶变换把时域信号变换到频域分析。\n\n"
               "快速傅里叶变换 FFT 是数字信号处理的基石。\n\n"
               "今天天气很好适合去操场跑步。")
        kb = KnowledgeBase(folder=str(tmp_path), use_embed=False)
        hits = kb.retrieve("FFT 快速傅里叶", top_k=1)
        assert hits and "FFT" in hits[0]["text"]

    def test_query_terms_absent_return_empty(self, tmp_path):
        _write(tmp_path, "a.md", "线性代数：矩阵乘法。")
        kb = KnowledgeBase(folder=str(tmp_path), use_embed=False)
        assert kb.retrieve("量子力学纠缠") == []

    def test_embed_unavailable_falls_back(self, tmp_path):
        """没有 sentence-transformers 时 use_embed=True 也正常走词频。"""
        _write(tmp_path, "n.txt", "操作系统：进程调度与死锁。")
        kb = KnowledgeBase(folder=str(tmp_path), use_embed=True)
        assert kb._emb_matrix is None          # 未安装 -> 无向量矩阵
        hits = kb.retrieve("进程调度", top_k=1)
        assert hits and "调度" in hits[0]["text"]


class TestCoursewareMultiFormatParsing:
    def test_docx_parsing(self, tmp_path):
        docx_file = tmp_path / "操作系统_实验指导.docx"
        _create_dummy_docx(str(docx_file), "虚拟存储器管理与页面置换算法")
        text = extract_text_from_file(str(docx_file))
        assert "页面置换算法" in text

    def test_pptx_parsing(self, tmp_path):
        pptx_file = tmp_path / "第4章_热力学.pptx"
        _create_dummy_pptx(str(pptx_file), ["热力学第一定律与能量守恒", "卡诺循环与理想气体状态方程"])
        text = extract_text_from_file(str(pptx_file))
        assert "热力学第一定律" in text
        assert "卡诺循环" in text


class TestCourseMatching:
    def test_match_course_for_file_abbreviations(self):
        courses = ["大学物理", "高等数学", "计算机网络", "操作系统"]
        assert match_course_for_file("大物期末复习重点.pptx", courses) == "大学物理"
        assert match_course_for_file("高数第3章导数与微分.pdf", courses) == "高等数学"
        assert match_course_for_file("计网TCP三次握手.docx", courses) == "计算机网络"
        assert match_course_for_file("OS_死锁四个必要条件.md", courses) == "操作系统"

    def test_match_course_from_query(self):
        courses = ["大学物理", "高等数学", "操作系统"]
        assert match_course_from_query("请问大物的热力学第二定律怎么理解？", courses) == "大学物理"
        assert match_course_from_query("帮我出5道高数的期末简答题", courses) == "高等数学"
        assert match_course_from_query("操作系统中PV操作的具体解题步骤是什么？", courses) == "操作系统"


class TestCoursewarePartitioningAndManagement:
    def test_import_and_retrieve_by_course(self, tmp_path):
        kb_dir = tmp_path / "kb"
        src_dir = tmp_path / "downloads"
        src_dir.mkdir()
        kb = KnowledgeBase(folder=str(kb_dir))
        src_file = src_dir / "课件.pptx"
        _create_dummy_pptx(str(src_file), ["操作系统PV操作信号量机制", "死锁产生的四个必要条件"])

        ok, chunks, c_name = kb.import_file(str(src_file), course="操作系统")
        assert ok is True
        assert c_name == "操作系统"
        assert chunks >= 1

        stats = kb.get_stats()
        assert stats["course_count"] == 1
        assert "操作系统" in stats["courses"]

        # 指定课程精准检索
        hits = kb.retrieve("信号量机制", course="操作系统", top_k=1)
        assert hits and "信号量" in hits[0]["text"]
        assert hits[0]["course"] == "操作系统"

        # 上下文格式化
        ctx = kb.context("PV操作", course="操作系统")
        assert "【罗德岛学业资料库 · 《操作系统》课件参考】" in ctx
        assert "【课件.pptx】" in ctx

        # 删除文件测试
        assert kb.delete_file("课件.pptx", course="操作系统") is True
        assert len(kb) == 0


class TestCoursewareActions:
    def test_actions_courseware_query_and_list(self, tmp_path):
        kb_dir = tmp_path / "kb"
        src_dir = tmp_path / "downloads"
        src_dir.mkdir(exist_ok=True)
        kb = KnowledgeBase(folder=str(kb_dir))
        src_file = src_dir / "复习.docx"
        _create_dummy_docx(str(src_file), "麦克斯韦电磁方程组与电磁波理论")
        kb.import_file(str(src_file), course="大学物理")

        actions.set_knowledge_provider(lambda: kb)

        # list_courseware 测试
        listing = actions.list_courseware(course="大学物理")
        assert "复习.docx" in listing
        assert "大学物理" in listing

        # query_courseware 测试
        res = actions.query_courseware("麦克斯韦方程组", course="大学物理")
        assert "麦克斯韦" in res
        assert "大学物理" in res


class TestMenuIntegration:
    def test_menu_builder_has_upload_action(self):
        from pet.menu import PetContextMenuBuilder
        from PyQt5 import QtWidgets
        from unittest.mock import MagicMock

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        mock_window = MagicMock()
        mock_window.char.display_name = "阿米娅"
        mock_window.char.dir = "/dummy"
        mock_window.prefs = {}
        builder = PetContextMenuBuilder(mock_window)

        # 构建课程表子菜单：仅保留网页版统一入口，已移除桌面独立上传入口
        menu = QtWidgets.QMenu()
        builder.add_schedule_menu(menu)
        sub_actions = [a.text() for a in menu.actions()[0].menu().actions()]
        assert not any("导入课件" in t for t in sub_actions)
        assert any("课程知识库" in t for t in sub_actions)


class TestSlideAwareChunkingAndDigest:
    def test_slide_aware_chunking(self):
        text = (
            "=== 第 1 页 · 计算机网络体系结构 ===\n"
            "OSI七层模型包括物理层、数据链路层、网络层、传输层、会话层、表示层和应用层。\n\n"
            "=== 第 2 页 · TCP与UDP区别 ===\n"
            "TCP是面向连接的可靠传输协议，UDP是无连接的尽最大努力交付协议。"
        )
        chunks = _segment(text)
        assert len(chunks) == 2
        assert "第 1 页" in chunks[0] and "OSI七层模型" in chunks[0]
        assert "第 2 页" in chunks[1] and "TCP是面向连接" in chunks[1]

    def test_slide_aware_chunking_long_slide_retains_header(self):
        long_body = "可靠传输滑动窗口协议实现流量控制与拥塞控制。" * 30
        text = f"=== 第 3 页 · 滑动窗口 ===\n{long_body}"
        chunks = _segment(text, max_len=200)
        assert len(chunks) > 1
        for ch in chunks:
            assert "【第 3 页 · 滑动窗口】" in ch

    def test_digest_lifecycle_in_kb(self, tmp_path):
        kb_dir = tmp_path / "kb"
        src_dir = tmp_path / "downloads"
        src_dir.mkdir(exist_ok=True)
        kb = KnowledgeBase(folder=str(kb_dir))

        src_file = src_dir / "课件.pptx"
        _create_dummy_pptx(str(src_file), ["计算机操作系统PV操作", "死锁产生的原因"])
        kb.import_file(str(src_file), course="OS")

        fn = "课件.pptx"
        course = "OS"
        assert not kb.has_digest(fn, course)
        assert kb.get_digest(fn, course) == ""

        mock_digest = (
            "# 《课件.pptx》核心考点提炼\n\n"
            "## 1. 核心概念与必背定义\n"
            "- **PV操作**：P操作申请资源，V操作释放资源。\n\n"
            "## 2. 期末常考题型与解题套路\n"
            "- 生产者-消费者问题与哲学家就餐问题经典伪代码模板。"
        )

        ok = kb.save_digest(fn, course, mock_digest)
        assert ok is True
        assert kb.has_digest(fn, course) is True
        assert "PV操作" in kb.get_digest(fn, course)

        # 检查是否作为考点提炼切片被索引到 RAG 中
        hits = kb.retrieve("生产者 消费者 哲学家", course="OS", top_k=1)
        assert hits and hits[0]["is_digest"] is True
        assert "考点提炼" in hits[0]["source"]

        # 检查文件删除时是否连带清理 digest
        assert kb.delete_file(fn, course=course) is True
        assert not kb.has_digest(fn, course)

    def test_generate_courseware_digest(self, tmp_path):
        from pet.ai import AmiyaBrain
        from unittest.mock import MagicMock

        brain = AmiyaBrain(str(tmp_path), persona="dummy")
        brain._post_stream = MagicMock(side_effect=RuntimeError("stream disabled in unit test"))
        brain._post = MagicMock(return_value="## 1. 核心概念\n- 死锁\n## 💡 五、 期末高分冲刺自测 Q&A\n> Q1: 题目")

        raw_slides = "=== 第 1 页 · 死锁 ===\n死锁的定义与必要条件"
        digest = brain.generate_courseware_digest(raw_slides, filename="ch3.pptx", course="操作系统")
        assert "死锁" in digest
        brain._post.assert_called_once()
        call_msgs = brain._post.call_args[0][0]
        assert any("ch3.pptx" in m["content"] for m in call_msgs if m["role"] == "user")
        assert any("操作系统" in m["content"] for m in call_msgs if m["role"] == "user")

    def test_generate_courseware_digest_stream(self, tmp_path):
        from pet.ai import AmiyaBrain
        from unittest.mock import MagicMock

        brain = AmiyaBrain(str(tmp_path), persona="dummy")
        brain._post_stream = MagicMock(return_value={"content": "## 1. 核心概念\n- 死锁\n## 💡 五、 期末高分冲刺自测 Q&A\n> Q1: 题目", "finish_reason": "stop"})

        raw_slides = "=== 第 1 页 · 死锁 ===\n死锁的定义与必要条件"
        digest = brain.generate_courseware_digest(raw_slides, filename="ch3.pptx", course="操作系统")
        assert "死锁" in digest
        brain._post_stream.assert_called_once()

    def test_courseware_summary_dialog(self, tmp_path):
        from pet.schedule_dialogs import CoursewareSummaryDialog
        from PyQt5 import QtWidgets

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        kb_dir = tmp_path / "kb"
        kb = KnowledgeBase(folder=str(kb_dir))
        kb.save_digest("test.pdf", "微积分", "## 核心概念\n- 极限与导数")

        dlg = CoursewareSummaryDialog(
            filename="test.pdf",
            course="微积分",
            file_path=str(tmp_path / "test.pdf"),
            kb=kb,
            brain=None
        )
        assert dlg.filename == "test.pdf"
        assert "极限与导数" in dlg._current_text
        dlg.close()

    def test_empty_or_failed_file_still_in_files_meta(self, tmp_path):
        """修复上传课件因解析为空而不显示的 Bug：确保即使文本提取为空，课件仍在 files_meta 中。"""
        kb_dir = tmp_path / "kb"
        kb = KnowledgeBase(folder=str(kb_dir))

        # 构造一个无文本内容的空白 pptx / docx
        empty_ppt = kb_dir / "courses" / "信号处理" / "空白课件.pptx"
        empty_ppt.parent.mkdir(parents=True, exist_ok=True)
        empty_ppt.write_bytes(b"PK\x05\x06" + b"\x00" * 18)  # minimal empty zip header

        kb.reload()
        files = kb.get_course_files("信号处理")
        assert len(files) == 1
        assert files[0]["filename"] == "空白课件.pptx"
        assert files[0]["chunks"] == 0

    def test_extract_ppt_legacy(self, tmp_path):
        """测试从二进制 .ppt 模拟文件中提取 UTF-16LE 文本。"""
        from pet.knowledge import _extract_ppt_legacy
        ppt_file = tmp_path / "legacy.ppt"
        payload = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # OLE header prefix
        text_utf16 = "数字信号处理与滤波器设计".encode("utf-16le")
        ppt_file.write_bytes(payload + b"\x00" * 20 + text_utf16 + b"\x00" * 20)

        extracted = _extract_ppt_legacy(str(ppt_file))
        assert "数字信号处理" in extracted

    def test_global_and_all_course_files(self, tmp_path):
        kb_dir = tmp_path / "kb"
        kb = KnowledgeBase(folder=str(kb_dir))
        
        # 课程课件
        c_file = kb_dir / "courses" / "操作系统" / "ch1.txt"
        c_file.parent.mkdir(parents=True, exist_ok=True)
        c_file.write_text("操作系统概述", encoding="utf-8")

        # 通用课件（根目录）
        g_file = kb_dir / "general_handout.txt"
        g_file.write_text("公共英语四级核心词汇", encoding="utf-8")

        kb.reload()
        all_f = kb.get_course_files("__ALL__")
        assert len(all_f) == 2

        global_f = kb.get_course_files("__GLOBAL__")
        assert len(global_f) == 1
        assert global_f[0]["filename"] == "general_handout.txt"

        os_f = kb.get_course_files("操作系统")
        assert len(os_f) == 1
        assert os_f[0]["filename"] == "ch1.txt"

    def test_digest_generate_thread_progress(self, tmp_path):
        from pet.schedule_dialogs import DigestGenerateThread
        from pet.ai import AmiyaBrain
        from unittest.mock import MagicMock

        txt_file = tmp_path / "test.txt"
        txt_file.write_text("=== 第 1 页 ===\n线性代数行列式计算与特征值", encoding="utf-8")

        brain = AmiyaBrain(str(tmp_path), persona="dummy")
        brain.generate_courseware_digest = MagicMock(return_value="## 核心考点\n- 特征值")

        thread = DigestGenerateThread(brain, str(txt_file), "test.txt", "高数")
        progresses = []
        thread.sig_progress.connect(lambda pct, msg: progresses.append((pct, msg)))

        thread.run()
        assert len(progresses) >= 3
        assert any(p[0] == 10 for p in progresses)
        assert any(p[0] == 25 for p in progresses)
        assert any(p[0] == 98 for p in progresses)

    def test_info_panel_active_task_progressbar(self, tmp_path):
        from pet.info_panel import InfoPanel
        from PyQt5 import QtWidgets, QtCore
        from unittest.mock import MagicMock

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

        kb_dir = tmp_path / "kb"
        kb = KnowledgeBase(folder=str(kb_dir))
        c_file = kb_dir / "courses" / "微积分" / "ch1.txt"
        c_file.parent.mkdir(parents=True, exist_ok=True)
        c_file.write_text("导数定义与连续性", encoding="utf-8")
        kb.reload()

        class MockOwner(QtCore.QObject):
            sig_digest_progress = QtCore.pyqtSignal(str, str, int, str)
            sig_digest_finished = QtCore.pyqtSignal(str, str, bool, str)

            def __init__(self):
                super().__init__()
                self.schedule = MagicMock()
                self.schedule.courses = []
                self.brain = MagicMock()
                self.brain.knowledge = kb
                self._active_digest_tasks = {
                    ("ch1.txt", "微积分"): {"progress": 45, "status": "正在生成考纲..."}
                }

        mock_owner = MockOwner()
        panel = InfoPanel(owner=mock_owner)
        panel.refresh_knowledge_page(select_course="微积分")
        assert hasattr(panel, "_btn_open_web")
        assert panel._btn_open_web is not None
        panel.close()

    def test_text_cache_path_location_independence(self, tmp_path):
        from pet.knowledge import _text_cache_path, extract_text_from_file
        import shutil

        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        f1 = dir1 / "lecture.txt"
        f1.write_text("Hello World! 恒定磁场与高斯定理", encoding="utf-8")

        f2 = dir2 / "lecture.txt"
        shutil.copy2(str(f1), str(f2))

        cp1 = _text_cache_path(str(f1))
        cp2 = _text_cache_path(str(f2))
        assert cp1 is not None and cp2 is not None
        assert cp1 == cp2, "Cache paths must match regardless of folder location"

        res1 = extract_text_from_file(str(f1))
        assert "恒定磁场" in res1
        # f2 should immediately hit the cache
        res2 = extract_text_from_file(str(f2))
        assert res2 == res1




