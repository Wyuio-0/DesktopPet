
import re

# CHANGELOG.md
with open("CHANGELOG.md", "r", encoding="utf-8") as f:
    changelog = f.read()
changelog = "## [v1.8.1]\n- 修改下午课程默认时间，第六节课调整为14:05开始。\n\n" + changelog
with open("CHANGELOG.md", "w", encoding="utf-8") as f:
    f.write(changelog)

# android/app/build.gradle.kts
with open("android/app/build.gradle.kts", "r", encoding="utf-8") as f:
    gradle = f.read()
gradle = re.sub(r"versionCode = \d+", "versionCode = 181", gradle)
gradle = re.sub(r"versionName = \".*?\"", "versionName = \"1.8.1\"", gradle)
with open("android/app/build.gradle.kts", "w", encoding="utf-8") as f:
    f.write(gradle)

# pet/updater.py
with open("pet/updater.py", "r", encoding="utf-8") as f:
    updater = f.read()
updater = re.sub(r"CURRENT_VERSION = \".*?\"", "CURRENT_VERSION = \"1.8.1\"", updater)
with open("pet/updater.py", "w", encoding="utf-8") as f:
    f.write(updater)

