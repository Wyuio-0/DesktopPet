package com.amiya.pet.core.notes

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.*

data class Note(
    val id: String = "note_" + UUID.randomUUID().toString().substring(0, 8),
    var title: String = "灵感随记",
    var content: String = "",
    val createdAt: String = currentTimestamp(),
    var updatedAt: String = currentTimestamp(),
    var pinned: Boolean = false
) {
    fun autoDeriveTitle(maxLen: Int = 16): String {
        val firstLine = content.lines().firstOrNull { it.isNotBlank() }?.trim()
        if (firstLine.isNullOrEmpty()) return "空白便签"
        val cleaned = firstLine.trimStart('#', '-', '*', '•', ' ')
        return if (cleaned.length > maxLen) cleaned.substring(0, maxLen) + "…" else cleaned
    }

    fun toJsonObject(): JSONObject {
        return JSONObject().apply {
            put("id", id)
            put("title", title)
            put("content", content)
            put("created_at", createdAt)
            put("updated_at", updatedAt)
            put("pinned", pinned)
        }
    }

    companion object {
        fun fromJsonObject(obj: JSONObject): Note {
            return Note(
                id = obj.optString("id", "note_" + UUID.randomUUID().toString().substring(0, 8)),
                title = obj.optString("title", "灵感随记"),
                content = obj.optString("content", ""),
                createdAt = obj.optString("created_at", currentTimestamp()),
                updatedAt = obj.optString("updated_at", currentTimestamp()),
                pinned = obj.optBoolean("pinned", false)
            )
        }

        fun currentTimestamp(): String {
            return SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()).format(Date())
        }
    }
}

class NotesManager private constructor(private val context: Context) {

    private val notesFile: File
        get() = File(context.filesDir, "notes.json")

    private val _notes = mutableListOf<Note>()
    val notes: List<Note>
        get() = _notes.sortedWith(compareByDescending<Note> { it.pinned }.thenByDescending { it.updatedAt })

    init {
        loadNotes()
    }

    fun loadNotes() {
        _notes.clear()
        val file = notesFile
        if (!file.exists()) {
            // 初始化默认第一条便签
            val defaultNote = Note(
                title = "罗德岛灵感随记",
                content = "欢迎使用阿米娅灵感便签！\n\n- 随手记录工作灵感与备忘待办\n- 输入即时自动保存\n- 点击顶部可新建或切换便签",
                pinned = true
            )
            _notes.add(defaultNote)
            saveNotes()
            return
        }

        try {
            val jsonStr = file.readText(Charsets.UTF_8)
            val root = JSONObject(jsonStr)
            val arr = root.optJSONArray("notes") ?: JSONArray()
            for (i in 0 until arr.length()) {
                val item = arr.getJSONObject(i)
                _notes.add(Note.fromJsonObject(item))
            }
            if (_notes.isEmpty()) {
                _notes.add(Note(title = "灵感随记", content = ""))
                saveNotes()
            }
        } catch (e: Exception) {
            e.printStackTrace()
            _notes.add(Note(title = "灵感随记", content = ""))
        }
    }

    fun saveNotes() {
        try {
            val root = JSONObject()
            val arr = JSONArray()
            _notes.forEach { arr.put(it.toJsonObject()) }
            root.put("notes", arr)

            val file = notesFile
            val tmp = File(file.parentFile, "${file.name}.tmp")
            tmp.writeText(root.toString(2), Charsets.UTF_8)
            if (tmp.exists()) {
                if (file.exists()) file.delete()
                tmp.renameTo(file)
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun createNote(title: String = "新便签", content: String = ""): Note {
        val note = Note(title = title, content = content)
        _notes.add(0, note)
        saveNotes()
        return note
    }

    fun updateNote(id: String, content: String, title: String? = null, pinned: Boolean? = null): Note? {
        val note = _notes.find { it.id == id } ?: return null
        note.content = content
        if (title != null) {
            note.title = title
        } else {
            note.title = note.autoDeriveTitle()
        }
        if (pinned != null) {
            note.pinned = pinned
        }
        note.updatedAt = Note.currentTimestamp()
        saveNotes()
        return note
    }

    fun deleteNote(id: String): Boolean {
        val removed = _notes.removeAll { it.id == id }
        if (_notes.isEmpty()) {
            _notes.add(Note(title = "新便签", content = ""))
        }
        if (removed) {
            saveNotes()
        }
        return removed
    }

    fun togglePin(id: String): Boolean {
        val note = _notes.find { it.id == id } ?: return false
        note.pinned = !note.pinned
        note.updatedAt = Note.currentTimestamp()
        saveNotes()
        return note.pinned
    }

    companion object {
        @Volatile
        private var INSTANCE: NotesManager? = null

        fun getInstance(context: Context): NotesManager {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: NotesManager(context.applicationContext).also { INSTANCE = it }
            }
        }
    }
}
