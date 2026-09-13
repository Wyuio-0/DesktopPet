"""罗德岛跨端协同管理中心与配对认证界面 (Rhodes Link Center & Pairing UI)。

提供：
1. RhodesPairConfirmDialog：当有移动终端发起配对时弹出的战术核验确认弹窗（必须博士确认才能建立受信任互联）。
2. RhodesSyncWindow：完整的双端协同控制台（设备搜索、手动 IP 直连、学业数据一键双向同步、战术快传投递）。
"""

import threading
import time
from PyQt5 import QtCore, QtGui, QtWidgets

from . import theme
from .notes import NotesManager
from .schedule import Schedule
from .sync_service import get_sync_service, get_local_ips
from .tasks import Tasks

_SYNC_QSS = """
QDialog, QWidget#RhodesSyncWindow {
    background-color: %s;
    color: %s;
    font-family: %s;
}
QGroupBox {
    border: 1px solid %s;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 14px;
    font-size: 13px;
    font-weight: bold;
    color: %s;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
}
QPushButton {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: %s;
    border-color: %s;
    color: #FFFFFF;
}
QPushButton:pressed {
    background-color: %s;
}
QPushButton#PrimaryBtn {
    background-color: #00838F;
    border: 1px solid #00ACC1;
    color: #FFFFFF;
    font-weight: bold;
}
QPushButton#PrimaryBtn:hover {
    background-color: #0097A7;
    border-color: #26C6DA;
}
QPushButton#DangerBtn {
    background-color: #5C2525;
    border: 1px solid #8C3A3A;
    color: #FFAAAA;
}
QPushButton#DangerBtn:hover {
    background-color: #7A2E2E;
    color: #FFFFFF;
}
QLineEdit, QTextEdit {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
    border-radius: 4px;
    padding: 6px 8px;
    selection-background-color: #00838F;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #00ACC1;
    background-color: %s;
}
QListWidget {
    background-color: %s;
    border: 1px solid %s;
    border-radius: 4px;
    color: %s;
    padding: 4px;
}
QListWidget::item {
    padding: 8px;
    border-bottom: 1px solid %s;
    border-radius: 3px;
}
QListWidget::item:selected {
    background-color: #1A3038;
    color: #00E5FF;
}
QLabel {
    color: %s;
}
""" % (
    theme.DLG_BG, theme.FLOAT_TEXT, theme.FONT,
    theme.FLOAT_GRID, theme.FLOAT_GOLD,
    theme.DLG_FIELD, theme.FLOAT_TEXT, theme.FLOAT_GRID,
    "#222222", theme.FLOAT_ACCENT, "#111111",
    theme.DLG_FIELD, theme.FLOAT_TEXT, theme.FLOAT_GRID,
    theme.DLG_FIELD_FOCUS,
    theme.DLG_FIELD, theme.FLOAT_GRID, theme.FLOAT_TEXT,
    theme.FLOAT_GRID,
    theme.FLOAT_TEXT
)


class RhodesPairConfirmDialog(QtWidgets.QDialog):
    """蓝牙式配对确认弹窗：当远端设备发起连接时，要求博士必须在屏幕上亲自核对并确认。"""

    def __init__(self, pair_req, parent=None):
        super().__init__(parent)
        self.pair_req = pair_req
        self.accepted_result = False
        self.countdown = 30

        self.setWindowTitle("罗德岛终端互联 · 战术配对确认")
        self.setFixedWidth(440)
        self.setStyleSheet(_SYNC_QSS)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)

        self._init_ui()

        # 30秒倒计时自动拒绝
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(1000)

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题栏
        head_layout = QtWidgets.QHBoxLayout()
        icon_lbl = QtWidgets.QLabel("🛡️")
        icon_lbl.setStyleSheet("font-size: 26px;")
        head_layout.addWidget(icon_lbl)

        title_box = QtWidgets.QVBoxLayout()
        title_lbl = QtWidgets.QLabel("罗德岛终端配对请求")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #00E5FF;")
        sub_lbl = QtWidgets.QLabel("检测到来自移动终端的连接申请，请核对配对码")
        sub_lbl.setStyleSheet(f"font-size: 12px; color: {theme.FLOAT_TEXT_DIM};")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        head_layout.addLayout(title_box)
        head_layout.addStretch()
        layout.addLayout(head_layout)

        # 信息卡片
        info_card = QtWidgets.QFrame()
        info_card.setStyleSheet(f"background-color: {theme.FIELD_DARK}; border: 1px solid {theme.FLOAT_GRID}; border-radius: 6px; padding: 10px;")
        card_layout = QtWidgets.QVBoxLayout(info_card)
        card_layout.setSpacing(8)

        req_device = QtWidgets.QLabel(f"<b>请求设备：</b> {self.pair_req.client_name}")
        req_ip = QtWidgets.QLabel(f"<b>设备 IP：</b> {self.pair_req.client_ip}:{self.pair_req.client_port}")
        card_layout.addWidget(req_device)
        card_layout.addWidget(req_ip)

        pin_box = QtWidgets.QHBoxLayout()
        pin_title = QtWidgets.QLabel("<b>战术配对码：</b>")
        # 格式化配对码，如 "582 914"
        raw_pin = self.pair_req.pin
        formatted_pin = f"{raw_pin[:3]} {raw_pin[3:]}" if len(raw_pin) == 6 else raw_pin
        pin_val = QtWidgets.QLabel(formatted_pin)
        pin_val.setStyleSheet("font-size: 24px; font-weight: bold; color: #00E5FF; letter-spacing: 2px;")
        pin_box.addWidget(pin_title)
        pin_box.addWidget(pin_val)
        pin_box.addStretch()
        card_layout.addLayout(pin_box)

        layout.addWidget(info_card)

        tip_lbl = QtWidgets.QLabel("⚠️ 只有点击「确认配对」后，双方才会建立受信任连接并允许同步课表、考试、便签及剪贴板。若不是您本人的操作，请点击拒绝。")
        tip_lbl.setWordWrap(True)
        tip_lbl.setStyleSheet(f"font-size: 11px; color: {theme.FLOAT_TEXT_DIM}; line-height: 1.4;")
        layout.addWidget(tip_lbl)

        # 倒计时与按键
        btn_layout = QtWidgets.QHBoxLayout()
        self.countdown_lbl = QtWidgets.QLabel(f"自动拒绝倒计时: {self.countdown}s")
        self.countdown_lbl.setStyleSheet(f"font-size: 11px; color: {theme.FLOAT_TEXT_DIM};")
        btn_layout.addWidget(self.countdown_lbl)
        btn_layout.addStretch()

        self.btn_reject = QtWidgets.QPushButton("拒绝 (Reject)")
        self.btn_reject.setObjectName("DangerBtn")
        self.btn_reject.clicked.connect(self._on_reject)
        btn_layout.addWidget(self.btn_reject)

        self.btn_accept = QtWidgets.QPushButton("确认配对 (Accept)")
        self.btn_accept.setObjectName("PrimaryBtn")
        self.btn_accept.clicked.connect(self._on_accept)
        btn_layout.addWidget(self.btn_accept)

        layout.addLayout(btn_layout)

    def _on_tick(self):
        self.countdown -= 1
        self.countdown_lbl.setText(f"自动拒绝倒计时: {self.countdown}s")
        if self.countdown <= 0:
            self.timer.stop()
            self._on_reject()

    def _on_accept(self):
        self.timer.stop()
        self.accepted_result = True
        service = get_sync_service()
        service.pair_manager.accept_request(self.pair_req.request_id)
        self.accept()

    def _on_reject(self):
        self.timer.stop()
        self.accepted_result = False
        service = get_sync_service()
        service.pair_manager.reject_request(self.pair_req.request_id)
        self.reject()

    def closeEvent(self, event):
        if not self.accepted_result:
            service = get_sync_service()
            service.pair_manager.reject_request(self.pair_req.request_id)
        super().closeEvent(event)


class RhodesSyncWindow(QtWidgets.QDialog):
    """罗德岛跨端协同管理中心主窗口。"""

    # Qt 信号保证跨线程安全触发 UI
    pair_request_signal = QtCore.pyqtSignal(object)
    clipboard_signal = QtCore.pyqtSignal(str, str)
    data_synced_signal = QtCore.pyqtSignal(dict)

    def __init__(self, owner=None):
        super().__init__(owner)
        self.owner = owner
        self.service = get_sync_service()
        self.discovered_devices = []

        self.setWindowTitle("罗德岛跨端协同 · 双端互联管理中心")
        self.resize(680, 560)
        self.setStyleSheet(_SYNC_QSS)

        self._init_ui()
        self._bind_service()
        self._refresh_local_info()
        self._refresh_paired_list()
        self._refresh_data_counts()

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # ── 1. 本机终端状态栏 ─────────────────────────────────────────
        top_box = QtWidgets.QHBoxLayout()
        title_icon = QtWidgets.QLabel("📱💻")
        title_icon.setStyleSheet("font-size: 24px;")
        top_box.addWidget(title_icon)

        title_info = QtWidgets.QVBoxLayout()
        title_text = QtWidgets.QLabel("罗德岛终端局域网互联 (PC ↔ Android)")
        title_text.setStyleSheet("font-size: 15px; font-weight: bold; color: #00E5FF;")
        self.lbl_status = QtWidgets.QLabel("服务状态: 🟢 监听中 | 本机 IP: 获取中...")
        self.lbl_status.setStyleSheet(f"font-size: 12px; color: {theme.FLOAT_TEXT_DIM};")
        title_info.addWidget(title_text)
        title_info.addWidget(self.lbl_status)
        top_box.addLayout(title_info)
        top_box.addStretch()

        self.btn_refresh = QtWidgets.QPushButton("⟳ 刷新状态")
        self.btn_refresh.clicked.connect(self._refresh_all)
        top_box.addWidget(self.btn_refresh)
        main_layout.addLayout(top_box)

        # ── 2. 设备发现与配对区 ───────────────────────────────────────
        dev_group = QtWidgets.QGroupBox("1. 终端发现与配对 (像蓝牙一样搜索并显式确认)")
        dev_layout = QtWidgets.QVBoxLayout(dev_group)

        # 发现与搜索控制条
        search_bar = QtWidgets.QHBoxLayout()
        self.btn_scan = QtWidgets.QPushButton("🔍 搜索局域网设备")
        self.btn_scan.setObjectName("PrimaryBtn")
        self.btn_scan.clicked.connect(self._start_scan)
        search_bar.addWidget(self.btn_scan)

        search_bar.addWidget(QtWidgets.QLabel("或直连 IP:"))
        self.txt_manual_ip = QtWidgets.QLineEdit()
        self.txt_manual_ip.setPlaceholderText("例如: 10.0.2.15 或 192.168.1.xxx")
        self.txt_manual_ip.setFixedWidth(180)
        search_bar.addWidget(self.txt_manual_ip)

        self.btn_manual_connect = QtWidgets.QPushButton("探测并请求配对")
        self.btn_manual_connect.clicked.connect(self._connect_manual)
        search_bar.addWidget(self.btn_manual_connect)
        search_bar.addStretch()
        dev_layout.addLayout(search_bar)

        # 设备列表分为：发现的设备 / 已配对设备
        lists_layout = QtWidgets.QHBoxLayout()

        discovered_box = QtWidgets.QVBoxLayout()
        discovered_box.addWidget(QtWidgets.QLabel("发现的附近设备 (点击请求配对):"))
        self.list_discovered = QtWidgets.QListWidget()
        self.list_discovered.itemDoubleClicked.connect(self._on_discovered_clicked)
        discovered_box.addWidget(self.list_discovered)
        lists_layout.addLayout(discovered_box)

        paired_box = QtWidgets.QVBoxLayout()
        paired_box.addWidget(QtWidgets.QLabel("已配对信任设备 (已建立安全信道):"))
        self.list_paired = QtWidgets.QListWidget()
        paired_box.addWidget(self.list_paired)

        paired_btn_box = QtWidgets.QHBoxLayout()
        self.btn_unpair = QtWidgets.QPushButton("解除配对 / 撤销信任")
        self.btn_unpair.setObjectName("DangerBtn")
        self.btn_unpair.clicked.connect(self._on_unpair_clicked)
        paired_btn_box.addWidget(self.btn_unpair)
        paired_btn_box.addStretch()
        paired_box.addLayout(paired_btn_box)

        lists_layout.addLayout(paired_box)
        dev_layout.addLayout(lists_layout)
        main_layout.addWidget(dev_group)

        # ── 3. 学业数据一键双向同步区 ─────────────────────────────────
        sync_group = QtWidgets.QGroupBox("2. 学业数据双向同步 (课表 · 考试 · 便签)")
        sync_layout = QtWidgets.QVBoxLayout(sync_group)

        # 数据概览
        self.lbl_data_counts = QtWidgets.QLabel("本地学业数据：课表 0 门 | 考试日程 0 场 | 灵感便签 0 篇")
        self.lbl_data_counts.setStyleSheet(f"font-size: 12px; color: {theme.FLOAT_GOLD}; font-weight: bold;")
        sync_layout.addWidget(self.lbl_data_counts)

        sync_btn_bar = QtWidgets.QHBoxLayout()
        self.btn_sync_all = QtWidgets.QPushButton("⚡ 一键双向智能合并 (Merge All)")
        self.btn_sync_all.setObjectName("PrimaryBtn")
        self.btn_sync_all.clicked.connect(self._sync_merge_all)
        sync_btn_bar.addWidget(self.btn_sync_all)

        self.btn_pull = QtWidgets.QPushButton("📥 从选中手机拉取覆盖")
        self.btn_pull.clicked.connect(self._sync_pull_remote)
        sync_btn_bar.addWidget(self.btn_pull)

        self.btn_push = QtWidgets.QPushButton("📤 推送电脑数据到手机")
        self.btn_push.clicked.connect(self._sync_push_remote)
        sync_btn_bar.addWidget(self.btn_push)
        sync_btn_bar.addStretch()
        sync_layout.addLayout(sync_btn_bar)

        self.lbl_sync_result = QtWidgets.QLabel("就绪。")
        self.lbl_sync_result.setStyleSheet(f"font-size: 11px; color: {theme.FLOAT_TEXT_DIM};")
        sync_layout.addWidget(self.lbl_sync_result)

        main_layout.addWidget(sync_group)

        # ── 4. 罗德岛「战术快传」隔空投送区 ───────────────────────────
        drop_group = QtWidgets.QGroupBox("3. 罗德岛「战术快传」(跨端隔空投送剪贴板/文字)")
        drop_layout = QtWidgets.QHBoxLayout(drop_group)

        self.txt_drop_content = QtWidgets.QLineEdit()
        self.txt_drop_content.setPlaceholderText("输入要发送到手机的文本、网址或便签内容...")
        drop_layout.addWidget(self.txt_drop_content)

        self.btn_send_text = QtWidgets.QPushButton("🚀 发送文本到手机")
        self.btn_send_text.setObjectName("PrimaryBtn")
        self.btn_send_text.clicked.connect(self._send_text_drop)
        drop_layout.addWidget(self.btn_send_text)

        self.btn_send_clip = QtWidgets.QPushButton("📋 发送当前剪贴板")
        self.btn_send_clip.clicked.connect(self._send_clipboard_drop)
        drop_layout.addWidget(self.btn_send_clip)

        main_layout.addWidget(drop_group)

    def _bind_service(self):
        """绑定服务事件到 Qt 信号槽。"""
        self.pair_request_signal.connect(self._show_pair_confirm_dialog)
        self.clipboard_signal.connect(self._handle_incoming_clipboard)
        self.data_synced_signal.connect(self._handle_data_synced)

        self.service.on_pair_request_callback = lambda req: self.pair_request_signal.emit(req)
        self.service.on_clipboard_callback = lambda text, title: self.clipboard_signal.emit(text, title)
        self.service.on_data_synced_callback = lambda res: self.data_synced_signal.emit(res)

    def _refresh_local_info(self):
        ips = get_local_ips()
        ip_str = ", ".join(ips)
        self.lbl_status.setText(f"服务状态: 🟢 监听中 (端口 {self.service.http_port}) | 本机 IP: {ip_str}")

    def _refresh_data_counts(self):
        sched = Schedule()
        tasks = Tasks()
        notes = NotesManager()
        exams_count = len([t for t in tasks.items if t.kind == "exam"])
        self.lbl_data_counts.setText(
            f"本地学业数据：课表 {len(sched.courses)} 门课程 | 考试日程 {exams_count} 场 | 灵感便签 {len(notes.notes)} 篇"
        )

    def _refresh_paired_list(self):
        self.list_paired.clear()
        trusted = self.service.pair_manager.get_trusted_devices()
        for dev_id, info in trusted.items():
            name = info.get("name", "移动终端")
            ip = info.get("ip", "未知 IP")
            port = info.get("port", 23334)
            paired_at = info.get("paired_at", "")
            item = QtWidgets.QListWidgetItem(f"📱 {name} ({ip}:{port}) - 已连接\n   配对时间: {paired_at}")
            item.setData(QtCore.Qt.UserRole, (dev_id, info))
            self.list_paired.addItem(item)

        if not trusted:
            item = QtWidgets.QListWidgetItem("暂无受信任设备，请先在左侧搜索或输入 IP 配对")
            item.setFlags(QtCore.Qt.NoItemFlags)
            self.list_paired.addItem(item)

    def _refresh_all(self):
        self._refresh_local_info()
        self._refresh_paired_list()
        self._refresh_data_counts()

    # ── 设备搜索与配对 ───────────────────────────────────────────────

    def _start_scan(self):
        self.btn_scan.setEnabled(False)
        self.btn_scan.setText("正在雷达扫描...")
        self.list_discovered.clear()
        self.list_discovered.addItem("正在广播搜索局域网 Android 终端...")

        def scan_worker():
            results = self.service.scan_lan_devices(timeout=2.0)
            QtCore.QMetaObject.invokeMethod(self, "_on_scan_finished", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(object, results))

        threading.Thread(target=scan_worker, daemon=True).start()

    @QtCore.pyqtSlot(object)
    def _on_scan_finished(self, results):
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("🔍 搜索局域网设备")
        self.list_discovered.clear()
        self.discovered_devices = results or []

        if not self.discovered_devices:
            self.list_discovered.addItem("未扫描到附近的终端。提示：\n1. 确保手机处于同一局域网并打开终端互联页面\n2. 模拟器环境请在右侧直接输入 127.0.0.1 或 10.0.2.15 直连")
            return

        for dev in self.discovered_devices:
            name = dev.get("device_name", "Android 设备")
            ip = dev.get("ip", "")
            port = dev.get("http_port", 23334)
            dev_type = dev.get("device_type", "android")
            item = QtWidgets.QListWidgetItem(f"📱 {name} ({ip}:{port}) [{dev_type.upper()}] - 双击发起配对")
            item.setData(QtCore.Qt.UserRole, dev)
            self.list_discovered.addItem(item)

    def _on_discovered_clicked(self, item):
        dev = item.data(QtCore.Qt.UserRole)
        if not dev:
            return
        ip = dev.get("ip")
        port = dev.get("http_port", 23334)
        name = dev.get("device_name", ip)
        self._request_pair_to_remote(ip, port, name)

    def _connect_manual(self):
        ip = self.txt_manual_ip.text().strip()
        if not ip:
            QtWidgets.QMessageBox.warning(self, "提示", "请输入目标设备的 IP 地址")
            return

        port = 23334
        if ":" in ip:
            parts = ip.split(":")
            ip = parts[0]
            try:
                port = int(parts[1])
            except Exception:
                pass

        self._request_pair_to_remote(ip, port, ip)

    def _request_pair_to_remote(self, ip, port, name):
        reply = QtWidgets.QMessageBox.question(
            self, "发起配对确认",
            f"确定向终端「{name}」({ip}:{port}) 发起蓝牙式配对请求？\n发起后目标端屏幕将弹出核验确认卡片。",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        self.lbl_sync_result.setText(f"正在向 {name} 发送配对握手请求，等待手机端确认...")

        def pair_worker():
            success, msg, _ = self.service.request_pair(ip, port)
            QtCore.QMetaObject.invokeMethod(
                self, "_on_pair_result", QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(bool, success), QtCore.Q_ARG(str, msg)
            )

        threading.Thread(target=pair_worker, daemon=True).start()

    @QtCore.pyqtSlot(bool, str)
    def _on_pair_result(self, success, msg):
        self.lbl_sync_result.setText(f"配对结果: {msg}")
        if success:
            QtWidgets.QMessageBox.information(self, "配对成功", f"🎉 {msg}\n双端已成功建立信任互联信道！")
            self._refresh_paired_list()
        else:
            QtWidgets.QMessageBox.warning(self, "配对未完成", f"❌ {msg}")

    def _on_unpair_clicked(self):
        selected = self.list_paired.currentItem()
        if not selected:
            QtWidgets.QMessageBox.warning(self, "提示", "请先在上方选中要解除配对的设备")
            return
        data = selected.data(QtCore.Qt.UserRole)
        if not data:
            return
        dev_id, info = data
        name = info.get("name", dev_id)
        if QtWidgets.QMessageBox.question(
            self, "解除信任确认",
            f"确定要解除与终端「{name}」的互联信任？\n解绑后该设备将无法同步数据，必须重新走确认流程。",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        ) == QtWidgets.QMessageBox.Yes:
            self.service.pair_manager.unpair_device(dev_id)
            self._refresh_paired_list()
            self.lbl_sync_result.setText(f"已解绑设备「{name}」")

    # ── 弹窗核验 ─────────────────────────────────────────────────────

    def _show_pair_confirm_dialog(self, pair_req):
        """收到远端配对请求，弹出确认弹窗。"""
        dialog = RhodesPairConfirmDialog(pair_req, self)
        dialog.exec_()
        self._refresh_paired_list()

    # ── 数据同步 ─────────────────────────────────────────────────────

    def _get_target_paired_device(self):
        selected = self.list_paired.currentItem()
        trusted = self.service.pair_manager.get_trusted_devices()
        if not trusted:
            QtWidgets.QMessageBox.warning(self, "无已配对设备", "请先配对连接至少一台移动终端！")
            return None, None
        if selected and selected.data(QtCore.Qt.UserRole):
            dev_id, info = selected.data(QtCore.Qt.UserRole)
            return dev_id, info
        # 默认取第一台
        dev_id = list(trusted.keys())[0]
        return dev_id, trusted[dev_id]

    def _sync_merge_all(self):
        dev_id, info = self._get_target_paired_device()
        if not info:
            return
        ip = info.get("ip")
        port = info.get("port", 23334)
        token = info.get("token")
        name = info.get("name", "移动终端")

        self.lbl_sync_result.setText(f"正在与 {name} 进行全量双向智能合并...")
        self.btn_sync_all.setEnabled(False)

        def merge_worker():
            # 1. 先 Pull 远端合并到本地
            ok1, res1 = self.service.sync_pull(ip, port, token)
            # 2. 再 Push 本地最新合并数据给远端
            ok2, res2 = self.service.sync_push(ip, port, token, mode="replace")
            success = ok1 and ok2
            msg = "双向同步完成！" if success else f"同步中断: {res1 if not ok1 else res2}"
            QtCore.QMetaObject.invokeMethod(
                self, "_on_sync_finished", QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(bool, success), QtCore.Q_ARG(str, msg)
            )

        threading.Thread(target=merge_worker, daemon=True).start()

    def _sync_pull_remote(self):
        dev_id, info = self._get_target_paired_device()
        if not info:
            return
        ip, port, token = info.get("ip"), info.get("port", 23334), info.get("token")
        self.lbl_sync_result.setText("正在从手机拉取数据...")

        def pull_worker():
            ok, res = self.service.sync_pull(ip, port, token)
            QtCore.QMetaObject.invokeMethod(
                self, "_on_sync_finished", QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(bool, ok), QtCore.Q_ARG(str, "拉取并合并成功！" if ok else f"拉取失败: {res}")
            )

        threading.Thread(target=pull_worker, daemon=True).start()

    def _sync_push_remote(self):
        dev_id, info = self._get_target_paired_device()
        if not info:
            return
        ip, port, token = info.get("ip"), info.get("port", 23334), info.get("token")
        self.lbl_sync_result.setText("正在推送电脑学业数据到手机...")

        def push_worker():
            ok, res = self.service.sync_push(ip, port, token, mode="replace")
            QtCore.QMetaObject.invokeMethod(
                self, "_on_sync_finished", QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(bool, ok), QtCore.Q_ARG(str, "推送至手机成功！" if ok else f"推送失败: {res}")
            )

        threading.Thread(target=push_worker, daemon=True).start()

    @QtCore.pyqtSlot(bool, str)
    def _on_sync_finished(self, success, msg):
        self.btn_sync_all.setEnabled(True)
        self.lbl_sync_result.setText(msg)
        self._refresh_data_counts()
        if success:
            QtWidgets.QMessageBox.information(self, "同步成功", f"🎉 {msg}")
        else:
            QtWidgets.QMessageBox.warning(self, "同步失败", f"❌ {msg}")

    # ── 战术快传 ─────────────────────────────────────────────────────

    def _send_text_drop(self):
        text = self.txt_drop_content.text().strip()
        if not text:
            QtWidgets.QMessageBox.warning(self, "提示", "请输入要发送的内容")
            return
        self._do_send_clipboard(text)

    def _send_clipboard_drop(self):
        clipboard = QtWidgets.QApplication.clipboard()
        text = clipboard.text().strip()
        if not text:
            QtWidgets.QMessageBox.warning(self, "提示", "系统剪贴板当前为空")
            return
        self._do_send_clipboard(text)

    def _do_send_clipboard(self, text):
        dev_id, info = self._get_target_paired_device()
        if not info:
            return
        ip, port, token = info.get("ip"), info.get("port", 23334), info.get("token")
        name = info.get("name", "移动终端")

        def send_worker():
            ok = self.service.send_clipboard(ip, port, token, text, title="博士的电脑终端")
            msg = f"已投递至「{name}」！" if ok else "投递失败，请检查手机是否在线。"
            QtCore.QMetaObject.invokeMethod(
                self, "_on_drop_finished", QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(bool, ok), QtCore.Q_ARG(str, msg)
            )

        threading.Thread(target=send_worker, daemon=True).start()

    @QtCore.pyqtSlot(bool, str)
    def _on_drop_finished(self, success, msg):
        self.lbl_sync_result.setText(msg)
        if success:
            QtWidgets.QMessageBox.information(self, "战术快传", f"🚀 {msg}\n手机端悬浮桌宠已弹起气泡并更新剪贴板！")
        else:
            QtWidgets.QMessageBox.warning(self, "快传失败", msg)

    # ── 接收快传与状态感知 ───────────────────────────────────────────

    def _handle_incoming_clipboard(self, text, title):
        """收到手机传来的文本，写入剪贴板并让桌宠提示。"""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(text)
        if self.owner and hasattr(self.owner, "_say"):
            preview = text[:30] + ("…" if len(text) > 30 else "")
            self.owner._say(f"收到来自移动终端的快传：\n「{preview}」\n已自动存入剪贴板！")

    def _handle_data_synced(self, result):
        """远端推送数据到本地后的处理。"""
        self._refresh_data_counts()
        if self.owner and hasattr(self.owner, "_say"):
            self.owner._say("博士，移动终端已为您同步最新的学业日程与便签！")
