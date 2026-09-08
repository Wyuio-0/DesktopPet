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
    val note: String = ""
) {
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

