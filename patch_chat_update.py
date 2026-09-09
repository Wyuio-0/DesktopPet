
import re

with open("android/app/src/main/java/com/amiya/pet/ui/ChatView.kt", "r", encoding="utf-8") as f:
    text = f.read()

# Add state variables
state_vars = """    var chatList by remember { mutableStateOf(brain.chatHistory) }
    var inputText by remember { mutableStateOf("") }
    var listState = rememberLazyListState()
    
    // Update States
    var showUpdateDialog by remember { mutableStateOf(false) }
    var releaseInfo by remember { mutableStateOf<com.amiya.pet.core.update.ReleaseInfo?>(null) }
    var isDownloading by remember { mutableStateOf(false) }
    var downloadProgress by remember { mutableStateOf<com.amiya.pet.core.update.DownloadProgress?>(null) }
    var downloadJob by remember { mutableStateOf<kotlinx.coroutines.Job?>(null) }
"""
text = text.replace("    var chatList by remember { mutableStateOf(brain.chatHistory) }\n    var inputText by remember { mutableStateOf(\"\") }\n    var listState = rememberLazyListState()", state_vars.strip())

# Add TopAppBar action
top_app_bar_actions = """                actions = {
                    TextButton(onClick = {
                        scope.launch {
                            val res = UpdateManager.checkUpdate(context)
                            if (res.isSuccess && res.getOrNull()?.hasUpdate == true) {
                                releaseInfo = res.getOrNull()
                                showUpdateDialog = true
                            } else {
                                android.widget.Toast.makeText(context, "当前已是最新版本", android.widget.Toast.LENGTH_SHORT).show()
                            }
                        }
                    }) {
                        Text("检查更新", color = Color.LightGray, fontSize = 14.sp)
                    }
                    IconButton(onClick = { showCharDialog = true }) {"""
text = text.replace("                actions = {\n                    IconButton(onClick = { showCharDialog = true }) {", top_app_bar_actions)

# Remove the update button from settings dialog
old_settings_button = """                    
                    val context = LocalContext.current
                    var isChecking by remember { mutableStateOf(false) }
                    
                    Button(
                        onClick = {
                            isChecking = true
                            scope.launch {
                                val res = UpdateManager.checkUpdate(context)
                                isChecking = false
                                if (res.isSuccess && res.getOrNull()?.hasUpdate == true) {
                                    android.widget.Toast.makeText(context, "发现新版本，请在App主页更新", android.widget.Toast.LENGTH_SHORT).show()
                                } else {
                                    android.widget.Toast.makeText(context, "当前已是最新版本", android.widget.Toast.LENGTH_SHORT).show()
                                }
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF242832))
                    ) {
                        if (isChecking) {
                            CircularProgressIndicator(modifier = Modifier.size(16.dp), color = Color.White, strokeWidth = 2.dp)
                            Spacer(Modifier.width(8.dp))
                        }
                        Text(if (isChecking) "检查中..." else "检查更新版本", color = Color.White)
                    }"""
# Note: The text in old file may have messy encoding like "°汾Appҳ" due to PowerShell Get-Content. 
# It's better to just use regex to remove everything from `val context = LocalContext.current` down to `}` before `}, confirmButton`.

# Add the UpdateDialog at the bottom
update_dialog = """
    if (showUpdateDialog && releaseInfo != null) {
        AlertDialog(
            onDismissRequest = { if (!isDownloading) showUpdateDialog = false },
            title = { Text("发现新版本: ${releaseInfo!!.versionName}", color = Color.White) },
            text = {
                Column {
                    Text(releaseInfo!!.releaseNotes, fontSize = 14.sp, color = Color.LightGray)
                    Spacer(Modifier.height(16.dp))
                    if (isDownloading && downloadProgress != null) {
                        LinearProgressIndicator(
                            progress = { downloadProgress!!.progress },
                            modifier = Modifier.fillMaxWidth()
                        )
                        Spacer(Modifier.height(8.dp))
                        Text(
                            "${(downloadProgress!!.downloadedBytes / 1024 / 1024)}MB / ${(downloadProgress!!.totalBytes / 1024 / 1024)}MB",
                            fontSize = 12.sp,
                            color = Color.Gray
                        )
                    }
                }
            },
            confirmButton = {
                if (!isDownloading) {
                    Button(onClick = {
                        isDownloading = true
                        downloadJob = scope.launch {
                            val apkUrl = releaseInfo!!.apkDownloadUrl
                            if (apkUrl.isNullOrEmpty()) {
                                isDownloading = false
                                return@launch
                            }
                            val res = UpdateManager.downloadApk(
                                context,
                                apkUrl,
                                onProgress = { downloadProgress = it }
                            )
                            if (res.isSuccess) {
                                isDownloading = false
                                showUpdateDialog = false
                                UpdateManager.installApk(context, res.getOrThrow())
                            } else {
                                isDownloading = false
                            }
                        }
                    }) {
                        Text("立即更新")
                    }
                }
            },
            dismissButton = {
                if (!isDownloading) {
                    TextButton(onClick = { showUpdateDialog = false }) {
                        Text("稍后再说", color = Color.Gray)
                    }
                } else {
                    TextButton(onClick = {
                        downloadJob?.cancel()
                        isDownloading = false
                    }) {
                        Text("取消下载", color = Color.Red)
                    }
                }
            }
        )
    }

}

@Composable
fun QuickPromptChip"""
text = text.replace("}\n\n@Composable\nfun QuickPromptChip", update_dialog)

with open("android/app/src/main/java/com/amiya/pet/ui/ChatView.kt", "w", encoding="utf-8") as f:
    f.write(text)

