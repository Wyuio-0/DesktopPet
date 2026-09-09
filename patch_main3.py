
import re

with open("android/app/src/main/java/com/amiya/pet/ui/MainActivity.kt", "r", encoding="utf-8") as f:
    text = f.read()

# 1. UpdateManager.hasUpdate -> info.hasUpdate
text = text.replace("if (UpdateManager.hasUpdate && info != null)", "if (info != null && info.hasUpdate)")

# 2. releaseInfo!!.version -> releaseInfo!!.versionName
text = text.replace("releaseInfo!!.version", "releaseInfo!!.versionName")

# 3. releaseInfo!!.notes -> releaseInfo!!.releaseNotes
text = text.replace("releaseInfo!!.notes", "releaseInfo!!.releaseNotes")

# 4. Fix downloadUpdate signature
old_download = """UpdateManager.downloadUpdate(
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
                            )"""
new_download = """val apkUrl = releaseInfo!!.apkDownloadUrl
                            if (apkUrl.isNullOrEmpty()) {
                                isDownloading = false
                                return@launch
                            }
                            val res = UpdateManager.downloadUpdate(
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
                            }"""
text = text.replace(old_download, new_download)

with open("android/app/src/main/java/com/amiya/pet/ui/MainActivity.kt", "w", encoding="utf-8") as f:
    f.write(text)

