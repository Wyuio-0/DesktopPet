package com.amiya.pet.core.schedule

import java.util.Calendar

data class Course(
    val name: String,
    val weekday: Int, // 1=周一, 7=周日
    val secStart: Int,
    val secEnd: Int,
    val weekStart: Int,
    val weekEnd: Int,
    val parity: String, // "all", "odd", "even"
    val room: String = "",
    val teacher: String = "",
    val campus: String = "",
    val note: String = "",
    val customTime: String = "", // 自定义精确时间，如 "14:15-15:30"
    val id: String = java.util.UUID.randomUUID().toString()
) {
    val isActivity: Boolean
        get() = customTime.isNotBlank()

    fun activeOn(weekNo: Int): Boolean {
        if (weekNo < weekStart || weekNo > weekEnd) return false
        return when (parity) {
            "even" -> weekNo % 2 == 0
            "odd" -> weekNo % 2 == 1
            else -> true
        }
    }

    fun startTime(weekNo: Int, sections: Map<String, String>): Pair<Int, Int>? {
        if (!activeOn(weekNo)) return null
        if (customTime.isNotBlank() && customTime.contains(":")) {
            try {
                val startPart = customTime.split("-", "~", "至", "到").first().trim()
                val parts = startPart.split(":")
                if (parts.size >= 2) {
                    val h = parts[0].trim().toInt()
                    val m = parts[1].trim().toInt()
                    if (h in 0..23 && m in 0..59) return Pair(h, m)
                }
            } catch (ignored: Exception) {}
        }
        val timeStr = sections[secStart.toString()] ?: return null
        return try {
            val parts = timeStr.split(":")
            if (parts.size != 2) return null
            val h = parts[0].toInt()
            val m = parts[1].toInt()
            if (h in 0..23 && m in 0..59) Pair(h, m) else null
        } catch (e: Exception) {
            null
        }
    }
}

