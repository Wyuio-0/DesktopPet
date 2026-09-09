
with open("android/app/src/main/java/com/amiya/pet/ui/ChatView.kt", "r", encoding="utf-8") as f:
    text = f.read()
text = text.replace("contentPadding = PaddingValues(16.dp)", "contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 146.dp, bottom = 16.dp)")
with open("android/app/src/main/java/com/amiya/pet/ui/ChatView.kt", "w", encoding="utf-8") as f:
    f.write(text)

