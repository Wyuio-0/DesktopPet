"""First-run introduction using local character assets; no network required."""
import glob
import os
import sys

from PyQt5 import QtCore, QtMultimedia, QtWidgets

from . import theme
from .character import Character
from .voice import VoicePlayer


def available_characters(roots):
    """Match launcher precedence, ignoring malformed optional characters."""
    found = {}
    for root in roots:
        for path in sorted(glob.glob(os.path.join(root, '*', 'config.json'))):
            key = os.path.basename(os.path.dirname(path))
            if key in found:
                continue
            try:
                found[key] = Character(os.path.dirname(path))
            except (OSError, ValueError, TypeError, KeyError):
                continue
    return list(found.values())


class WelcomeDialog(QtWidgets.QDialog):
    def __init__(self, characters, selected_path, prefs, parent=None):
        super().__init__(parent)
        self.characters = characters
        self.prefs = prefs
        self.preview = None
        self.setWindowTitle('欢迎使用桌面宠物')
        self.setMinimumWidth(460)
        self.setStyleSheet(theme.DIALOG_QSS)
        layout = QtWidgets.QVBoxLayout(self)
        self.title = QtWidgets.QLabel('1 / 2 · 认识你的伙伴')
        layout.addWidget(self.title)
        self.pages = QtWidgets.QStackedWidget()
        layout.addWidget(self.pages)
        first = QtWidgets.QWidget()
        form = QtWidgets.QVBoxLayout(first)
        form.addWidget(QtWidgets.QLabel('选一个喜欢的角色，之后也可以在右键菜单中切换。'))
        self.character_box = QtWidgets.QComboBox()
        for char in characters:
            self.character_box.addItem(char.display_name, char.dir)
        index = self.character_box.findData(selected_path)
        self.character_box.setCurrentIndex(max(0, index))
        form.addWidget(self.character_box)
        self.sound = QtWidgets.QCheckBox('开启角色语音')
        self.sound.setChecked(bool(prefs.get('voice_enabled', True)))
        form.addWidget(self.sound)
        self.volume = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(round(float(prefs.get('volume', .7)) * 100))
        form.addWidget(QtWidgets.QLabel('语音音量'))
        form.addWidget(self.volume)
        self.listen = QtWidgets.QPushButton('试听角色声音')
        self.listen.clicked.connect(self.play_preview)
        form.addWidget(self.listen)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        form.addWidget(self.status)
        form.addStretch()
        self.pages.addWidget(first)
        second = QtWidgets.QWidget()
        box = QtWidgets.QVBoxLayout(second)
        shortcut = '\nWindows 还可以按角色配置的聊天快捷键（默认 Alt+A）。' if sys.platform == 'win32' else ''
        instructions = QtWidgets.QLabel('拖动角色可以移动；双击角色或右键选择“聊天”开始对话。'
            + shortcut + '\n输入后按回车发送，Esc 关闭输入框。\n\n先打个招呼吧，这次体验在本地完成，不会发送到网络。')
        instructions.setWordWrap(True)
        box.addWidget(instructions)
        self.greet = QtWidgets.QPushButton('你好，很高兴认识你！')
        self.greet.clicked.connect(self.say_hello)
        box.addWidget(self.greet)
        self.reply = QtWidgets.QLabel()
        self.reply.setWordWrap(True)
        self.reply.setTextFormat(QtCore.Qt.PlainText)
        box.addWidget(self.reply)
        note = QtWidgets.QLabel('正式聊天可能使用公共 AI 线路或你配置的模型，消息会发送到相应服务。\n模型、课程表和其他设置都可以稍后再配。')
        note.setWordWrap(True)
        box.addWidget(note)
        box.addStretch()
        self.pages.addWidget(second)
        buttons = QtWidgets.QHBoxLayout()
        skip = QtWidgets.QPushButton('稍后再说')
        skip.clicked.connect(self.reject)
        buttons.addWidget(skip)
        buttons.addStretch()
        self.back = QtWidgets.QPushButton('上一步')
        self.back.clicked.connect(lambda: self.set_page(0))
        buttons.addWidget(self.back)
        self.next = QtWidgets.QPushButton()
        self.next.clicked.connect(self.advance)
        buttons.addWidget(self.next)
        layout.addLayout(buttons)
        self.character_box.currentIndexChanged.connect(self.change_character)
        self.sound.toggled.connect(self.update_audio)
        self.volume.valueChanged.connect(self.update_audio)
        self.change_character()
        self.set_page(0)

    @property
    def selected_path(self):
        return self.character_box.currentData()

    def change_character(self):
        if self.preview:
            self.preview.stop()
        self.preview = VoicePlayer(self.selected_path, self.volume.value() / 100, self.sound.isChecked())
        self.preview._player.error.connect(self.audio_error)
        self.reply.clear()
        self.update_audio()

    def update_audio(self):
        if self.preview:
            self.preview.set_enabled(self.sound.isChecked())
            self.preview.set_volume(self.volume.value() / 100)
        has_audio = bool(self.preview and self.preview.has('all'))
        self.listen.setEnabled(has_audio and self.sound.isChecked() and self.volume.value() > 0)
        if not has_audio:
            self.status.setText('这个角色没有本地语音，仍可正常使用。')
        elif not self.sound.isChecked():
            self.status.setText('语音已关闭；勾选“开启角色语音”后可试听。')
        elif self.volume.value() == 0:
            self.status.setText('当前音量为零，调高音量后可试听。')
        else:
            self.status.setText('点击试听，可随时调整音量。')

    def audio_error(self, *_):
        self.status.setText('声音播放失败，请检查音频设备；你可以继续完成引导。')

    def play_preview(self):
        self.preview.play('all')
        self.status.setText('正在试听；没有听到声音时，请检查音量和音频设备。')

    def set_page(self, index):
        self.preview.stop()
        self.pages.setCurrentIndex(index)
        self.title.setText('1 / 2 · 认识你的伙伴' if index == 0 else '2 / 2 · 开始第一次互动')
        self.back.setVisible(index == 1)
        self.next.setText('下一步' if index == 0 else '完成，开始聊天')
        self.next.setEnabled(index == 0 or bool(self.reply.text()))

    def say_hello(self):
        name = self.character_box.currentText()
        self.reply.setText(f'{name}：你好，博士！很高兴认识你，以后请多关照。\n\n已经学会第一次互动了，接下来试试自由聊天吧。')
        self.next.setEnabled(True)

    def advance(self):
        if self.pages.currentIndex() == 0:
            self.set_page(1)
        else:
            self.prefs.set('character', os.path.basename(self.selected_path))
            self.prefs.set('voice_enabled', self.sound.isChecked())
            self.prefs.set('volume', self.volume.value() / 100)
            self.prefs.set('onboarding_completed', True)
            self.accept()

    def done(self, result):
        if self.preview:
            self.preview.stop()
        super().done(result)
