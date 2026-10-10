# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules, collect_data_files
from PyInstaller.building.datastruct import Tree

# edge-tts + its async HTTP stack need their submodules pulled in explicitly.
_tts_imports = (collect_submodules('edge_tts')
                + collect_submodules('aiohttp')
                + ['certifi'])

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('app.ico', '.'), ('web/static', 'web/static')],
    hiddenimports=['cv2', 'PyQt5.QtMultimedia'] + _tts_imports + ['psutil', 'PIL.ImageGrab', 'fitz', 'pymupdf', 'pypdf', 'docx', 'pptx', 'pet.ocr', 'pet.memory', 'pet.ai_settings', 'pet.theme', 'pet.timers', 'pet.tray', 'pet.menu', 'pet.focus', 'pet.input_controller', 'pet.wander', 'pet.sedentary', 'pet.profile', 'pet.profile_ui', 'pet.weather', 'pet.music', 'pet.notes', 'pet.notes_ui', 'pet.sync_service', 'pet.sync_ui', 'pet.schedule_dialogs', 'pet.knowledge', 'pet.notebook_lm', 'pet.web_launcher', 'web.server', 'pet.single_instance'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 必须显式排除：本项目的运行依赖只有 requirements.txt 里那几个
    # （PyQt5 / opencv / numpy / edge-tts / psutil / Pillow / pymupdf / pypdf）。但如果在**共享的全局
    # 解释器**下打包（例如 D:\Python 同时装了 GPT-SoVITS 那套 torch 环境），
    # PyInstaller 会顺着 import链把 torch / scipy / matplotlib 整套拖进来：
    # dist 从 ~200 MB 膨胀到 883 MB，Analysis 阶段光遍历 torch 目录树就要 3~5 分钟
    # （看起来像卡死，实际是在啃磁盘）。这些包桌宠一个都不 import。
    # 语音克隆是**独立进程**（D:\Dev\voiceclone\serve.py，走 HTTP 9881），
    # 不在本 exe 内，所以排除 torch 不影响声线功能。
    # onnxruntime 和 rapidocr 采用 build.ps1 直接同步至 _internal 规避 PyInstaller 二进制分析时的 Qt5 冲突。
    excludes=[
        'torch', 'torchaudio', 'torchvision',   # 语音克隆走独立进程，不进 exe
        'scipy', 'matplotlib', 'pandas',
        'tkinter', 'IPython', 'jupyter', 'notebook', 'traitlets',
        'transformers', 'tensorboard', 'sympy', 'numba', 'llvmlite',
        'win32com', 'pythoncom', 'pywintypes',
        'pygame', 'sklearn', 'sentence_transformers',
        'onnxruntime', 'rapidocr_onnxruntime', 'shapely', 'pyclipper', 'flatbuffers',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# 角色素材**不**打进 _internal：onedir 发布时角色放在 exe 旁的 characters\，
# 由 build.ps1（本地）或 CI 的 "Sync characters" 步骤同步——全链路只保留
# 一份，安装包/zip 不再重复携带两倍素材。ai_config.json / .claude 由同步
# 步骤一并剔除。

# onedir 打包：DLL 就地加载，规避 onefile 解压后 Qt5Core.dll 加载崩溃
# （0xc0000409）。发布时把整个 dist/DesktopPet/ 目录打成 zip。
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DesktopPet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='DesktopPet',
)
