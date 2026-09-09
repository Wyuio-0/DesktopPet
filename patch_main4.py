
with open("android/app/src/main/java/com/amiya/pet/ui/MainActivity.kt", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("UpdateManager.downloadUpdate(", "UpdateManager.downloadApk(")

with open("android/app/src/main/java/com/amiya/pet/ui/MainActivity.kt", "w", encoding="utf-8") as f:
    f.write(text)

