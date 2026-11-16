package com.amiya.pet.core.sync

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption

/** Local deletion history used to carry deletes through later merge syncs. */
object SyncDeletionStore {
    val categories = listOf("schedule", "exams", "notes")
    private const val MAX_IDS = 10_000
    private const val MAX_ID_LENGTH = 128

    private fun file(context: Context) = File(context.filesDir, "sync_tombstones.json")
    private fun empty() = categories.associateWith { mutableSetOf<String>() }.toMutableMap()

    @Synchronized private fun load(context: Context): MutableMap<String, MutableSet<String>> {
        val path = file(context)
        if (!path.exists()) return empty()
        val body = JSONObject(path.readText(Charsets.UTF_8))
        require(body.getInt("schema") == 1)
        require(body.keys().asSequence().all { it == "schema" || it in categories })
        val result = empty()
        for (category in categories) {
            val array = if (body.has(category)) body.optJSONArray(category) ?: error("删除记录类别格式无效") else JSONArray()
            require(array.length() <= MAX_IDS)
            for (index in 0 until array.length()) {
                val id = array.get(index)
                require(id is String && id.isNotEmpty() && id.toByteArray(Charsets.UTF_8).size <= MAX_ID_LENGTH)
                require(result.getValue(category).add(id))
            }
        }
        return result
    }

    @Synchronized private fun save(context: Context, value: Map<String, Set<String>>) {
        val target = file(context)
        if (!target.parentFile!!.isDirectory && !target.parentFile!!.mkdirs()) error("无法创建删除记录")
        val body = JSONObject().put("schema", 1)
        for (category in categories) {
            require(value.getValue(category).size <= MAX_IDS)
            body.put(category, JSONArray(value.getValue(category).sorted()))
        }
        val temporary = File(target.parentFile, "sync_tombstones.tmp")
        FileOutputStream(temporary).use { stream -> stream.write(body.toString().toByteArray(Charsets.UTF_8)); stream.fd.sync() }
        Files.move(temporary.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE)
    }

    @Synchronized fun snapshot(context: Context): JSONObject {
        val current = load(context)
        return JSONObject().apply { for (category in categories) put(category, JSONArray(current.getValue(category).sorted())) }
    }

    @Synchronized fun record(context: Context, category: String, id: String): Boolean = try {
        require(category in categories && id.isNotEmpty() && id.toByteArray(Charsets.UTF_8).size <= MAX_ID_LENGTH)
        val current = load(context)
        current.getValue(category).add(id)
        save(context, current)
        true
    } catch (_: Exception) { false }

    @Synchronized fun validate(value: JSONObject): JSONObject {
        require(value.keys().asSequence().all { it in categories })
        val normalized = JSONObject()
        for (category in categories) {
            val rows = if (value.has(category)) value.optJSONArray(category) ?: error("删除记录类别格式无效") else JSONArray()
            require(rows.length() <= MAX_IDS)
            val ids = mutableSetOf<String>()
            for (index in 0 until rows.length()) {
                val id = rows.get(index)
                require(id is String && id.isNotEmpty() && id.toByteArray(Charsets.UTF_8).size <= MAX_ID_LENGTH && ids.add(id))
            }
            normalized.put(category, JSONArray(ids.sorted()))
        }
        return normalized
    }

    @Synchronized fun forget(context: Context, category: String, id: String) {
        try {
            val current = load(context)
            current.getValue(category).remove(id)
            save(context, current)
        } catch (_: Exception) {}
    }

    @Synchronized fun apply(context: Context, incoming: JSONObject, mode: String,
        categoriesToReplace: Set<String>, localIds: Map<String, Set<String>>, liveIds: Map<String, Set<String>>): Map<String, Set<String>> {
        val current = load(context)
        val remote = empty()
        require(incoming.keys().asSequence().all { it in categories })
        for (category in categories) {
            val rows = incoming.optJSONArray(category) ?: JSONArray()
            require(rows.length() <= MAX_IDS)
            for (index in 0 until rows.length()) {
                val id = rows.get(index)
                require(id is String && id.isNotEmpty() && id.toByteArray(Charsets.UTF_8).size <= MAX_ID_LENGTH)
                require(remote.getValue(category).add(id))
            }
            current.getValue(category).addAll(remote.getValue(category))
        }
        if (mode == "replace") for (category in categoriesToReplace) {
            current.getValue(category).addAll(localIds.getValue(category) - liveIds.getValue(category))
            current.getValue(category).removeAll(liveIds.getValue(category) - remote.getValue(category))
        }
        save(context, current)
        return current.mapValues { it.value.toSet() }
    }
}
