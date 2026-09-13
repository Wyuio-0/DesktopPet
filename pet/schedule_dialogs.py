"""课程详情与编辑弹窗（对齐手机端交互体验）。"""

from PyQt5 import QtCore, QtGui, QtWidgets

from . import theme
from .schedule import Course, WEEKDAY_NAMES, _PARITY_LABEL


DIALOG_QSS = """
QFrame#DialogRoot {
    background: #14171C;
    border: 1px solid #2D3748;
    border-radius: 12px;
}
QLabel {
    color: #E2E8F0;
    font-size: 13px;
    font-family: 'Microsoft YaHei UI', 'Microsoft YaHei', 'Segoe UI';
}
QLineEdit, QSpinBox, QComboBox {
    background: #1E2430;
    color: #F8FAFC;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    selection-background-color: #00B0FF;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #00B0FF;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background: #1E2430;
    color: #F8FAFC;
    border: 1px solid #334155;
    selection-background-color: #00B0FF;
    selection-color: #FFFFFF;
}
QPushButton {
    background: #2A3342;
    color: #E2E8F0;
    border: 1px solid #3B485E;
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton:hover {
    background: #374459;
    border-color: #4B5E7D;
}
QPushButton#PrimaryBtn {
    background: #00B0FF;
    color: #FFFFFF;
    border: 1px solid #0091EA;
    font-weight: bold;
}
QPushButton#PrimaryBtn:hover {
    background: #40C4FF;
}
QPushButton#DangerBtn {
    background: #2D1A1F;
    color: #FF5252;
    border: 1px solid #7F1D1D;
}
QPushButton#DangerBtn:hover {
    background: #4C1D24;
    color: #FF8A80;
}
"""


class CourseDetailDialog(QtWidgets.QDialog):
    """课程详情弹窗（查看课程全量信息、支持编辑、删除或让阿米娅分析）。"""

    sig_edit_requested = QtCore.pyqtSignal(object)
    sig_delete_requested = QtCore.pyqtSignal(object)
    sig_ask_ai = QtCore.pyqtSignal(str)

    def __init__(self, course, color=None, sections=None, parent=None):
        super().__init__(parent)
        self.course = course
        self.color = color or QtGui.QColor("#00B0FF")
        self.sections = sections or {}
        self.setWindowTitle("课程详情")
        self.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(420)
        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QFrame(self)
        root.setObjectName("DialogRoot")
        root.setStyleSheet(DIALOG_QSS)
        root_lay = QtWidgets.QVBoxLayout(root)
        root_lay.setContentsMargins(22, 18, 22, 22)
        root_lay.setSpacing(14)

        # 顶栏：色块指示条 + 标题 + 关闭按钮
        head_lay = QtWidgets.QHBoxLayout()
        color_dot = QtWidgets.QFrame(root)
        color_dot.setFixedSize(5, 20)
        color_dot.setStyleSheet(f"background: {self.color.name()}; border-radius: 2px;")
        head_lay.addWidget(color_dot)

        title_lbl = QtWidgets.QLabel("课程详情", root)
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #94A3B8;")
        head_lay.addWidget(title_lbl)
        head_lay.addStretch(1)

        close_btn = QtWidgets.QPushButton("✕", root)
        close_btn.setFixedSize(26, 26)
        close_btn.setStyleSheet("border:none; font-size: 15px; color: #94A3B8; background: transparent;")
        close_btn.clicked.connect(self.reject)
        head_lay.addWidget(close_btn)
        root_lay.addLayout(head_lay)

        # 课程大标题
        name_lbl = QtWidgets.QLabel(self.course.name, root)
        name_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF;")
        name_lbl.setWordWrap(True)
        root_lay.addWidget(name_lbl)

        # 详情条目卡片
        info_card = QtWidgets.QFrame(root)
        info_card.setStyleSheet("background: #1A1F29; border-radius: 8px;")
        card_lay = QtWidgets.QVBoxLayout(info_card)
        card_lay.setContentsMargins(14, 12, 14, 12)
        card_lay.setSpacing(10)

        # 1. 时间
        wd_str = WEEKDAY_NAMES.get(self.course.weekday, f"周{self.course.weekday}")
        t_start = self.sections.get(str(self.course.sec_start), "")
        t_end = self.sections.get(str(self.course.sec_end), "")
        time_span = f" ({t_start} - {t_end})" if t_start and t_end else ""
        self._add_row(card_lay, "⏰ 上课时间", f"{wd_str} 第 {self.course.sec_start}-{self.course.sec_end} 节{time_span}")

        # 2. 周次与单双周
        parity_str = {"all": "全部周", "odd": "仅单周", "even": "仅双周"}.get(self.course.parity, "全部周")
        self._add_row(card_lay, "📅 教学周次", f"第 {self.course.week_start}-{self.course.week_end} 周 ({parity_str})")

        # 3. 教室
        room_str = self.course.room if self.course.room else "未指定教室"
        self._add_row(card_lay, "📍 上课教室", room_str)

        # 4. 教师
        teacher_str = self.course.teacher if self.course.teacher else "未指定教师"
        self._add_row(card_lay, "👤 任课教师", teacher_str)

        # 5. 校区
        if self.course.campus:
            self._add_row(card_lay, "🏫 所在校区", self.course.campus)

        # 6. 备注
        if self.course.note:
            self._add_row(card_lay, "📝 课程备注", self.course.note)

        root_lay.addWidget(info_card)

        # 底部操作按钮栏
        btn_lay = QtWidgets.QHBoxLayout()
        btn_lay.setSpacing(10)

        del_btn = QtWidgets.QPushButton("🗑 删除", root)
        del_btn.setObjectName("DangerBtn")
        del_btn.clicked.connect(self._on_delete)
        btn_lay.addWidget(del_btn)

        edit_btn = QtWidgets.QPushButton("✏ 编辑", root)
        edit_btn.clicked.connect(self._on_edit)
        btn_lay.addWidget(edit_btn)

        ai_btn = QtWidgets.QPushButton("✨ 咨询阿米娅", root)
        ai_btn.setObjectName("PrimaryBtn")
        ai_btn.clicked.connect(self._on_ask_ai)
        btn_lay.addWidget(ai_btn)

        root_lay.addLayout(btn_lay)

        # 弹窗主布局
        dlg_lay = QtWidgets.QVBoxLayout(self)
        dlg_lay.setContentsMargins(0, 0, 0, 0)
        dlg_lay.addWidget(root)

    def _add_row(self, layout, label, value):
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        lbl = QtWidgets.QLabel(label)
        lbl.setStyleSheet("color: #94A3B8; font-size: 13px; min-width: 80px;")
        val = QtWidgets.QLabel(value)
        val.setStyleSheet("color: #F1F5F9; font-size: 13px; font-weight: 500;")
        val.setWordWrap(True)
        row.addWidget(lbl)
        row.addWidget(val, 1)
        layout.addLayout(row)

    def _on_edit(self):
        self.accept()
        self.sig_edit_requested.emit(self.course)

    def _on_delete(self):
        msg = QtWidgets.QMessageBox(
            QtWidgets.QMessageBox.Question,
            "删除确认",
            f"确定要删除课程《{self.course.name}》吗？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            self
        )
        msg.setStyleSheet(DIALOG_QSS)
        if msg.exec_() == QtWidgets.QMessageBox.Yes:
            self.accept()
            self.sig_delete_requested.emit(self.course)

    def _on_ask_ai(self):
        self.accept()
        prompt = (f"阿米娅，我想咨询一下课程《{self.course.name}》（教室：{self.course.room or '待定'}，"
                  f"教师：{self.course.teacher or '待定'}）的备考与学习规划建议！")
        self.sig_ask_ai.emit(prompt)


class CourseEditDialog(QtWidgets.QDialog):
    """添加或编辑课程弹窗。"""

    def __init__(self, course=None, default_weekday=1, default_sec=1, parent=None):
        super().__init__(parent)
        self.editing_course = course
        self.result_course = None
        self.setWindowTitle("编辑课程" if course else "添加课程")
        self.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(460)
        self._default_wd = default_weekday
        self._default_sec = default_sec
        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QFrame(self)
        root.setObjectName("DialogRoot")
        root.setStyleSheet(DIALOG_QSS)
        root_lay = QtWidgets.QVBoxLayout(root)
        root_lay.setContentsMargins(24, 20, 24, 24)
        root_lay.setSpacing(12)

        # 顶栏
        head_lay = QtWidgets.QHBoxLayout()
        title_text = "编辑课程" if self.editing_course else "添加新课程"
        title_lbl = QtWidgets.QLabel(title_text, root)
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        head_lay.addWidget(title_lbl)
        head_lay.addStretch(1)

        close_btn = QtWidgets.QPushButton("✕", root)
        close_btn.setFixedSize(26, 26)
        close_btn.setStyleSheet("border:none; font-size: 15px; color: #94A3B8; background: transparent;")
        close_btn.clicked.connect(self.reject)
        head_lay.addWidget(close_btn)
        root_lay.addLayout(head_lay)

        # 表单
        form = QtWidgets.QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        # 1. 课程名称
        self.name_edit = QtWidgets.QLineEdit(root)
        self.name_edit.setPlaceholderText("例如: 概率论与数理统计")
        if self.editing_course:
            self.name_edit.setText(self.editing_course.name)
        form.addRow("课程名称 *", self.name_edit)

        # 2. 星期
        self.wd_combo = QtWidgets.QComboBox(root)
        for i in range(1, 8):
            self.wd_combo.addItem(WEEKDAY_NAMES.get(i, f"周{i}"), i)
        cur_wd = self.editing_course.weekday if self.editing_course else self._default_wd
        self.wd_combo.setCurrentIndex(max(0, min(6, cur_wd - 1)))
        form.addRow("上课星期", self.wd_combo)

        # 3. 节次区间
        sec_lay = QtWidgets.QHBoxLayout()
        self.sec_start_combo = QtWidgets.QComboBox(root)
        self.sec_end_combo = QtWidgets.QComboBox(root)
        for i in range(1, 14):
            self.sec_start_combo.addItem(f"第 {i} 节", i)
            self.sec_end_combo.addItem(f"第 {i} 节", i)
        cur_s1 = self.editing_course.sec_start if self.editing_course else self._default_sec
        cur_s2 = self.editing_course.sec_end if self.editing_course else min(13, cur_s1 + 1)
        self.sec_start_combo.setCurrentIndex(cur_s1 - 1)
        self.sec_end_combo.setCurrentIndex(cur_s2 - 1)
        sec_lay.addWidget(self.sec_start_combo)
        sec_lay.addWidget(QtWidgets.QLabel("至"))
        sec_lay.addWidget(self.sec_end_combo)
        form.addRow("上课节次", sec_lay)

        # 4. 周次区间
        week_lay = QtWidgets.QHBoxLayout()
        self.w_start_spin = QtWidgets.QSpinBox(root)
        self.w_start_spin.setRange(1, 30)
        self.w_end_spin = QtWidgets.QSpinBox(root)
        self.w_end_spin.setRange(1, 30)
        self.w_start_spin.setValue(self.editing_course.week_start if self.editing_course else 1)
        self.w_end_spin.setValue(self.editing_course.week_end if self.editing_course else 16)
        week_lay.addWidget(self.w_start_spin)
        week_lay.addWidget(QtWidgets.QLabel("周 至"))
        week_lay.addWidget(self.w_end_spin)
        week_lay.addWidget(QtWidgets.QLabel("周"))
        form.addRow("教学周次", week_lay)

        # 5. 单双周
        self.parity_combo = QtWidgets.QComboBox(root)
        self.parity_combo.addItem("每周 (全部周)", "all")
        self.parity_combo.addItem("仅单周", "odd")
        self.parity_combo.addItem("仅双周", "even")
        if self.editing_course:
            idx = {"all": 0, "odd": 1, "even": 2}.get(self.editing_course.parity, 0)
            self.parity_combo.setCurrentIndex(idx)
        form.addRow("单双周", self.parity_combo)

        # 6. 上课教室
        self.room_edit = QtWidgets.QLineEdit(root)
        self.room_edit.setPlaceholderText("例如: 理学楼-401")
        if self.editing_course:
            self.room_edit.setText(self.editing_course.room)
        form.addRow("上课教室", self.room_edit)

        # 7. 任课教师
        self.teacher_edit = QtWidgets.QLineEdit(root)
        self.teacher_edit.setPlaceholderText("例如: 凯尔希")
        if self.editing_course:
            self.teacher_edit.setText(self.editing_course.teacher)
        form.addRow("任课教师", self.teacher_edit)

        # 8. 校区与备注
        self.campus_edit = QtWidgets.QLineEdit(root)
        self.campus_edit.setPlaceholderText("例如: 本部校区")
        if self.editing_course:
            self.campus_edit.setText(self.editing_course.campus)
        form.addRow("所属校区", self.campus_edit)

        self.note_edit = QtWidgets.QLineEdit(root)
        self.note_edit.setPlaceholderText("例如: 实验 / 选修")
        if self.editing_course:
            self.note_edit.setText(self.editing_course.note)
        form.addRow("课程备注", self.note_edit)

        root_lay.addLayout(form)

        # 底部按钮
        btn_lay = QtWidgets.QHBoxLayout()
        btn_lay.addStretch(1)

        cancel_btn = QtWidgets.QPushButton("取消", root)
        cancel_btn.clicked.connect(self.reject)
        btn_lay.addWidget(cancel_btn)

        save_btn = QtWidgets.QPushButton("✓ 保存课程", root)
        save_btn.setObjectName("PrimaryBtn")
        save_btn.clicked.connect(self._on_save)
        btn_lay.addWidget(save_btn)

        root_lay.addLayout(btn_lay)

        # 主布局
        dlg_lay = QtWidgets.QVBoxLayout(self)
        dlg_lay.setContentsMargins(0, 0, 0, 0)
        dlg_lay.addWidget(root)

    def _on_save(self):
        name = self.name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "提示", "请输入课程名称！")
            return

        s1 = self.sec_start_combo.currentData()
        s2 = self.sec_end_combo.currentData()
        if s2 < s1:
            QtWidgets.QMessageBox.warning(self, "提示", "结束节次不能小于开始节次！")
            return

        w1 = self.w_start_spin.value()
        w2 = self.w_end_spin.value()
        if w2 < w1:
            QtWidgets.QMessageBox.warning(self, "提示", "结束周次不能小于开始周次！")
            return

        wd = self.wd_combo.currentData()
        parity = self.parity_combo.currentData()
        room = self.room_edit.text().strip()
        teacher = self.teacher_edit.text().strip()
        campus = self.campus_edit.text().strip()
        note = self.note_edit.text().strip()

        self.result_course = Course(
            name=name,
            weekday=wd,
            sec_start=s1,
            sec_end=s2,
            week_start=w1,
            week_end=w2,
            parity=parity,
            room=room,
            teacher=teacher,
            campus=campus,
            note=note
        )
        self.accept()
