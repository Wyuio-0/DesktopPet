
import re

# 1. Update android build.gradle.kts
gradle_path = "android/app/build.gradle.kts"
with open(gradle_path, "r", encoding="utf-8") as f:
    gradle = f.read()
gradle = re.sub(r"versionCode\s*=\s*\d+", "versionCode = 9", gradle)
gradle = re.sub(r"versionName\s*=\s*\".*?\"", "versionName = \"1.8.0\"", gradle)
with open(gradle_path, "w", encoding="utf-8") as f:
    f.write(gradle)

# 2. Update pet/updater.py
updater_path = "pet/updater.py"
with open(updater_path, "r", encoding="utf-8") as f:
    updater = f.read()
updater = re.sub(r"APP_VERSION\s*=\s*\".*?\"", "APP_VERSION = \"1.8.0\"", updater)
with open(updater_path, "w", encoding="utf-8") as f:
    f.write(updater)

# 3. Update CHANGELOG.md
changelog_path = "CHANGELOG.md"
with open(changelog_path, "r", encoding="utf-8") as f:
    changelog = f.read()

new_log = """## [1.8.0] - 2026-09-08

### ✨ 手机端重大架构升级
- **内置对话融合**：彻底剥离了全局悬浮窗权限限制，现在阿米娅将直接无缝显示在「对话」界面顶部，交互更沉浸！
- **免悬浮窗权限**：新用户下载应用后无需再去系统设置里繁琐地授予“显示在其他应用上层”权限。
- **全局设置整合**：桌面端的音量、倍速、角色切换现已全部整合进对话页面的设置按钮中。
- **自适应一屏课表**：课表界面等比自适应屏幕高度，无需滑动即可纵览全天课程。
- **课表时间快捷切换**：点按左侧课表节数，即可一键将节次号切换为具体的上课时间。

"""

changelog = changelog.replace("# 更新日志\n\n", "# 更新日志\n\n" + new_log)
with open(changelog_path, "w", encoding="utf-8") as f:
    f.write(changelog)

