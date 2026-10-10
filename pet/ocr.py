"""OCR：从截图中提取文字（供截图翻译/截图总结使用）。

后端优先级：
  1. **Windows 自带 OCR**（WinRT，通过可选的 winsdk 包）——离线、免费、
     中文支持好。安装：`pip install winsdk`。未安装则跳过。
  2. **AI 视觉模型**（OpenAI 兼容 /chat/completions，image_url base64）——
     需要 ai_config 里配置支持视觉的模型（如 moonshot-v1-8k-vision-preview）。
两个后端都不可用时抛 OcrError，由调用方给出安装提示。

翻译与总结的 AI 调用是**无状态**的（不进对话历史）。
"""

import base64
import io
import json
import os
import urllib.request

# RapidOCR 本地高精度 OCR 引擎（首选：零配置、跨平台、中文公式支持好）
_RAPID_ENGINE = None

def _get_rapid_ocr():
    global _RAPID_ENGINE
    if _RAPID_ENGINE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _RAPID_ENGINE = RapidOCR()
        except Exception as e:
            try:
                from . import logging as petlog
                petlog.warn(f"ocr: 初始化 RapidOCR 失败: {e}")
            except Exception:
                pass
            _RAPID_ENGINE = False
    return _RAPID_ENGINE if _RAPID_ENGINE is not False else None


def rapidocr_available():
    """本地 RapidOCR 引擎是否可用。"""
    try:
        import rapidocr_onnxruntime
        return True
    except Exception:
        return False


# winsdk / winrt 为后备离线 OCR（延迟检测与导入，避免在导入期改变 Windows COM 运行时）
_wimg = _wocr = _wstreams = _wglob = None
_WINRT_CHECKED = False
_WINRT_OK = False

def _check_winrt():
    global _wimg, _wocr, _wstreams, _wglob, _WINRT_CHECKED, _WINRT_OK
    if not _WINRT_CHECKED:
        _WINRT_CHECKED = True
        try:
            import winsdk.windows.graphics.imaging as _wimg
            import winsdk.windows.media.ocr as _wocr
            import winsdk.windows.storage.streams as _wstreams
            import winsdk.windows.globalization as _wglob
            _WINRT_OK = True
        except Exception:
            try:
                import winrt.windows.graphics.imaging as _wimg
                import winrt.windows.media.ocr as _wocr
                import winrt.windows.storage.streams as _wstreams
                import winrt.windows.globalization as _wglob
                _WINRT_OK = True
            except Exception:
                _WINRT_OK = False
    return _WINRT_OK


class OcrError(Exception):
    pass


def winrt_available():
    """Windows 自带 OCR 是否可用（winsdk 已安装）。"""
    return _check_winrt()


def _ocr_winrt(image):
    """PIL Image -> 文字（Windows 自带 OCR，需 winsdk / winrt）。"""
    import asyncio

    async def go():
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        stream = _wstreams.InMemoryRandomAccessStream()
        writer = _wstreams.DataWriter(stream)
        writer.write_bytes(buf.getvalue())
        await writer.store_async()
        stream.seek(0)
        decoder = await _wimg.BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        engine = _wocr.OcrEngine.try_create_from_language(_wglob.Language("zh-Hans-CN"))
        if engine is None:
            engine = _wocr.OcrEngine.try_create_from_language(_wglob.Language("zh-CN"))
        if engine is None:
            engine = _wocr.OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            return ""
        result = await engine.recognize_async(bitmap)
        return "\n".join(line.text for line in result.lines)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(go())).result(timeout=30)
    else:
        return asyncio.run(go())


def _ocr_via_ai(image, cfg):
    """把图片发给 AI 视觉模型识别文字。"""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    data_url = "data:image/png;base64," + b64
    payload = {
        "model": cfg.get("model", "moonshot-v1-8k-vision-preview"),
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text",
                 "text": "请识别这张截图中的全部文字，原样输出，"
                         "不要添加任何解释、注释或额外文字。"},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
        "temperature": 0,
    }
    url = str(cfg["base_url"]).rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + cfg["api_key"]})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"].get("content", "").strip()


def ocr_available():
    """是否有离线或在线 OCR 能力可用。"""
    return bool(rapidocr_available() or winrt_available())


def recognize(target):
    """通用 OCR 识别入口，支持文件路径 (str)、PIL Image、bytes。返回字符串结果。"""
    if not target:
        return ""
    try:
        from PIL import Image
        if isinstance(target, str) and os.path.isfile(target):
            img = Image.open(target)
        elif isinstance(target, (bytes, bytearray)):
            img = Image.open(io.BytesIO(target))
        else:
            img = target
        text, _ = ocr_image(img)
        return text
    except Exception:
        return ""


def ocr_image(image, brain_cfg=None):
    """识别 PIL Image 中的文字，返回 (text, backend)。backend ∈ {'rapidocr','winrt','ai'}。"""
    # 尺寸优化：幻灯片超大图（如 1920x1440+）按比例缩放到最大宽 1280，提速 2~3 倍且不影响文字识别
    if hasattr(image, "width") and hasattr(image, "height"):
        max_dim = max(image.width, image.height)
        if max_dim > 1440:
            scale = 1280.0 / max_dim
            new_w = max(1, int(image.width * scale))
            new_h = max(1, int(image.height * scale))
            try:
                from PIL import Image
                image = image.resize((new_w, new_h), Image.Resampling.BILINEAR)
            except Exception:
                pass

    # 1. 优先使用本地高精度 RapidOCR (ONNXRuntime)
    engine = _get_rapid_ocr()
    if engine:
        try:
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            res, _ = engine(buf.getvalue())
            if res:
                lines = [r[1] for r in res if len(r) > 1 and str(r[1]).strip()]
                text = "\n".join(lines).strip()
                if text:
                    return text, "rapidocr"
        except Exception:
            pass

    # 2. 次选 Windows 自带 OCR (winsdk)
    if winrt_available():
        try:
            text = _ocr_winrt(image).strip()
            if text:
                return text, "winrt"
        except Exception:
            pass  # 降级到 AI

    # 3. 降级到 AI 视觉大模型
    if brain_cfg and brain_cfg.get("api_key"):
        try:
            return _ocr_via_ai(image, brain_cfg), "ai"
        except Exception as e:
            raise OcrError("AI 视觉识别失败：%s" % type(e).__name__)
    raise OcrError(
        "OCR 不可用或未能识别文字：请安装 winsdk (pip install winsdk) 使用离线识别，"
        "或在 ai_config.json 配置支持视觉的模型（如 moonshot-v1-8k-vision-preview）。")


def summarize_ai(cfg, text, target_lang="中文"):
    """用 AI 总结 OCR 出的文字（无状态调用）。返回总结或抛 OcrError。"""
    if not (cfg and cfg.get("api_key")):
        raise OcrError("总结需要配置 AI：请在 ai_config.json 填写 api_key。")
    prompt = ("你是学习助手。请用%s总结以下文字（来自截图），"
              "提炼要点、条理清晰，不要超过 200 字：\n\n%s"
              % (target_lang, text[:6000]))
    payload = {
        "model": cfg.get("model"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }
    url = str(cfg["base_url"]).rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + cfg["api_key"]})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"].get("content", "").strip()
    except Exception as e:
        raise OcrError("AI 总结失败：%s" % type(e).__name__)
