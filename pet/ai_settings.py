"""AI provider settings dialog."""

import json
import os
import time
import urllib.error
import urllib.request

from PyQt5 import QtCore, QtGui, QtWidgets

from . import theme
from .ai import diagnose_network_error, resolve_chat_endpoint


PROVIDERS = [
    ("智谱 GLM", "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash", "永久免费"),
    ("DeepSeek", "https://api.deepseek.com", "deepseek-chat", "高智商·实惠"),
    ("Kimi", "https://api.moonshot.cn", "moonshot-v1-8k", "长文本"),
    ("通义千问", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus", "阿里大模型"),
    ("OpenAI", "https://api.openai.com", "gpt-4o-mini", "官方原版"),
    ("本地 Ollama", "http://localhost:11434/v1", "qwen2.5:7b", "本地私有"),
    ("自定义", "", "", ""),
]

CHIP_STYLE = """
QPushButton {
    background: #181E27;
    color: #E2E8F0;
    border: 1px solid #2D3748;
    border-radius: 6px;
    padding: 7px 8px;
    min-height: 24px;
    font-family: 'Microsoft YaHei UI', 'Microsoft YaHei', 'Segoe UI';
    font-size: 12px;
    font-weight: 500;
}
QPushButton:hover {
    background: #232D3B;
    border-color: #00B0FF;
    color: #FFFFFF;
}
QPushButton:checked {
    background: rgba(0, 176, 255, 0.15);
    border: 1.5px solid #00B0FF;
    color: #00B0FF;
    font-weight: bold;
}
"""


def do_test_connection(base_url, model, api_key, timeout=8):
    """测试与 OpenAI 兼容端点的网络与凭据连通性。

    返回: (success: bool, message: str)
    """
    base = (base_url or "").strip()
    if not base:
        return False, "接口地址不能为空"
    if not model or not model.strip():
        return False, "模型名称不能为空"

    url = resolve_chat_endpoint(base)
    has_custom = bool(api_key and api_key.strip())

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "AmiyaDesktopPet/1.0",
    }
    if has_custom:
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    payload = {
        "model": model.strip(),
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 1,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = int((time.perf_counter() - t0) * 1000)
            code = resp.getcode()
            if 200 <= code < 300:
                return True, f"连接成功 (HTTP {code}，耗时: {elapsed}ms)"
            return False, f"HTTP {code} (耗时: {elapsed}ms)"
    except Exception as e:
        elapsed = int((time.perf_counter() - t0) * 1000)
        detail = ""
        if isinstance(e, urllib.error.HTTPError):
            try:
                err_text = e.read().decode("utf-8", errors="replace")
                err_obj = json.loads(err_text)
                if isinstance(err_obj, dict):
                    err_info = err_obj.get("error", {})
                    if isinstance(err_info, dict):
                        detail = err_info.get("message", "")
                    elif isinstance(err_info, str):
                        detail = err_info
                    else:
                        detail = str(err_obj.get("message", ""))
            except Exception:
                pass

        diag = diagnose_network_error(e, url=url, has_custom_key=has_custom)
        diag = diag.strip().removeprefix("（").removesuffix("）")

        msg = diag
        if detail and len(detail) < 80 and detail not in msg:
            msg += f" [{detail}]"
        msg += f" (耗时: {elapsed}ms)"
        return False, msg


class TestConnectionWorker(QtCore.QThread):
    """后台测试连接线程，保证主 UI 永不卡死。"""

    sig_result = QtCore.pyqtSignal(bool, str)

    def __init__(self, base_url, model, api_key, parent=None):
        super().__init__(parent)
        self.base_url = base_url
        self.model = model
        self.api_key = api_key

    def run(self):
        success, msg = do_test_connection(self.base_url, self.model, self.api_key)
        self.sig_result.emit(success, msg)



def config_path(char_dir):
    return os.path.join(char_dir, "ai_config.json")


def read_raw_config(char_dir):
    """Read ai_config.json, falling back to ai_config.example.json.

    On a fresh clone only the .example.json template exists (the real config is
    gitignored to prevent API-key leaks).  When the user opens AI settings for
    the first time, the .example.json values pre-fill the dialog and get saved
    to the local-only ai_config.json on confirm.
    """
    path = config_path(char_dir)
    example = os.path.join(char_dir, "ai_config.example.json")
    candidates = [path, example]
    for p in candidates:
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        return data if isinstance(data, dict) else {}
    return {}


def save_config(char_dir, cfg):
    path = config_path(char_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


class AiSettingsDialog(QtWidgets.QDialog):
    """OpenAI 兼容端点与大模型服务商配置对话框。"""

    saved = QtCore.pyqtSignal(dict)

    def __init__(self, char_dir, effective_cfg=None, parent=None,
                 character_name="阿米娅"):
        super().__init__(parent)
        self.char_dir = char_dir
        self.character_name = character_name
        self._test_worker = None
        self.setWindowTitle("模型配置")
        self.setModal(True)
        self.setMinimumWidth(720)
        self.setStyleSheet(theme.DIALOG_QSS)

        raw = read_raw_config(char_dir)
        self.cfg = {
            "base_url": raw.get("base_url", "https://api.deepseek.com"),
            "model": raw.get("model", "deepseek-chat"),
            "api_key": raw.get("api_key", ""),
            "temperature": raw.get("temperature", 0.8),
            "allow_actions": raw.get("allow_actions", True),
        }
        if effective_cfg:
            for key in ("base_url", "model", "api_key", "temperature",
                        "allow_actions"):
                if key in effective_cfg:
                    self.cfg[key] = effective_cfg[key]

        self._build_ui()
        self._load_values()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QtWidgets.QLabel("RHODES ISLAND", self)
        title.setObjectName("TerminalTitle")
        root.addWidget(title)

        subtitle = QtWidgets.QLabel("%s MODEL CONFIGURATION" % self.character_name, self)
        subtitle.setObjectName("TerminalSubTitle")
        root.addWidget(subtitle)

        # ── 快捷服务商 Chips 栏 ─────────────────────────────────────────
        chip_box = QtWidgets.QGroupBox("常用大模型一键配置（对齐手机端快捷选项）", self)
        chip_box.setStyleSheet("""
            QGroupBox {
                color: #00B0FF;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #232A36;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 4px;
            }
        """)
        chip_grid = QtWidgets.QGridLayout(chip_box)
        chip_grid.setContentsMargins(10, 10, 10, 10)
        chip_grid.setHorizontalSpacing(8)
        chip_grid.setVerticalSpacing(8)

        self.chip_buttons = []
        for i, preset in enumerate(PROVIDERS[:-1]):
            name, url, model, tag = preset
            btn = QtWidgets.QPushButton(chip_box)
            btn.setText(f"{name}  ·  {tag}")
            btn.setCheckable(True)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setStyleSheet(CHIP_STYLE)
            btn.clicked.connect(lambda _, idx=i: self._on_chip_clicked(idx))
            row = i // 3
            col = i % 3
            chip_grid.addWidget(btn, row, col)
            self.chip_buttons.append(btn)
        root.addWidget(chip_box)

        # ── 详细表单设置 ─────────────────────────────────────────────
        form = QtWidgets.QFormLayout()
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        form.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        root.addLayout(form)

        self.provider = QtWidgets.QComboBox(self)
        for p in PROVIDERS:
            name = p[0]
            self.provider.addItem(name)
        self.provider.currentIndexChanged.connect(self._provider_changed)
        form.addRow("服务商", self.provider)

        self.base_url = QtWidgets.QLineEdit(self)
        self.base_url.setPlaceholderText("https://... 或 http://localhost:11434/v1")
        self.base_url.textChanged.connect(self._sync_chips_and_combobox)
        form.addRow("接口地址", self.base_url)

        self.model = QtWidgets.QLineEdit(self)
        self.model.setPlaceholderText("例如 moonshot-v1-8k / qwen-plus")
        form.addRow("模型", self.model)

        self.api_key = QtWidgets.QLineEdit(self)
        self.api_key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.api_key.setPlaceholderText("不填则默认启用公共免费 AI 线路（离线时使用内置台词）")
        form.addRow("API Key", self.api_key)

        self.temperature = QtWidgets.QDoubleSpinBox(self)
        self.temperature.setRange(0.0, 2.0)
        self.temperature.setSingleStep(0.1)
        self.temperature.setDecimals(1)
        form.addRow("灵活度", self.temperature)

        self.allow_actions = QtWidgets.QCheckBox(
            "允许%s操作电脑" % self.character_name, self)
        form.addRow("", self.allow_actions)

        self.note = QtWidgets.QLabel(
            "提示：无需配置 Key 即可直接与阿米娅 AI 对话（默认走公共免费线路）；"
            "填写自定义 Key 后将优先使用您的专属模型。若设置了 PET_AI_* 环境变量亦优先遵循。",
            self,
        )
        self.note.setObjectName("TerminalNote")
        self.note.setWordWrap(True)
        root.addWidget(self.note)

        # ── 连通性测试与状态指示栏 ─────────────────────────────────────
        test_bar = QtWidgets.QHBoxLayout()
        test_bar.setSpacing(10)

        self.btn_test = QtWidgets.QPushButton("⚡ 测试连通性", self)
        self.btn_test.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_test.setStyleSheet("""
            QPushButton {
                background: #1A2230;
                color: #00B0FF;
                border: 1px solid #00B0FF;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(0, 176, 255, 0.2);
            }
            QPushButton:disabled {
                color: #64748B;
                border-color: #334155;
                background: #14171F;
            }
        """)
        self.btn_test.clicked.connect(self._start_test_connection)
        test_bar.addWidget(self.btn_test)

        self.lbl_test_status = QtWidgets.QLabel(self)
        self.lbl_test_status.setStyleSheet("font-size: 12px;")
        self.lbl_test_status.setWordWrap(True)
        test_bar.addWidget(self.lbl_test_status, 1)
        root.addLayout(test_bar)

        # ── 底部操作按钮 ─────────────────────────────────────────────
        bottom_bar = QtWidgets.QHBoxLayout()
        bottom_bar.addStretch(1)

        btn_cancel = QtWidgets.QPushButton("取消", self)
        btn_cancel.clicked.connect(self.reject)
        bottom_bar.addWidget(btn_cancel)

        btn_save = QtWidgets.QPushButton("保存配置", self)
        btn_save.setObjectName("PrimaryBtn")
        btn_save.setStyleSheet("""
            QPushButton#PrimaryBtn {
                background: #00B0FF;
                color: #FFFFFF;
                border: 1px solid #0091EA;
                border-radius: 4px;
                font-weight: bold;
                padding: 6px 16px;
            }
            QPushButton#PrimaryBtn:hover {
                background: #40C4FF;
            }
        """)
        btn_save.clicked.connect(self._save)
        bottom_bar.addWidget(btn_save)

        root.addLayout(bottom_bar)

    def _load_values(self):
        self.base_url.setText(str(self.cfg.get("base_url") or ""))
        self.model.setText(str(self.cfg.get("model") or ""))
        self.api_key.setText(str(self.cfg.get("api_key") or ""))
        self.temperature.setValue(float(self.cfg.get("temperature", 0.8)))
        self.allow_actions.setChecked(bool(self.cfg.get("allow_actions", True)))
        self._sync_chips_and_combobox()

    def _sync_chips_and_combobox(self):
        cur_url = self.base_url.text().strip().rstrip("/")
        norm_cur = cur_url
        if norm_cur.endswith("/chat/completions"):
            norm_cur = norm_cur[:-len("/chat/completions")].rstrip("/")

        matched_idx = -1
        for i, preset in enumerate(PROVIDERS[:-1]):
            _, url, _, _ = preset
            norm_preset = url.rstrip("/")
            if norm_preset.endswith("/chat/completions"):
                norm_preset = norm_preset[:-len("/chat/completions")].rstrip("/")
            if cur_url == url.rstrip("/") or norm_cur == norm_preset:
                matched_idx = i
                break

        for i, btn in enumerate(self.chip_buttons):
            btn.blockSignals(True)
            btn.setChecked(i == matched_idx)
            btn.blockSignals(False)

        target_cb_idx = matched_idx if matched_idx >= 0 else (len(PROVIDERS) - 1)
        self.provider.blockSignals(True)
        self.provider.setCurrentIndex(target_cb_idx)
        self.provider.blockSignals(False)

    def _on_chip_clicked(self, idx):
        _, url, model, _ = PROVIDERS[idx]
        self.base_url.setText(url)
        self.model.setText(model)
        self._sync_chips_and_combobox()
        self.lbl_test_status.setText("")

    def _provider_changed(self, index):
        if index < len(PROVIDERS) - 1:
            _, url, model, _ = PROVIDERS[index]
            self.base_url.setText(url)
            self.model.setText(model)
        self._sync_chips_and_combobox()
        self.lbl_test_status.setText("")

    def _start_test_connection(self):
        base_url = self.base_url.text().strip()
        model = self.model.text().strip()
        api_key = self.api_key.text().strip()

        if not base_url:
            QtWidgets.QMessageBox.warning(self, "连通性测试", "请先输入接口地址。")
            return
        if not model:
            QtWidgets.QMessageBox.warning(self, "连通性测试", "请先输入模型名称。")
            return

        self.btn_test.setEnabled(False)
        self.btn_test.setText("测试中...")
        self.lbl_test_status.setText("⏳ 正在测试网络与接口连通性...")
        self.lbl_test_status.setStyleSheet("color: #FBBF24; font-size: 12px; font-weight: bold;")

        self._test_worker = TestConnectionWorker(base_url, model, api_key, self)
        self._test_worker.sig_result.connect(self._on_test_finished)
        self._test_worker.start()

    def _on_test_finished(self, success, msg):
        self.btn_test.setEnabled(True)
        self.btn_test.setText("⚡ 测试连通性")
        if success:
            self.lbl_test_status.setText(f"✓ {msg}")
            self.lbl_test_status.setStyleSheet("color: #00E676; font-size: 12px; font-weight: bold;")
        else:
            self.lbl_test_status.setText(f"✗ {msg}")
            self.lbl_test_status.setStyleSheet("color: #FF5252; font-size: 12px; font-weight: bold;")

    def _save(self):
        base_url = self.base_url.text().strip().rstrip("/")
        model = self.model.text().strip()
        api_key = self.api_key.text().strip()
        if not base_url:
            QtWidgets.QMessageBox.warning(self, "模型配置", "请填写接口地址。")
            return
        if not model:
            QtWidgets.QMessageBox.warning(self, "模型配置", "请填写模型名称。")
            return

        cfg = {
            "base_url": base_url,
            "model": model,
            "api_key": api_key,
            "temperature": self.temperature.value(),
            "allow_actions": self.allow_actions.isChecked(),
        }
        try:
            save_config(self.char_dir, cfg)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "模型配置", "保存失败：%s" % type(e).__name__)
            return
        self.saved.emit(cfg)
        self.accept()

    def closeEvent(self, event):
        if self._test_worker and self._test_worker.isRunning():
            self._test_worker.terminate()
            self._test_worker.wait(500)
        super().closeEvent(event)
