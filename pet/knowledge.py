"""讲义/课件多模态知识库：切块 + 检索 + 课程关联（默认零依赖，支持本地语义模型）。

支持的文件格式：
- `.pptx` / `.ppt`: 幻灯片讲义提取（优先 python-pptx，内置 zip+xml 零依赖回退）
- `.pdf`: 教材/考纲/课件（优先 PyMuPDF / fitz，内置流提取回退）
- `.docx` / `.doc`: 实验指导书/考纲（优先 python-docx，内置 zip+xml 零依赖回退）
- `.txt` / `.md`: 笔记与讲义文本
- 图片文件（.png / .jpg）: 截图与黑板板书（通过 pet.ocr 离线 OCR 提取）

知识库结构：
%APPDATA%\\AmiyaPet\\knowledge\\
    ├── courses\\                # 课程子文件夹
    │   ├── 操作系统\\
    │   │   ├── 第3章_内存管理.pptx
    │   │   └── 期末考纲.pdf
    │   ├── 大学物理\\
    │   │   └── 热力学基础.pdf
    ├── 通用笔记.md              # 未分配特定课程的全局讲义

检索后端（KnowledgeBase(use_embed=...) 控制）：
1. **词频升级版（默认，零依赖）**：n-gram（中文单字+双字、英文词）TF-IDF +
   余弦相似度排序——支持按指定课程过滤或根据问题自动识别关联课程。
2. **本地语义检索（可选）**：检测到 `sentence-transformers` 时自动使用多语言 embedding 模型。
"""

import importlib
import math
import os
import re
import shutil
import time
import zipfile
import xml.etree.ElementTree as ET

from . import logging as petlog
from .settings import config_dir

# 多语言 embedding 模型（中英皆可；约 470MB，首次使用时下载并缓存）。
_EMBED_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

_MODEL = None            # 缓存的 SentenceTransformer 实例

# 常见大学课程简称与全称映射
_COURSE_ABBRS = {
    "高数": "高等数学",
    "微积分": "高等数学",
    "数分": "数学分析",
    "高代": "高等代数",
    "大物": "大学物理",
    "普物": "普通物理学",
    "线代": "线性代数",
    "计网": "计算机网络",
    "网络": "计算机网络",
    "计组": "计算机组成原理",
    "操作系统": "操作系统",
    "os": "操作系统",
    "数据结构": "数据结构与算法",
    "算法": "算法设计与分析",
    "软工": "软件工程",
    "离散": "离散数学",
    "马原": "马克思主义基本原理",
    "毛概": "毛泽东思想和中国特色社会主义理论体系概论",
    "思修": "思想道德与法治",
    "近纲": "中国近现代史纲要",
    "军理": "军事理论",
    "数电": "数字电子技术",
    "模电": "模拟电子技术",
    "电工": "电工电子学",
    "电路": "电路原理",
    "信号": "信号与系统",
    "信统": "信号与系统",
    "通原": "通信原理",
    "自控": "自动控制原理",
    "工图": "工程制图",
    "机设": "机械设计基础",
}


def _embed_available():
    """sentence-transformers + torch 是否可导入（守卫式，exe 里恒为 False）。"""
    try:
        importlib.import_module("sentence_" + "transformers")
        importlib.import_module("torch")
        return True
    except Exception:
        return False


def _embed_model():
    global _MODEL
    if _MODEL is None:
        st = importlib.import_module("sentence_" + "transformers")
        _MODEL = st.SentenceTransformer(_EMBED_MODEL_NAME)
    return _MODEL


def _encode_texts(texts):
    import numpy as np
    model = _embed_model()
    vecs = model.encode(texts, convert_to_numpy=True,
                        normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(vecs, dtype=np.float32)


def _encode_query(query):
    return _encode_texts([query])[0]


# ── 文档解析与文本提取 ─────────────────────────────────────────────────────────

def _extract_ppt_legacy(path):
    """从传统二进制 .ppt (OLE2) 文件中提取幻灯片文本。"""
    texts = []
    try:
        with open(path, "rb") as f:
            data = f.read()

        # 1. 匹配 UTF-16LE 连续中英文字符块
        utf16_pattern = re.compile(rb'(?:[\x20-\x7e]\x00|[\x00-\xff][\x4e-\x9f]|[\x00-\xff][\x30-\x39]){3,}')
        for m in utf16_pattern.finditer(data):
            try:
                s = m.group(0).decode("utf-16le", errors="ignore").strip()
                if len(s) >= 3 and any('\u4e00' <= c <= '\u9fa5' or c.isalnum() for c in s):
                    if not s.startswith(("_", "PowerPoint", "Current User", "Document")):
                        texts.append(s)
            except Exception:
                pass

        # 2. 匹配 ASCII 连续文本块 (长度 >= 4)
        ascii_pattern = re.compile(rb'[\x20-\x7e\n\r\t]{5,}')
        for m in ascii_pattern.finditer(data):
            try:
                s = m.group(0).decode("ascii", errors="ignore").strip()
                if len(s) >= 4 and any(c.isalnum() for c in s):
                    if not any(noise in s for noise in ["Font", "Arial", "Times New", "PowerPoint", "Microsoft"]):
                        texts.append(s)
            except Exception:
                pass
    except Exception:
        pass

    seen = set()
    cleaned = []
    for t in texts:
        t = t.strip()
        if t and t not in seen and len(t) >= 2:
            seen.add(t)
            cleaned.append(t)
    return "\n\n".join(cleaned)


def _text_cache_path(path):
    """计算课件文本的本地缓存文件路径（按文件名+大小+首尾采样哈希，实现跨目录/拷贝复用的内容寻址缓存）。"""
    try:
        stat = os.stat(path)
        import hashlib
        h = hashlib.md5(f"{os.path.basename(path)}_{stat.st_size}".encode("utf-8"))
        with open(path, "rb") as f:
            h.update(f.read(65536))
            if stat.st_size > 65536:
                f.seek(max(0, stat.st_size - 65536))
                h.update(f.read(65536))
        digest_hex = h.hexdigest()
        safe_name = re.sub(r'[\/\\:\*\?"<>\|]', "_", os.path.basename(path))[:30]
        cdir = os.path.join(config_dir(), "knowledge", ".cache")
        os.makedirs(cdir, exist_ok=True)
        return os.path.join(cdir, f"{safe_name}_{digest_hex}.txt")
    except OSError:
        return None


def _extract_pptx_images_fallback(path, max_slides=20):
    """当 PPTX 没有文本框或仅包含全页背景图时（例如 Marp/全图导出），直接从 PPTX 的 zip 结构提取幻灯片对应图片执行 OCR。"""
    import zipfile
    import xml.etree.ElementTree as ET
    from . import ocr
    texts = []
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            slide_files = [n for n in names if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
            def get_num(fn):
                m = re.search(r"\d+", os.path.basename(fn))
                return int(m.group(0)) if m else 0
            slide_files = sorted(slide_files, key=get_num)
            total = len(slide_files)
            if not total:
                return ""

            # 步长自适应：前3页(大纲/目录) + 末尾总结页 + 中间均匀平铺，抽取最多 max_slides 页
            if total <= max_slides:
                sampled = slide_files
            else:
                step = max(1, (total - 5) // max(1, (max_slides - 5)))
                middle = slide_files[3:-2:step]
                selected_set = set(slide_files[:3] + middle + slide_files[-2:])
                sampled = [s for s in slide_files if s in selected_set][:max_slides]

            petlog.log(f"knowledge: 纯图片 PPT 幻灯片，启动快速离线 OCR 提取 ({len(sampled)}/{total} 页)...")

            for sfile in sampled:
                page_num = get_num(sfile)
                base = os.path.basename(sfile)
                rel_file = f"ppt/slides/_rels/{base}.rels"
                img_rel_path = None
                if rel_file in names:
                    try:
                        rel_tree = ET.fromstring(z.read(rel_file))
                        for rel in rel_tree.iter():
                            if rel.tag.endswith("Relationship") and "image" in rel.attrib.get("Type", ""):
                                img_rel_path = rel.attrib.get("Target", "")
                                break
                    except Exception:
                        pass
                if not img_rel_path:
                    # 备选：直接按 Marp 常见命名查找媒体图片
                    cand = f"ppt/media/Slide-{page_num}-image-1.png"
                    if cand in names:
                        img_rel_path = f"../media/Slide-{page_num}-image-1.png"
                if img_rel_path:
                    norm_path = os.path.normpath(os.path.join("ppt/slides", img_rel_path)).replace("\\", "/")
                    if norm_path in names:
                        try:
                            img_bytes = z.read(norm_path)
                            txt = ocr.recognize(img_bytes)
                            if txt and txt.strip():
                                texts.append(f"=== 第 {page_num} 页 ===\n" + txt.strip())
                        except Exception as e:
                            petlog.warn(f"knowledge: 第 {page_num} 页 OCR 异常: {e}")
    except Exception as e:
        petlog.warn(f"knowledge: _extract_pptx_images_fallback 异常: {e}")
    return "\n\n".join(texts)


def _do_extract_text_from_file(path):
    """从 PPTX, PDF, DOCX, TXT, MD 等多种格式文件中提取全文纯文本（内部实现）。"""
    if not os.path.isfile(path):
        return ""

    ext = os.path.splitext(path)[1].lower()

    # 1. 文本文件
    if ext in (".txt", ".md", ".json", ".csv", ".log"):
        for enc in ("utf-8", "gbk", "gb18030", "utf-16"):
            try:
                with open(path, "r", encoding=enc) as f:
                    return f.read()
            except (UnicodeDecodeError, OSError):
                continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except OSError:
            return ""

    # 2. DOCX 文件 (优先使用 python-docx，失败回退纯标准库 zip+xml 解析)
    if ext == ".docx":
        try:
            import docx
            doc = docx.Document(path)
            lines = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    row_txt = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
                    if row_txt:
                        lines.append(row_txt)
            if lines:
                return "\n".join(lines)
        except Exception:
            pass

        # 零依赖回退：解压读取 word/document.xml
        try:
            with zipfile.ZipFile(path) as z:
                if "word/document.xml" in z.namelist():
                    xml_content = z.read("word/document.xml")
                    tree = ET.fromstring(xml_content)
                    texts = [n.text for n in tree.iter() if n.tag.endswith("}t") and n.text]
                    return "".join(texts)
        except Exception:
            pass
        return ""


    # 3. PPTX 与 PPT 演示文稿文件
    if ext == ".ppt":
        return _extract_ppt_legacy(path)

    if ext == ".pptx":
        try:
            import pptx
            prs = pptx.Presentation(path)
            slide_texts = []
            ocr_count = 0
            MAX_OCR_PAGES = 30  # 纯图片 PPT/PDF 幻灯片 OCR 数量上限，防卡死
            for idx, slide in enumerate(prs.slides, 1):
                cur_slide = []
                title_text = ""
                # 尝试提取幻灯片自带的主标题
                try:
                    title_shape = getattr(slide.shapes, "title", None)
                    if title_shape and title_shape.has_text_frame:
                        title_text = title_shape.text_frame.text.strip()
                except Exception:
                    pass

                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for p in shape.text_frame.paragraphs:
                            t = p.text.strip()
                            if t and t != title_text:
                                cur_slide.append(t)
                    elif getattr(shape, "has_table", False):
                        try:
                            for row in shape.table.rows:
                                for cell in row.cells:
                                    ct = cell.text.strip()
                                    if ct:
                                        cur_slide.append(ct)
                        except Exception:
                            pass
                    elif hasattr(shape, "image") and shape.image:
                        # 纯图片 PPT 幻灯片兜底：若当前页没有文字框，自动对图片运行 OCR 提取
                        if not cur_slide and not title_text and ocr_count < MAX_OCR_PAGES:
                            try:
                                from . import ocr
                                ocr_res = ocr.recognize(shape.image.blob)
                                if ocr_res and ocr_res.strip():
                                    cur_slide.append(ocr_res.strip())
                                    ocr_count += 1
                            except Exception:
                                pass
                header = f"=== 第 {idx} 页" + (f" · {title_text}" if title_text else "") + " ==="
                body = "\n".join(cur_slide)
                if body or title_text:
                    slide_texts.append(f"{header}\n{body}".strip())
            if slide_texts:
                return "\n\n".join(slide_texts)
        except Exception:
            pass

        # 零依赖回退：解压读取 ppt/slides/slide*.xml
        try:
            with zipfile.ZipFile(path) as z:
                slide_files = sorted([n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")])
                res = []
                for idx, sfile in enumerate(slide_files, 1):
                    xml_data = z.read(sfile)
                    tree = ET.fromstring(xml_data)
                    texts = [n.text for n in tree.iter() if n.tag.endswith("}t") and n.text]
                    if texts:
                        res.append(f"=== 第 {idx} 页 ===\n" + "\n".join(texts))
                if res:
                    return "\n\n".join(res)
        except Exception:
            pass

        # 终极兜底：针对全页背景图/Marp 导出的 PPTX，执行背景图片 OCR 提取
        bg_ocr_text = _extract_pptx_images_fallback(path)
        if bg_ocr_text and bg_ocr_text.strip():
            return bg_ocr_text.strip()

        return ""

    # 4. PDF 文件 (优先使用 PyMuPDF / fitz，保留页面编号与边界；图片扫描页支持 OCR 兜底)
    if ext == ".pdf":
        try:
            try:
                import pymupdf as fitz
            except ImportError:
                import fitz
            doc = fitz.open(path)
            pages = []
            ocr_count = 0
            MAX_OCR_PAGES = 30  # 避免百页纯扫描教材无限制 OCR 导致长时间占用 CPU
            for i in range(len(doc)):
                page = doc[i]
                txt = page.get_text()
                if txt and txt.strip():
                    pages.append(f"--- 第 {i+1} 页 ---\n" + txt.strip())
                elif ocr_count < MAX_OCR_PAGES:
                    # 本页无矢量文字（纯图片/扫描件），自动调用 OCR 渲染提取
                    try:
                        from . import ocr
                        pix = page.get_pixmap(dpi=150)
                        img_bytes = pix.tobytes("png")
                        ocr_txt = ocr.recognize(img_bytes)
                        if ocr_txt and ocr_txt.strip():
                            pages.append(f"--- 第 {i+1} 页 (OCR) ---\n" + ocr_txt.strip())
                            ocr_count += 1
                    except Exception:
                        pass
            doc.close()
            if pages:
                return "\n\n".join(pages)
        except Exception:
            pass

        # 回退：尝试 pypdf
        try:
            import pypdf
            reader = pypdf.PdfReader(path)
            pages = []
            for i, p in enumerate(reader.pages):
                txt = p.extract_text()
                if txt and txt.strip():
                    pages.append(f"--- 第 {i+1} 页 ---\n" + txt.strip())
            if pages:
                return "\n\n".join(pages)
        except Exception:
            pass
        return ""

    # 5. 图片文件（讲义截图/板书照片）
    if ext in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
        try:
            from . import ocr
            res = ocr.recognize(path)
            if res and isinstance(res, str) and res.strip():
                return res.strip()
        except Exception:
            pass

    return ""


def extract_text_from_file(path):
    """从 PPTX, PDF, DOCX, TXT, MD 等多种格式文件中提取全文纯文本（带本地磁盘缓存加速）。"""
    if not os.path.isfile(path):
        return ""

    cp = _text_cache_path(path)
    if cp and os.path.isfile(cp):
        try:
            with open(cp, "r", encoding="utf-8") as f:
                cached = f.read()
            if cached and cached.strip():
                return cached
        except OSError:
            pass

    text = _do_extract_text_from_file(path)
    if text and text.strip() and cp:
        try:
            with open(cp, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError:
            pass
    return text


def match_course_for_file(filename, course_names, active_course=None):
    """根据文件名智能推测所属课程名称。
    支持全称包含、简称匹配（如「大物」->「大学物理」）或当前活跃课程兜底。
    """
    if not filename:
        return active_course

    base = os.path.splitext(os.path.basename(filename))[0].lower()
    cleaned = re.sub(r"[_\-\s\(\)\[\]（）【】0-9]+", "", base)

    # 1. 课程全名子串精准包含
    for name in course_names:
        if not name:
            continue
        n_low = name.lower()
        if n_low in base or n_low in cleaned:
            return name
        # 反向：如果课程名称包含文件名关键字
        if len(cleaned) >= 2 and cleaned in n_low:
            return name

    # 2. 经典缩写词匹配
    for abbr, full in _COURSE_ABBRS.items():
        if abbr in base or abbr in cleaned:
            for name in course_names:
                if full in name or name in full or abbr in name:
                    return name
            return full

    # 3. 若正在上课或今日有活跃课程，作为推荐候选
    return active_course


def match_course_from_query(query, course_names):
    """从用户提问中解析出可能涉及的课程名称。"""
    if not query:
        return None
    q = query.lower()
    for name in course_names:
        if name and (name.lower() in q or re.sub(r"[0-9\(\)（）]", "", name).lower() in q):
            return name
    for abbr, full in _COURSE_ABBRS.items():
        if abbr in q:
            for name in course_names:
                if full in name or abbr in name:
                    return name
            return full
    return None


# ── 知识库核心 ─────────────────────────────────────────────────────────────────

class KnowledgeBase:
    """讲义与课件知识库：支持按课程分类管理、多格式解析、切块与精确检索。"""

    SUPPORTED_EXTS = (".pptx", ".ppt", ".pdf", ".docx", ".doc", ".txt", ".md", ".png", ".jpg", ".jpeg")

    def __init__(self, folder=None, use_embed=True):
        self.folder = folder or os.path.join(config_dir(), "knowledge")
        self.courses_dir = os.path.join(self.folder, "courses")
        self.use_embed = bool(use_embed)
        self.chunks = []            # [{"text", "source", "course", "path"}]
        self.files_meta = []        # [{"filename", "course", "size", "chunks", "mtime", "path"}]
        self._docs = []             # 每块的 token 列表（TF-IDF 用）
        self._idf = {}
        self._doc_weights = []      # [(token->tfidf 权重 dict, 模长)]
        self._emb_matrix = None     # (N, D) 归一化向量；embedding 可用时非空
        self.reload()

    def reload(self):
        """重新扫描知识库目录及其下所有 courses/<课程名> 文件夹并建立索引。"""
        self.chunks = []
        self.files_meta = []
        os.makedirs(self.folder, exist_ok=True)
        os.makedirs(self.courses_dir, exist_ok=True)

        # 1. 扫描根目录下的全局文档 (course="")
        self._scan_directory(self.folder, course="")

        # 2. 扫描 courses 子目录下的各个课程文件夹
        if os.path.isdir(self.courses_dir):
            for cname in sorted(os.listdir(self.courses_dir)):
                cdir = os.path.join(self.courses_dir, cname)
                if os.path.isdir(cdir):
                    self._scan_directory(cdir, course=cname)

        self._build_index()

    def _scan_directory(self, dpath, course=""):
        """扫描单个文件夹中的课件文件并分块切片。"""
        try:
            files = sorted(os.listdir(dpath))
        except OSError:
            return

        for fn in files:
            if not fn.lower().endswith(self.SUPPORTED_EXTS):
                continue
            path = os.path.join(dpath, fn)
            if not os.path.isfile(path):
                continue

            try:
                stat = os.stat(path)
                size = stat.st_size
                mtime = stat.st_mtime
            except OSError:
                size, mtime = 0, 0

            doc_chunks = []
            raw_text = extract_text_from_file(path)
            if raw_text and raw_text.strip():
                for seg in _segment(raw_text):
                    seg = seg.strip()
                    if seg:
                        c_obj = {
                            "text": seg,
                            "source": fn,
                            "course": course or "",
                            "path": path
                        }
                        self.chunks.append(c_obj)
                        doc_chunks.append(c_obj)

            # 若已生成 AI 核心考点纲要，作为高权重知识切片一并收录
            has_digest = self.has_digest(fn, course)
            if has_digest:
                digest_text = self.get_digest(fn, course)
                if digest_text:
                    for d_seg in _segment_digest(digest_text):
                        d_obj = {
                            "text": d_seg,
                            "source": f"{fn} (考点提炼)",
                            "course": course or "",
                            "path": path,
                            "is_digest": True,
                        }
                        self.chunks.append(d_obj)
                        doc_chunks.append(d_obj)

            self.files_meta.append({
                "filename": fn,
                "course": course or "",
                "size": size,
                "chunks": len(doc_chunks),
                "mtime": mtime,
                "path": path,
                "has_digest": has_digest,
            })

    def get_digest_path(self, filename, course=None):
        """获取指定课件的知识点考纲 Markdown 存储路径。"""
        safe_course = re.sub(r'[\/\\:\*\?"<>\|]', "_", str(course).strip()) if course and str(course).strip() else "_global"
        safe_fn = re.sub(r'[\/\\:\*\?"<>\|]', "_", filename)
        d_dir = os.path.join(self.folder, "digests", safe_course)
        os.makedirs(d_dir, exist_ok=True)
        return os.path.join(d_dir, f"{safe_fn}.md")

    def has_digest(self, filename, course=None):
        """检查指定课件是否已经提炼过 AI 知识点与考纲。"""
        return os.path.isfile(self.get_digest_path(filename, course))

    def get_digest(self, filename, course=None):
        """读取指定课件提炼出的核心知识点与考纲 Markdown 全文。若未生成或读取失败返回空字符串。"""
        p = self.get_digest_path(filename, course)
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return f.read()
            except OSError:
                return ""
        return ""

    def save_digest(self, filename, course, content):
        """持久化保存 AI 提炼出的考纲，并重载知识切片索引。"""
        p = self.get_digest_path(filename, course)
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            self.reload()
            return True
        except OSError as e:
            petlog.warn(f"knowledge: 保存知识考点大纲失败 {p}: {e}")
            return False

    def _build_index(self):
        """重建 TF-IDF 索引；embedding 可用时额外编码向量矩阵。"""
        self._docs = [_tokenize(c["text"]) for c in self.chunks]
        n = len(self._docs)
        df = {}
        for toks in self._docs:
            for t in set(toks):
                df[t] = df.get(t, 0) + 1
        self._idf = {t: math.log((n + 1) / (c + 1)) + 1
                     for t, c in df.items()}
        self._doc_weights = []
        for toks in self._docs:
            tf = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            w = {t: (1 + math.log(tf[t])) * self._idf[t] for t in tf}
            norm = math.sqrt(sum(v * v for v in w.values())) or 1.0
            self._doc_weights.append((w, norm))

        self._emb_matrix = None
        if self.use_embed and n and _embed_available():
            try:
                self._emb_matrix = _encode_texts([c["text"] for c in self.chunks])
                petlog.log("knowledge: 本地语义检索已启用（%d 片段）" % n)
            except Exception:
                self._emb_matrix = None
                petlog.log("knowledge: 语义模型加载失败，回退词频检索")

    def __bool__(self):
        return bool(self.chunks)

    def __len__(self):
        return len(self.chunks)

    # ── 知识库管理与导入操作 ───────────────────────────────────────────────────

    def import_file(self, src_path, course=None, copy=True, reload_index=True):
        """将外部课件导入知识库，并与指定课程关联绑定。
        返回: (bool 成功与否, int 生成切片数, str 课程名称)
        """
        if not os.path.isfile(src_path):
            return False, 0, ""

        fn = os.path.basename(src_path)
        if course and str(course).strip():
            course_clean = re.sub(r'[\/\\:\*\?"<>\|]', "_", str(course).strip())
            dest_dir = os.path.join(self.courses_dir, course_clean)
        else:
            course_clean = ""
            dest_dir = self.folder

        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, fn)

        if copy and os.path.abspath(src_path) != os.path.abspath(dest_path):
            shutil.copy2(src_path, dest_path)

        if reload_index:
            self.reload()

        # 统计刚导入文件的切片数
        chunks_count = sum(1 for c in self.chunks if c.get("source") == fn and c.get("course") == course_clean)
        return True, chunks_count, course_clean

    def delete_file(self, filename, course=None):
        """从知识库及磁盘中移除指定文件并刷新索引。"""
        deleted = False
        if course and str(course).strip():
            course_clean = re.sub(r'[\/\\:\*\?"<>\|]', "_", str(course).strip())
            path = os.path.join(self.courses_dir, course_clean, filename)
            if os.path.isfile(path):
                os.remove(path)
                deleted = True
        else:
            path = os.path.join(self.folder, filename)
            if os.path.isfile(path):
                os.remove(path)
                deleted = True

        if deleted:
            d_path = self.get_digest_path(filename, course)
            if os.path.isfile(d_path):
                try:
                    os.remove(d_path)
                except OSError:
                    pass
            self.reload()
        return deleted

    def get_courses(self):
        """返回当前知识库中已收录的所有课程列表。"""
        cs = set(m["course"] for m in self.files_meta if m.get("course"))
        return sorted(list(cs))

    def get_course_files(self, course=None):
        """获取指定课程（或全部/通用）的课件文件列表。"""
        if course is None or course == "__ALL__":
            return list(self.files_meta)
        if course == "__GLOBAL__":
            return [m for m in self.files_meta if not m.get("course")]
        return [m for m in self.files_meta if m.get("course") == course]

    def get_stats(self):
        """获取知识库全景统计信息。"""
        courses = self.get_courses()
        return {
            "course_count": len(courses),
            "file_count": len(self.files_meta),
            "chunk_count": len(self.chunks),
            "courses": courses
        }

    # ── 检索与上下文组装 ───────────────────────────────────────────────────────

    def retrieve(self, query, top_k=4, course=None):
        """返回与 query 最相关的 top_k 个片段。
        若指定 course，则优先检索该课程下的课件切片。
        若未指定 course，会先尝试从 query 自动解析涉及的课程。
        """
        if not self.chunks or not query:
            return []

        # 尝试自动检测 query 中的课程名
        target_course = course
        if not target_course:
            known_courses = self.get_courses()
            target_course = match_course_from_query(query, known_courses)

        # 1. 如果指定了目标课程，先做针对性检索
        if target_course:
            course_chunks = [c for c in self.chunks if c.get("course") == target_course]
            if course_chunks:
                # 建立该课程的临时权重与检索
                results = self._retrieve_from_subset(query, course_chunks, top_k=top_k)
                if results:
                    return results

        # 2. 全量检索（语义 > TF-IDF）
        if self._emb_matrix is not None:
            try:
                import numpy as np
                qv = _encode_query(query)
                sims = self._emb_matrix @ qv
                order = np.argsort(-sims)[:top_k]
                return [self.chunks[i] for i in order if float(sims[i]) > 0]
            except Exception:
                pass

        return _retrieve_tfidf(query, self._idf, self._doc_weights, self.chunks, top_k)

    def _retrieve_from_subset(self, query, subset_chunks, top_k=4):
        """在特定课程子集中进行 TF-IDF 检索。"""
        sub_docs = [_tokenize(c["text"]) for c in subset_chunks]
        n = len(sub_docs)
        if not n:
            return []
        df = {}
        for toks in sub_docs:
            for t in set(toks):
                df[t] = df.get(t, 0) + 1
        sub_idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}
        sub_weights = []
        for toks in sub_docs:
            tf = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            w = {t: (1 + math.log(tf[t])) * sub_idf[t] for t in tf}
            norm = math.sqrt(sum(v * v for v in w.values())) or 1.0
            sub_weights.append((w, norm))
        return _retrieve_tfidf(query, sub_idf, sub_weights, subset_chunks, top_k)

    def context(self, query, max_chars=1800, course=None):
        """组装注入大模型 Prompt 的格式化知识库上下文。包含课程归属与来源课件名。"""
        hits = self.retrieve(query, top_k=4, course=course)
        if not hits:
            return ""

        parts = []
        total = 0
        target_course = course or (hits[0].get("course", "") if hits else "")

        if target_course:
            banner = f"【罗德岛学业资料库 · 《{target_course}》课件参考】"
            parts.append(banner)
            total += len(banner)

        for i, ch in enumerate(hits, 1):
            c_tag = f" (课程: {ch['course']})" if ch.get("course") else ""
            piece = "【%s】%s\n%s" % (ch["source"], c_tag, ch["text"])
            if total + len(piece) > max_chars:
                piece = piece[:max_chars - total]
            parts.append(piece)
            total += len(piece)
            if total >= max_chars:
                break

        return "\n\n".join(parts)


def _tokenize(text):
    """粗分词：英文/数字按连续词，中文按单字 + 相邻双字（bigram）。"""
    words = re.findall(r"[a-zA-Z0-9_]{2,}", text.lower())
    han = re.findall(r"[\u4e00-\u9fff]", text)
    bigrams = [a + b for a, b in zip(han, han[1:])]
    return words + han + bigrams


def _retrieve_tfidf(query, idf, doc_weights, chunks, top_k):
    """n-gram TF-IDF 余弦检索（零依赖后端）。"""
    qtoks = _tokenize(query)
    if not qtoks:
        return []
    qtf = {}
    for t in qtoks:
        qtf[t] = qtf.get(t, 0) + 1
    qvec = {t: (1 + math.log(qtf[t])) * idf.get(t, 0.0)
            for t in qtf if idf.get(t, 0.0) > 0}
    if not qvec:
        return []
    qn = math.sqrt(sum(v * v for v in qvec.values())) or 1.0
    scored = []
    for (w, norm), ch in zip(doc_weights, chunks):
        s = sum(w.get(t, 0.0) * v for t, v in qvec.items())
        if s > 0:
            scored.append((s / (norm * qn), ch))
    scored.sort(key=lambda x: -x[0])
    return [ch for _, ch in scored[:top_k]]


def _segment_digest(text):
    """将提炼的考纲按二级标题 (##) 划分为高密度知识点卡片。"""
    sections = []
    parts = re.split(r"(?m)^(?=##\s+)", text.strip())
    for p in parts:
        p = p.strip()
        if p:
            sections.append(p)
    return sections if sections else [text.strip()]


def _segment(text, max_len=600):
    """按幻灯片/页面感知切块（Slide-Aware Chunking）。
    若检测到 PPT/PDF 页码标记，以完整一页为天然知识单元；
    超长页面切分时仍保留页码与页面标题上下文。
    """
    chunks = []
    text = (text or "").strip()
    if not text:
        return []

    # 1. 检测 PPT 页码标记 (=== 第 X 页) 或 PDF 页面标记 (--- 第 X 页 ---)
    is_slide_marked = bool(re.search(r"(?:=== 第 \d+ 页|--- 第 \d+ 页)", text))
    if is_slide_marked:
        pages = re.split(r"(?=(?:=== 第 \d+ 页|--- 第 \d+ 页))", text)
        for page in pages:
            page = page.strip()
            if not page:
                continue
            m_head = re.match(r"^((?:=== 第 \d+ 页.*?===|--- 第 \d+ 页.*?---))(?:\n|$)", page)
            header = m_head.group(1).strip() if m_head else ""
            body = page[len(m_head.group(0)):].strip() if m_head else page

            if len(page) <= max_len:
                chunks.append(page)
            else:
                # 页面超长，先按段落切分，再按句子细分，始终保留页眉标题标记
                clean_title = header.strip("=- ")
                prefix = f"【{clean_title}】\n" if clean_title else ""
                sub_paras = re.split(r"\n\s*\n", body)
                buf = ""
                for sp in sub_paras:
                    sp = sp.strip()
                    if not sp:
                        continue
                    sentences = [s for s in re.split(r"(?<=[。！？；;\n])", sp) if s.strip()] or [sp]
                    for sent in sentences:
                        if len(buf) + len(sent) > max_len and buf:
                            chunks.append(f"{prefix}{buf}".strip())
                            buf = sent
                        else:
                            buf = f"{buf}{sent}"
                if buf:
                    chunks.append(f"{prefix}{buf}".strip())
        if chunks:
            return chunks

    # 2. Markdown 标题感知分割 (# / ##)
    if re.search(r"(?m)^#{1,3}\s+", text):
        sections = re.split(r"(?m)^(?=#{1,3}\s+)", text)
        for sec in sections:
            sec = sec.strip()
            if not sec:
                continue
            if len(sec) <= max_len:
                chunks.append(sec)
            else:
                for p in re.split(r"\n\s*\n", sec):
                    p = p.strip()
                    if p:
                        chunks.append(p)
        if chunks:
            return chunks

    # 3. 常规普通段落分割
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_len:
            chunks.append(para)
            continue
        buf = ""
        for sent in re.split(r"(?<=[。！？；;])", para):
            if len(buf) + len(sent) > max_len and buf:
                chunks.append(buf)
                buf = sent
            else:
                buf += sent
        if buf:
            chunks.append(buf)
    return chunks
