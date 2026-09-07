package com.amiya.pet.core.update

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
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
