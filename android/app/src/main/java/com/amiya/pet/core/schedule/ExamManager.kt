package com.amiya.pet.core.schedule

import android.content.Context
import androidx.compose.runtime.mutableStateListOf
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.UUID

/**
 * 期末考试数据模型
 */
data class ExamItem(
    val id: String = UUID.randomUUID().toString(),
    val title: String,
    val examTimeMillis: Long,
    val durationMinutes: Int = 120,
    val location: String = "",
    val seatNumber: String = "",
    val examType: String = "闭卷",
    val note: String = "",
    val relatedCourseId: String? = null
) {
    /** 考试结束时间戳 */
    val endTimeMillis: Long
        get() = examTimeMillis + durationMinutes * 60_000L

    /** 是否已经结束 */
    fun isFinished(now: Long = System.currentTimeMillis()): Boolean = now > endTimeMillis

    /** 是否正在进行中 */
    fun isOngoing(now: Long = System.currentTimeMillis()): Boolean = now in examTimeMillis..endTimeMillis

    /** 距离开考剩余毫秒数（若已开始或结束则为 <= 0） */
    fun remainingMillis(now: Long = System.currentTimeMillis()): Long = examTimeMillis - now

    /** 格式化日期字符串，如 "10月25日 周五" */
    fun formattedDateStr(): String {
        val sdf = SimpleDateFormat("M月d日 E", Locale.CHINESE)
        return sdf.format(Date(examTimeMillis))
    }

    /** 格式化时间段字符串，如 "09:00 - 11:00" */
    fun formattedTimeRangeStr(): String {
        val timeSdf = SimpleDateFormat("HH:mm", Locale.CHINESE)
        val startStr = timeSdf.format(Date(examTimeMillis))
        val endStr = timeSdf.format(Date(endTimeMillis))
        return "$startStr - $endStr"
    }

    /** 完整日期时间，如 "2026-10-25 09:00" */
    fun formattedFullDateTimeStr(): String {
        val sdf = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.CHINESE)
        return sdf.format(Date(examTimeMillis))
    }

    fun toJson(): JSONObject {
        return JSONObject().apply {
            put("id", id)
            put("title", title)
            put("examTimeMillis", examTimeMillis)
            put("durationMinutes", durationMinutes)
            put("location", location)
            put("seatNumber", seatNumber)
            put("examType", examType)
            put("note", note)
            if (relatedCourseId != null) put("relatedCourseId", relatedCourseId)
        }
    }

    companion object {
        fun fromJson(json: JSONObject): ExamItem {
            return ExamItem(
                id = json.optString("id", UUID.randomUUID().toString()),
                title = json.optString("title", "未命名考试"),
                examTimeMillis = json.optLong("examTimeMillis", System.currentTimeMillis()),
                durationMinutes = json.optInt("durationMinutes", 120),
                location = json.optString("location", ""),
                seatNumber = json.optString("seatNumber", ""),
                examType = json.optString("examType", "闭卷"),
                note = json.optString("note", ""),
                relatedCourseId = if (json.has("relatedCourseId")) json.getString("relatedCourseId") else null
            )
        }
    }
}

/**
 * 考试日程管理器
 */
object ExamManager {
    private const val FILE_NAME = "exams.json"
    private var isLoaded = false

    val exams = mutableStateListOf<ExamItem>()

    fun load(context: Context) {
        if (isLoaded) return
        val file = File(context.filesDir, FILE_NAME)
        if (file.exists()) {
            try {
                val jsonStr = file.readText()
                val array = JSONArray(jsonStr)
                exams.clear()
                for (i in 0 until array.length()) {
                    exams.add(ExamItem.fromJson(array.getJSONObject(i)))
                }
                exams.sortBy { it.examTimeMillis }
                isLoaded = true
                return
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }

        // 若无数据，初始化默认考试示例数据
        initSampleExams(context)
        isLoaded = true
    }

    fun save(context: Context) {
        try {
            val array = JSONArray()
            exams.forEach { array.put(it.toJson()) }
            val file = File(context.filesDir, FILE_NAME)
            file.writeText(array.toString(2))
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun addExam(context: Context, item: ExamItem) {
        exams.add(item)
        exams.sortBy { it.examTimeMillis }
        save(context)
    }

    fun updateExam(context: Context, item: ExamItem) {
        val index = exams.indexOfFirst { it.id == item.id }
        if (index != -1) {
            exams[index] = item
            exams.sortBy { it.examTimeMillis }
            save(context)
        }
    }

    fun deleteExam(context: Context, id: String) {
        exams.removeAll { it.id == id }
        save(context)
    }

    /**
     * 获取最近一场未结束的考试
     */
    fun getNextUpcomingExam(now: Long = System.currentTimeMillis()): ExamItem? {
        return exams.firstOrNull { !it.isFinished(now) }
    }

    /**
     * 计算距考试倒计时详情
     * @return Triple(days, hours, minutes)
     */
    fun getCountdownParts(targetMillis: Long, now: Long = System.currentTimeMillis()): Triple<Long, Long, Long> {
        val diff = targetMillis - now
        if (diff <= 0) return Triple(0L, 0L, 0L)
        val totalSec = diff / 1000
        val days = totalSec / 86400
        val hours = (totalSec % 86400) / 3600
        val minutes = (totalSec % 3600) / 60
        return Triple(days, hours, minutes)
    }

    /**
     * 初始化充满罗德岛学业特色的示范考试数据
     */
    private fun initSampleExams(context: Context) {
        exams.clear()
        val cal = Calendar.getInstance()

        // 考试 1：2 天后的上午 09:00 - 11:00（紧迫倒计时）
        cal.timeInMillis = System.currentTimeMillis()
        cal.add(Calendar.DAY_OF_YEAR, 2)
        cal.set(Calendar.HOUR_OF_DAY, 9)
        cal.set(Calendar.MINUTE, 0)
        cal.set(Calendar.SECOND, 0)
        exams.add(
            ExamItem(
                title = "大学物理B（下）",
                examTimeMillis = cal.timeInMillis,
                durationMinutes = 120,
                location = "理学楼 301 阶梯教室",
                seatNumber = "36 号",
                examType = "闭卷",
                note = "自备科学计算器、2B铅笔与黑色水笔，严禁携带智能手表"
            )
        )

        // 考试 2：5 天后的下午 14:30 - 16:30
        cal.add(Calendar.DAY_OF_YEAR, 3)
        cal.set(Calendar.HOUR_OF_DAY, 14)
        cal.set(Calendar.MINUTE, 30)
        exams.add(
            ExamItem(
                title = "概率论与数理统计A",
                examTimeMillis = cal.timeInMillis,
                durationMinutes = 120,
                location = "信息学部 3区2-108",
                seatNumber = "19 号",
                examType = "闭卷",
                note = "允许携带一张 A4 纸手写公式表（存底备查）"
            )
        )

        // 考试 3：9 天后的上午 09:00 - 11:30
        cal.add(Calendar.DAY_OF_YEAR, 4)
        cal.set(Calendar.HOUR_OF_DAY, 9)
        cal.set(Calendar.MINUTE, 0)
        exams.add(
            ExamItem(
                title = "计算机组成与体系结构",
                examTimeMillis = cal.timeInMillis,
                durationMinutes = 150,
                location = "计算机学院 405 实验机房",
                seatNumber = "A-23 机位",
                examType = "上机/半开卷",
                note = "提前 15 分钟入场调试机位与编译环境"
            )
        )

        // 考试 4：14 天后
        cal.add(Calendar.DAY_OF_YEAR, 5)
        cal.set(Calendar.HOUR_OF_DAY, 14)
        cal.set(Calendar.MINUTE, 0)
        exams.add(
            ExamItem(
                title = "高等量子力学研讨报告",
                examTimeMillis = cal.timeInMillis,
                durationMinutes = 90,
                location = "主楼 812 会议厅",
                seatNumber = "答辩顺序 04",
                examType = "论文/口试",
                note = "准备 10 分钟 PPT 汇报与 5 分钟答辩"
            )
        )

        exams.sortBy { it.examTimeMillis }
        save(context)
    }
}
