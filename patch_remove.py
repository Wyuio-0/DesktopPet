
import re

with open("android/app/src/main/java/com/amiya/pet/ui/ChatView.kt", "r", encoding="utf-8") as f:
    text = f.read()

pattern = re.compile(r"\s+val context = LocalContext\.current\s+var isChecking by remember \{ mutableStateOf\(false\) \}\s+Button\(.*?\)\s+\{.*?Text\(if \(isChecking\).*?\}\n", re.DOTALL)
text = pattern.sub("\n", text)

with open("android/app/src/main/java/com/amiya/pet/ui/ChatView.kt", "w", encoding="utf-8") as f:
    f.write(text)

