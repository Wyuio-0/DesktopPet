
import re
with open("app/src/main/AndroidManifest.xml", "r", encoding="utf-8") as f:
    text = f.read()

text = re.sub(r"<!-- 悬浮窗显示在其他应用上层 -->\s*<uses-permission android:name=\"android\.permission\.SYSTEM_ALERT_WINDOW\" />", "", text)
text = text.replace(".service.PetFloatingService", ".service.AppBackgroundService")
text = text.replace("Desktop pet interactive overlay and character animation rendering", "Schedule reminders and Pomodoro timer background checks")

with open("app/src/main/AndroidManifest.xml", "w", encoding="utf-8") as f:
    f.write(text)

