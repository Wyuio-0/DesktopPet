
import re

with open("android/app/src/main/java/com/amiya/pet/ui/ChatView.kt", "r", encoding="utf-8") as f:
    text = f.read()

states = """    var showCharDialog by remember { mutableStateOf(false) }

    // Update States
    var showUpdateDialog by remember { mutableStateOf(false) }
    var releaseInfo by remember { mutableStateOf<com.amiya.pet.core.update.ReleaseInfo?>(null) }
    var isDownloading by remember { mutableStateOf(false) }
    var downloadProgress by remember { mutableStateOf<com.amiya.pet.core.update.DownloadProgress?>(null) }
    var downloadJob by remember { mutableStateOf<kotlinx.coroutines.Job?>(null) }"""

text = text.replace("    var showCharDialog by remember { mutableStateOf(false) }", states)

with open("android/app/src/main/java/com/amiya/pet/ui/ChatView.kt", "w", encoding="utf-8") as f:
    f.write(text)

