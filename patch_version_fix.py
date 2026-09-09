
import re

# android/app/build.gradle.kts
with open("android/app/build.gradle.kts", "r", encoding="utf-8") as f:
    gradle = f.read()
gradle = re.sub(r"versionCode = \d+", "versionCode = 184", gradle)
gradle = re.sub(r"versionName = \".*?\"", "versionName = \"1.8.4\"", gradle)
with open("android/app/build.gradle.kts", "w", encoding="utf-8") as f:
    f.write(gradle)

# pet/updater.py
with open("pet/updater.py", "r", encoding="utf-8") as f:
    updater = f.read()
updater = re.sub(r"CURRENT_VERSION = \".*?\"", "CURRENT_VERSION = \"1.8.4\"", updater)
with open("pet/updater.py", "w", encoding="utf-8") as f:
    f.write(updater)

