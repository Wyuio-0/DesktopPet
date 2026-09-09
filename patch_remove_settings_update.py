
import re

with open("android/app/src/main/java/com/amiya/pet/ui/ChatView.kt", "r", encoding="utf-8") as f:
    text = f.read()

pattern = re.compile(r"val context = LocalContext\.current\s+var isChecking by remember \{ mutableStateOf\(false\) \}\s+Button\([^}]+?\}\s+\}\s+\},\s+modifier = Modifier\.fillMaxWidth\(\),\s+colors = ButtonDefaults\.buttonColors[^}]+?\}", re.DOTALL)
text = pattern.sub("", text)

with open("android/app/src/main/java/com/amiya/pet/ui/ChatView.kt", "w", encoding="utf-8") as f:
    f.write(text)

