package com.amiya.pet.core.sync

import android.content.Context
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest
import java.util.UUID

/** Local study snapshots only. Nothing in this directory is sent by sync. */
object SyncBackupStore {
    const val KEEP = 10
    private const val MAX = 16 * 1024 * 1024
    private val pattern = Regex("b-[0-9]{13}-[a-f0-9]{32}")
    private val categories = setOf("schedule", "exams", "notes")
    data class Entry(val id: String, val createdMillis: Long, val reason: String,
        val categories: List<String>, val valid: Boolean)

    private fun directory(context: Context) = File(context.filesDir, "sync_backups")
    private fun file(context: Context, id: String): File {
        require(pattern.matches(id)) { "备份标识无效" }
        val result = File(directory(context), "$id.json")
        require(!Files.isSymbolicLink(result.toPath())) { "不能读取链接形式的备份" }
        return result
    }
    private fun files(context: Context) = directory(context).listFiles()?.filter {
        it.extension == "json" && pattern.matches(it.nameWithoutExtension)
    }?.sortedByDescending { it.name } ?: emptyList()
    private fun digest(value: String) = MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8))
        .joinToString("") { (it.toInt() and 255).toString(16).padStart(2, '0') }
    private fun checkPayload(payload: JSONObject) {
        require(payload.keys().asSequence().toSet() == setOf("data", "local"))
        val data = payload.getJSONObject("data"); val local = payload.getJSONObject("local")
        val keys = data.keys().asSequence().toSet()
        val dataCategories = keys - "tombstones"
        require(keys.isNotEmpty() && (categories + "tombstones").containsAll(keys) &&
            local.keys().asSequence().toSet() == dataCategories)
    }
    private fun read(context: Context, id: String): Pair<JSONObject, JSONObject> {
        val raw = ByteArrayOutputStream()
        file(context, id).inputStream().use { input ->
            val buffer = ByteArray(8192)
            while (true) {
                val n = input.read(buffer)
                if (n < 0) break
                require(raw.size() + n <= MAX) { "备份超过大小限制" }
                raw.write(buffer, 0, n)
            }
        }
        val entry = JSONObject(raw.toString("UTF-8"))
        require(entry.getInt("schema") == 1 && entry.getString("platform") == "android" && entry.getString("id") == id)
        require(entry.getString("reason") in setOf("before_replace", "before_restore"))
        require(entry.getLong("created_ms") in 1L until 253402300800000L)
        val body = entry.getString("payload")
        require(MessageDigest.isEqual(digest(body).toByteArray(Charsets.US_ASCII), entry.getString("sha256").toByteArray(Charsets.US_ASCII)))
        val payload = JSONObject(body); checkPayload(payload)
        return entry to payload
    }
    @Synchronized fun load(context: Context, id: String): JSONObject = read(context, id).second

    @Synchronized fun create(context: Context, payload: JSONObject, reason: String = "before_replace"): String {
        checkPayload(payload)
        require(reason in setOf("before_replace", "before_restore"))
        require(files(context).size <= KEEP) { "备份清理失败，请先检查存储" }
        val now = System.currentTimeMillis()
        val id = "b-$now-" + UUID.randomUUID().toString().replace("-", "")
        val target = file(context, id)
        val temporary = File(target.parentFile, "$id.tmp")
        try {
            val dir = directory(context)
            if (!dir.isDirectory && !dir.mkdirs()) throw IOException("无法创建备份目录")
            val body = payload.toString()
            val envelope = JSONObject().put("schema", 1).put("platform", "android").put("id", id)
                .put("created_ms", now).put("reason", reason).put("payload", body).put("sha256", digest(body))
                .toString().toByteArray(Charsets.UTF_8)
            require(envelope.size <= MAX) { "备份超过 16 MiB" }
            FileOutputStream(temporary).use { output -> output.write(envelope); output.fd.sync() }
            Files.move(temporary.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE)
            read(context, id)
            files(context).filter { it != target }.drop(KEEP - 1).forEach {
                if (!it.delete()) throw IOException("备份清理失败")
            }
            return id
        } finally { temporary.delete() }
    }
    @Synchronized fun list(context: Context): List<Entry> = files(context).map { path ->
        val id = path.nameWithoutExtension
        try {
            val (entry, payload) = read(context, id)
            Entry(id, entry.getLong("created_ms"), entry.getString("reason"),
                payload.getJSONObject("data").keys().asSequence().filter { it != "tombstones" }.toList(), true)
        } catch (_: Exception) { Entry(id, 0, "corrupt", emptyList(), false) }
    }
}
