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
