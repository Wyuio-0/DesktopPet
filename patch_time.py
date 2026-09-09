
import re

# Update Android
android_path = "android/app/src/main/java/com/amiya/pet/core/schedule/ScheduleManager.kt"
with open(android_path, "r", encoding="utf-8") as f:
    android_text = f.read()

android_text = android_text.replace(
    "\"6\" to \"14:00\", \"7\" to \"14:50\", \"8\" to \"15:40\", \"9\" to \"16:30\"",
    "\"6\" to \"14:05\", \"7\" to \"14:55\", \"8\" to \"15:45\", \"9\" to \"16:35\""
)

with open(android_path, "w", encoding="utf-8") as f:
    f.write(android_text)

# Update PC
pc_path = "pet/schedule.py"
with open(pc_path, "r", encoding="utf-8") as f:
    pc_text = f.read()

pc_text = pc_text.replace(
    "\"6\": \"14:00\", \"7\": \"14:50\", \"8\": \"15:40\", \"9\": \"16:30\"",
    "\"6\": \"14:05\", \"7\": \"14:55\", \"8\": \"15:45\", \"9\": \"16:35\""
)

with open(pc_path, "w", encoding="utf-8") as f:
    f.write(pc_text)

