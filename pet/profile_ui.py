"""博士档案本管理界面：可视化查看、编辑与管理阿米娅的长程记忆。"""

from PyQt5 import QtCore, QtWidgets

from . import theme
from .profile import get_doctor_profile


class DoctorProfileDialog(QtWidgets.QDialog):
    """博士档案本对话框：编辑基本资料 + 随记条目查看与删改。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("博士档案本（阿米娅的备忘录）")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.resize(600, 680)
        self.setStyleSheet(theme.DIALOG_QSS)
        self.profile = get_doctor_profile()
        self._build()
        self._load()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        head = QtWidgets.QLabel("DOCTOR PROFILE", self)
        head.setObjectName("TerminalTitle")
        root.addWidget(head)

        sub = QtWidgets.QLabel(
            "阿米娅用心记下的关于博士的个人偏好、作息习惯与长程随记。\n"
            "在与博士日常交谈时，阿米娅会自然融入这些记忆，越聊越懂您。", self)
        sub.setObjectName("TerminalSubTitle")
        sub.setWordWrap(True)
        root.addWidget(sub)

        # ── 基础档案表单 ──────────────────────────────────────────
        group_box = QtWidgets.QGroupBox("基础个人档案", self)
        form = QtWidgets.QFormLayout(group_box)
        form.setContentsMargins(12, 14, 12, 14)
        form.setSpacing(10)

        self.edit_nickname = QtWidgets.QLineEdit(group_box)
        self.edit_nickname.setPlaceholderText("阿米娅对您的称呼（默认：博士）")

        self.edit_identity = QtWidgets.QLineEdit(group_box)
        self.edit_identity.setPlaceholderText("如 计算机系研究生、软件工程师、罗德岛指挥官")

        self.edit_preferences = QtWidgets.QLineEdit(group_box)
        self.edit_preferences.setPlaceholderText("如 喜欢无糖乌龙茶、爱喝冰美式、偏好VSCode")

        self.edit_habits = QtWidgets.QLineEdit(group_box)
        self.edit_habits.setPlaceholderText("如 习惯熬夜写代码、常在晚上专注、爱用番茄工作法")

        self.edit_goals = QtWidgets.QLineEdit(group_box)
        self.edit_goals.setPlaceholderText("如 备考考研408、准备下周三答辩、复习六级词汇")

        form.addRow("专属称呼", self.edit_nickname)
        form.addRow("身份/阶段", self.edit_identity)
        form.addRow("喜好与偏好", self.edit_preferences)
        form.addRow("作息与习惯", self.edit_habits)
        form.addRow("当前重心与目标", self.edit_goals)
        root.addWidget(group_box)

        # ── 长程记忆与随记列表 ──────────────────────────────────────
        mem_group = QtWidgets.QGroupBox("长程记忆与随记事项", self)
        mem_layout = QtWidgets.QVBoxLayout(mem_group)
        mem_layout.setContentsMargins(12, 14, 12, 14)
        mem_layout.setSpacing(8)

        self.lbl_mem_count = QtWidgets.QLabel(mem_group)
        mem_layout.addWidget(self.lbl_mem_count)

        self.list_memories = QtWidgets.QListWidget(mem_group)
        self.list_memories.setAlternatingRowColors(True)
        self.list_memories.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        mem_layout.addWidget(self.list_memories, 1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_add_mem = QtWidgets.QPushButton("添加记忆…", mem_group)
        self.btn_del_mem = QtWidgets.QPushButton("删除选中", mem_group)
        self.btn_clear_mem = QtWidgets.QPushButton("清空随记", mem_group)
        self.btn_add_mem.clicked.connect(self._on_add_memory)
        self.btn_del_mem.clicked.connect(self._on_del_memory)
        self.btn_clear_mem.clicked.connect(self._on_clear_memories)

        btn_row.addWidget(self.btn_add_mem)
        btn_row.addWidget(self.btn_del_mem)
        btn_row.addWidget(self.btn_clear_mem)
        btn_row.addStretch(1)
        mem_layout.addLayout(btn_row)

        root.addWidget(mem_group, 1)

        # ── 底部操作按钮 ──────────────────────────────────────────
        action_row = QtWidgets.QHBoxLayout()
        action_row.setSpacing(10)
        self.btn_save = QtWidgets.QPushButton("保存档案", self)
        self.btn_save.setObjectName("PrimaryButton")
        self.btn_save.clicked.connect(self._on_save)

        self.btn_cancel = QtWidgets.QPushButton("取消", self)
        self.btn_cancel.clicked.connect(self.reject)

        action_row.addStretch(1)
        action_row.addWidget(self.btn_save)
        action_row.addWidget(self.btn_cancel)
        root.addLayout(action_row)

    def _load(self):
        self.profile.load()
        self.edit_nickname.setText(self.profile.nickname or "博士")
        self.edit_identity.setText(self.profile.identity or "")
        self.edit_preferences.setText(self.profile.preferences or "")
        self.edit_habits.setText(self.profile.habits or "")
        self.edit_goals.setText(self.profile.goals or "")
        self._refresh_memories()

    def _refresh_memories(self):
        self.list_memories.clear()
        mems = self.profile.memories
        self.lbl_mem_count.setText(f"阿米娅已记下的随记与重要事项（共 {len(mems)} 条）：")
        if not mems:
            item = QtWidgets.QListWidgetItem("（暂无随记。聊天时提到重要事情阿米娅会自动记下，您也可以点击下方按钮手动添加）")
            item.setFlags(QtCore.Qt.NoItemFlags)
            self.list_memories.addItem(item)
            return

        for m in reversed(mems):  # 最新记忆在上方
            text = f"[{m['time']}] {m['content']}"
            item = QtWidgets.QListWidgetItem(text)
            item.setData(QtCore.Qt.UserRole, m["id"])
            self.list_memories.addItem(item)

    def _on_add_memory(self):
        text, ok = QtWidgets.QInputDialog.getText(
            self, "添加长程记忆", "请输入希望阿米娅长久记住的事项：",
            QtWidgets.QLineEdit.Normal, ""
        )
        if ok and text.strip():
            self.profile.add_memory(text.strip())
            self._refresh_memories()

    def _on_del_memory(self):
        curr = self.list_memories.currentItem()
        if not curr:
            return
        mem_id = curr.data(QtCore.Qt.UserRole)
        if not mem_id:
            return
        self.profile.delete_memory(mem_id)
        self._refresh_memories()

    def _on_clear_memories(self):
        if not self.profile.memories:
            return
        res = QtWidgets.QMessageBox.question(
            self, "确认清空", "确定要清空阿米娅记下的所有随记事项吗？\n（基础档案资料不会被清除）",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        if res == QtWidgets.QMessageBox.Yes:
            self.profile.clear_memories()
            self._refresh_memories()

    def _on_save(self):
        self.profile.nickname = self.edit_nickname.text().strip() or "博士"
        self.profile.identity = self.edit_identity.text().strip()
        self.profile.preferences = self.edit_preferences.text().strip()
        self.profile.habits = self.edit_habits.text().strip()
        self.profile.goals = self.edit_goals.text().strip()
        self.profile.save()
        self.accept()
