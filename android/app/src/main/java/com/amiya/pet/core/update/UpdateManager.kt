package com.amiya.pet.core.update

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Environment
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL

data class ReleaseInfo(
    val tagName: String,
    val versionName: String,
    val releaseNotes: String,
    val apkDownloadUrl: String?,
    val htmlUrl: String,
    val hasUpdate: Boolean
)

data class DownloadProgress(
    val downloadedBytes: Long = 0L,
    val totalBytes: Long = 0L,
    val progress: Float = 0f, // 0.0f .. 1.0f
    val speedBps: Long = 0L,  // 字节/秒
    val isDone: Boolean = false,
    val error: String? = null
) {
    fun formattedSpeed(): String {
        return when {
            speedBps >= 1024 * 1024 -> "%.1f MB/s".format(speedBps / (1024.0 * 1024.0))
            speedBps >= 1024 -> "%.0f KB/s".format(speedBps / 1024.0)
            else -> "$speedBps B/s"
        }
    }

    fun formattedDownloaded(): String {
        val mb = downloadedBytes / (1024.0 * 1024.0)
        return "%.1f MB".format(mb)
    }

    fun formattedTotal(): String {
        if (totalBytes <= 0) return "计算中..."
        val mb = totalBytes / (1024.0 * 1024.0)
        return "%.1f MB".format(mb)
    }
}

object UpdateManager {

    private const val GITHUB_API_LATEST =
        "https://api.github.com/repos/Wyuio-0/AmiyaDesktopPet/releases/latest"

    suspend fun checkUpdate(context: Context): Result<ReleaseInfo> = withContext(Dispatchers.IO) {
        try {
            val currentVersion = getCurrentVersion(context)
            val url = URL(GITHUB_API_LATEST)
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = 8000
                readTimeout = 8000
                setRequestProperty("Accept", "application/vnd.github.v3+json")
                setRequestProperty("User-Agent", "AmiyaPet-Android")
            }

            if (conn.responseCode != 200) {
                return@withContext Result.failure(Exception("GitHub 响应错误 (${conn.responseCode})"))
            }

            val resp = conn.inputStream.bufferedReader().use { it.readText() }
            val json = JSONObject(resp)

            val tagName = json.optString("tag_name", "")
            val body = json.optString("body", "暂无版本更新说明。")
            val htmlUrl = json.optString("html_url", "https://github.com/Wyuio-0/AmiyaDesktopPet/releases")

            var apkUrl: String? = null
            val assets = json.optJSONArray("assets")
            if (assets != null) {
                for (i in 0 until assets.length()) {
                    val asset = assets.getJSONObject(i)
                    val name = asset.optString("name", "")
                    if (name.endsWith(".apk", ignoreCase = true)) {
                        apkUrl = asset.optString("browser_download_url")
                        break
                    }
                }
            }

            val cleanTag = tagName.removePrefix("v").removePrefix("V")
            val hasNewVersion = isNewerVersion(cleanTag, currentVersion)

            Result.success(
                ReleaseInfo(
                    tagName = tagName,
                    versionName = cleanTag,
                    releaseNotes = body,
                    apkDownloadUrl = apkUrl,
                    htmlUrl = htmlUrl,
                    hasUpdate = hasNewVersion
                )
            )
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun downloadApk(
        context: Context,
        apkUrl: String,
        onProgress: (DownloadProgress) -> Unit
    ): Result<File> = withContext(Dispatchers.IO) {
        try {
            val downloadDir = context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)
                ?: File(context.cacheDir, "apk_updates").apply { mkdirs() }
            if (!downloadDir.exists()) downloadDir.mkdirs()

            val destFile = File(downloadDir, "AmiyaPet-update.apk")
            val tempFile = File(downloadDir, "AmiyaPet-update.apk.tmp")
            if (tempFile.exists()) tempFile.delete()

            var currentUrl = apkUrl
            var conn: HttpURLConnection
            var redirectCount = 0
            while (true) {
                val u = URL(currentUrl)
                conn = (u.openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 15000
                    readTimeout = 30000
                    setRequestProperty("User-Agent", "AmiyaPet-Android")
                    instanceFollowRedirects = true
                }
                val code = conn.responseCode
                if (code in listOf(HttpURLConnection.HTTP_MOVED_PERM, HttpURLConnection.HTTP_MOVED_TEMP, 307, 308)) {
                    val newUrl = conn.getHeaderField("Location")
                    conn.disconnect()
                    if (!newUrl.isNullOrBlank() && redirectCount < 5) {
                        currentUrl = newUrl
                        redirectCount++
                        continue
                    }
                }
                if (code != HttpURLConnection.HTTP_OK) {
                    return@withContext Result.failure(Exception("下载服务器响应失败 (HTTP $code)"))
                }
                break
            }

            val totalLength = conn.contentLengthLong.let { if (it > 0) it else conn.contentLength.toLong() }
            var downloadedBytes = 0L
            var lastTime = System.currentTimeMillis()
            var lastBytes = 0L
            var speed = 0L

            conn.inputStream.use { input ->
                FileOutputStream(tempFile).use { output ->
                    val buffer = ByteArray(32 * 1024)
                    var bytesRead: Int
                    while (input.read(buffer).also { bytesRead = it } != -1) {
                        currentCoroutineContext().ensureActive()
                        output.write(buffer, 0, bytesRead)
                        downloadedBytes += bytesRead

                        val now = System.currentTimeMillis()
                        val interval = now - lastTime
                        if (interval >= 200 || downloadedBytes == totalLength) {
                            if (interval > 0) {
                                speed = ((downloadedBytes - lastBytes) * 1000L) / interval
                            }
                            lastTime = now
                            lastBytes = downloadedBytes

                            val prog = if (totalLength > 0) {
                                (downloadedBytes.toFloat() / totalLength).coerceIn(0f, 1f)
                            } else 0f

                            onProgress(
                                DownloadProgress(
                                    downloadedBytes = downloadedBytes,
                                    totalBytes = totalLength,
                                    progress = prog,
                                    speedBps = speed,
                                    isDone = false
                                )
                            )
                        }
                    }
                }
            }

            if (destFile.exists()) destFile.delete()
            if (!tempFile.renameTo(destFile)) {
                tempFile.copyTo(destFile, overwrite = true)
                tempFile.delete()
            }

            onProgress(
                DownloadProgress(
                    downloadedBytes = downloadedBytes,
                    totalBytes = totalLength,
                    progress = 1.0f,
                    speedBps = 0L,
                    isDone = true
                )
            )

            Result.success(destFile)
        } catch (e: Exception) {
            onProgress(
                DownloadProgress(
                    downloadedBytes = 0,
                    totalBytes = 0,
                    progress = 0f,
                    speedBps = 0,
                    isDone = false,
                    error = e.localizedMessage ?: "下载失败"
                )
            )
            Result.failure(e)
        }
    }

    fun installApk(context: Context, apkFile: File) {
        val apkUri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            apkFile
        )
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(apkUri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }

    fun getCurrentVersion(context: Context): String {
        return try {
            val pInfo = context.packageManager.getPackageInfo(context.packageName, 0)
            pInfo.versionName ?: "1.0.0"
        } catch (e: Exception) {
            "1.0.0"
        }
    }

    private fun isNewerVersion(remote: String, local: String): Boolean {
        if (remote.isBlank()) return false
        val rParts = remote.split(".").mapNotNull { it.toIntOrNull() }
        val lParts = local.split(".").mapNotNull { it.toIntOrNull() }
        val maxLen = maxOf(rParts.size, lParts.size)
        for (i in 0 until maxLen) {
            val r = rParts.getOrElse(i) { 0 }
            val l = lParts.getOrElse(i) { 0 }
            if (r > l) return true
            if (r < l) return false
        }
        return false
    }
}
