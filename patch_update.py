
import re
with open("android/app/src/main/java/com/amiya/pet/ui/MainActivity.kt", "r", encoding="utf-8") as f:
    text = f.read()

# Make sure LocalContext is imported
if "import androidx.compose.ui.platform.LocalContext" not in text:
    text = text.replace("import androidx.compose.ui.text.font.FontWeight", "import androidx.compose.ui.text.font.FontWeight\nimport androidx.compose.ui.platform.LocalContext\nimport androidx.compose.runtime.rememberCoroutineScope\nimport androidx.compose.runtime.LaunchedEffect")

update_logic = """@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen() {
    var selectedTab by remember { mutableStateOf(MainTab.CHAT) }
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    
    // Update States
    var showUpdateDialog by remember { mutableStateOf(false) }
    var releaseInfo by remember { mutableStateOf<ReleaseInfo?>(null) }
    var isDownloading by remember { mutableStateOf(false) }
    var downloadProgress by remember { mutableStateOf<DownloadProgress?>(null) }
    var downloadJob by remember { mutableStateOf<Job?>(null) }
    
    // Auto check update on startup
    LaunchedEffect(Unit) {
        val result = UpdateManager.checkUpdate(context)
        if (result.isSuccess) {
            val info = result.getOrNull()
            if (UpdateManager.hasUpdate && info != null) {
                releaseInfo = info
                showUpdateDialog = true
            }
        }
    }
    
    // Update Dialog UI
    if (showUpdateDialog && releaseInfo != null) {
        AlertDialog(
            onDismissRequest = { if (!isDownloading) showUpdateDialog = false },
            title = { Text("发现新版本: ${releaseInfo!!.version}", color = Color.White) },
            text = {
                Column {
                    Text(releaseInfo!!.notes, fontSize = 14.sp, color = Color.LightGray)
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
                        downloadJob = coroutineScope.launch {
                            UpdateManager.downloadUpdate(
                                releaseInfo!!.downloadUrl,
                                context,
                                onProgress = { downloadProgress = it },
                                onSuccess = { file ->
                                    isDownloading = false
                                    showUpdateDialog = false
                                    UpdateManager.installApk(context, file)
                                },
                                onError = { _ ->
                                    isDownloading = false
                                }
                            )
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

    Scaffold("""

text = text.replace("@OptIn(ExperimentalMaterial3Api::class)\n@Composable\nfun MainScreen() {\n    var selectedTab by remember { mutableStateOf(MainTab.CHAT) }\n\n    Scaffold(", update_logic)

with open("android/app/src/main/java/com/amiya/pet/ui/MainActivity.kt", "w", encoding="utf-8") as f:
    f.write(text)

