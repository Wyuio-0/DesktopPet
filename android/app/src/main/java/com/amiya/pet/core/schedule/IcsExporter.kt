package com.amiya.pet.core.schedule

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import java.io.File
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * iCalendar (.ics / RFC 5545) 通用日历文件生成引擎
 * 支持将学期所有排课离散展开为高兼容度的 VEVENT 事件，
 * 完美支持小米、华为、OPPO、苹果、Google Calendar 等系统日历一键导入。
 */
object IcsExporter {

    private val utcFormat = SimpleDateFormat("yyyyMMdd'T'HHmmss'Z'", Locale.US).apply {
        timeZone = TimeZone.getTimeZone("UTC")
    }

    private val localDateTimeFormat = SimpleDateFormat("yyyyMMdd'T'HHmmss", Locale.US).apply {
        timeZone = TimeZone.getTimeZone("Asia/Shanghai")
    }

    /**
     * 计算预计生成的日历日程总条数
     */
    fun calculateTotalEvents(courses: List<Course>): Int {
        var count = 0
        for (c in courses) {
            for (w in c.weekStart..c.weekEnd) {
                if (c.activeOn(w)) {
                    count++
                }
            }
        }
        return count
    }

    /**
     * 生成标准 RFC 5545 文本内容
     */
    fun generateIcsContent(
        courses: List<Course>,
        sections: Map<String, String>,
        termStart: Date,
        remindMinutes: Int = 20,
        exams: List<ExamItem> = emptyList(),
        calendarName: String = "阿米娅学期课表"
    ): String {
        val sb = StringBuilder()
        val nowUtcStr = utcFormat.format(Date())

        // 1. VCALENDAR 标头
        sb.append("BEGIN:VCALENDAR\r\n")
        sb.append("VERSION:2.0\r\n")
        sb.append("PRODID:-//Amiya Pet//Schedule Exporter//CN\r\n")
        sb.append("CALSCALE:GREGORIAN\r\n")
        sb.append("METHOD:PUBLISH\r\n")
        sb.append("X-WR-CALNAME:").append(calendarName).append("\r\n")
        sb.append("X-WR-TIMEZONE:Asia/Shanghai\r\n")

        // 2. VTIMEZONE 中国标准时间 (CST, +0800)
        sb.append("BEGIN:VTIMEZONE\r\n")
        sb.append("TZID:Asia/Shanghai\r\n")
        sb.append("X-LIC-LOCATION:Asia/Shanghai\r\n")
        sb.append("BEGIN:STANDARD\r\n")
        sb.append("TZOFFSETFROM:+0800\r\n")
        sb.append("TZOFFSETTO:+0800\r\n")
        sb.append("TZNAME:CST\r\n")
        sb.append("DTSTART:19700101T000000\r\n")
        sb.append("END:STANDARD\r\n")
        sb.append("END:VTIMEZONE\r\n")

        // 3. 遍历课程与活跃周次，逐条展开为独立 VEVENT
        for (c in courses) {
            val stStr = sections[c.secStart.toString()] ?: "08:00"
            val etStr = sections[c.secEnd.toString()] ?: stStr
            val stParts = stStr.split(":")
            val etParts = etStr.split(":")
            val stH = stParts.getOrNull(0)?.toIntOrNull() ?: 8
            val stM = stParts.getOrNull(1)?.toIntOrNull() ?: 0
            val etHRaw = etParts.getOrNull(0)?.toIntOrNull() ?: 8
            val etMRaw = etParts.getOrNull(1)?.toIntOrNull() ?: 0
            // 每小节标准时长 45 分钟
            val endTotalMin = etHRaw * 60 + etMRaw + 45
            val etH = endTotalMin / 60
            val etM = endTotalMin % 60

            for (weekNo in c.weekStart..c.weekEnd) {
                if (!c.activeOn(weekNo)) continue

                // 计算具体公历日期：termStart 为第 1 周周日，c.weekday (1=周一..6=周六, 7=周日)
                val dayOffsetInWeek = if (c.weekday == 7) 0 else c.weekday
                val dayOffset = (weekNo - 1) * 7 + dayOffsetInWeek
                val cal = Calendar.getInstance(TimeZone.getTimeZone("Asia/Shanghai")).apply {
                    time = termStart
                    add(Calendar.DAY_OF_YEAR, dayOffset)
                }

                cal.set(Calendar.HOUR_OF_DAY, stH)
                cal.set(Calendar.MINUTE, stM)
                cal.set(Calendar.SECOND, 0)
                cal.set(Calendar.MILLISECOND, 0)
                val dtStartStr = localDateTimeFormat.format(cal.time)

                cal.set(Calendar.HOUR_OF_DAY, etH)
                cal.set(Calendar.MINUTE, etM)
                val dtEndStr = localDateTimeFormat.format(cal.time)

                val eventUid = "${c.id}_w${weekNo}_s${c.secStart}@amiya.pet"

                sb.append("BEGIN:VEVENT\r\n")
                sb.append("UID:").append(eventUid).append("\r\n")
                sb.append("DTSTAMP:").append(nowUtcStr).append("\r\n")
                sb.append("DTSTART;TZID=Asia/Shanghai:").append(dtStartStr).append("\r\n")
                sb.append("DTEND;TZID=Asia/Shanghai:").append(dtEndStr).append("\r\n")
                sb.append("SUMMARY:").append(escapeIcsText(c.name)).append("\r\n")

                if (c.room.isNotEmpty()) {
                    sb.append("LOCATION:").append(escapeIcsText(c.room)).append("\r\n")
                }

                // 描述详情：教师、周次、节次与校区
                val descParts = mutableListOf<String>()
                if (c.teacher.isNotEmpty()) descParts.add("任课教师: ${c.teacher}")
                descParts.add("节次: 第 ${c.secStart}-${c.secEnd} 节")
                descParts.add("周次: 第 $weekNo 周 (全周段 ${c.weekStart}-${c.weekEnd} 周)")
                if (c.campus.isNotEmpty()) descParts.add("校区: ${c.campus}")
                if (c.note.isNotEmpty()) descParts.add("备注: ${c.note}")
                sb.append("DESCRIPTION:").append(escapeIcsText(descParts.joinToString("\\n"))).append("\r\n")

                // 4. VALARM 课前提醒
                if (remindMinutes > 0) {
                    sb.append("BEGIN:VALARM\r\n")
                    sb.append("ACTION:DISPLAY\r\n")
                    sb.append("DESCRIPTION:上课提醒: ").append(escapeIcsText(c.name)).append("\r\n")
                    sb.append("TRIGGER:-PT").append(remindMinutes).append("M\r\n")
                    sb.append("END:VALARM\r\n")
                }

                sb.append("END:VEVENT\r\n")
            }
        }

        // 4. 追加期末考试日程 (VEVENT)
        for (exam in exams) {
            val examStartStr = localDateTimeFormat.format(Date(exam.examTimeMillis))
            val examEndStr = localDateTimeFormat.format(Date(exam.endTimeMillis))
            val examUid = "exam_${exam.id}@amiya.pet"

            sb.append("BEGIN:VEVENT\r\n")
            sb.append("UID:").append(examUid).append("\r\n")
            sb.append("DTSTAMP:").append(nowUtcStr).append("\r\n")
            sb.append("DTSTART;TZID=Asia/Shanghai:").append(examStartStr).append("\r\n")
            sb.append("DTEND;TZID=Asia/Shanghai:").append(examEndStr).append("\r\n")
            sb.append("SUMMARY:【期末考试】").append(escapeIcsText(exam.title)).append("\r\n")

            if (exam.location.isNotEmpty()) {
                sb.append("LOCATION:").append(escapeIcsText(exam.location)).append("\r\n")
            }

            val descParts = mutableListOf<String>()
            descParts.add("考试形式: ${exam.examType}")
            if (exam.seatNumber.isNotEmpty()) descParts.add("座位号: ${exam.seatNumber}")
            descParts.add("考试时长: ${exam.durationMinutes} 分钟")
            if (exam.note.isNotEmpty()) descParts.add("备战提示: ${exam.note}")
            sb.append("DESCRIPTION:").append(escapeIcsText(descParts.joinToString("\\n"))).append("\r\n")

            // 考前 60 分钟提醒
            sb.append("BEGIN:VALARM\r\n")
            sb.append("ACTION:DISPLAY\r\n")
            sb.append("DESCRIPTION:期末考试提醒: ").append(escapeIcsText(exam.title)).append("\r\n")
            sb.append("TRIGGER:-PT60M\r\n")
            sb.append("END:VALARM\r\n")

            sb.append("END:VEVENT\r\n")
        }

        sb.append("END:VCALENDAR\r\n")
        return sb.toString()
    }

    /**
     * 将 .ics 内容写入应用缓存并返回 File
     */
    fun exportIcsFile(
        context: Context,
        termStart: Date,
        remindMinutes: Int = 20,
        includeExams: Boolean = true,
        fileName: String = "amiya_schedule.ics"
    ): File {
        ScheduleManager.load(context)
        ExamManager.load(context)
        val courses = ScheduleManager.courses
        val sections = ScheduleManager.sections
        val exams = if (includeExams) ExamManager.exams else emptyList()
        val icsText = generateIcsContent(courses, sections, termStart, remindMinutes, exams)

        val file = File(context.cacheDir, fileName)
        file.writeText(icsText, Charsets.UTF_8)
        return file
    }

    /**
     * 调起系统日历直接导入 .ics 日程
     */
    fun openInSystemCalendar(context: Context, file: File): Boolean {
        return try {
            val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, "text/calendar")
                flags = Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK
            }
            if (intent.resolveActivity(context.packageManager) != null) {
                context.startActivity(intent)
                true
            } else {
                // 若系统未注册 text/calendar 的 ACTION_VIEW，降级为系统分享
                shareIcsFile(context, file)
                true
            }
        } catch (e: Exception) {
            e.printStackTrace()
            try {
                shareIcsFile(context, file)
                true
            } catch (_: Exception) {
                false
            }
        }
    }

    /**
     * 调起系统分享菜单，支持保存到文件管理器、微信、QQ、发送到电脑等
     */
    fun shareIcsFile(context: Context, file: File) {
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "text/calendar"
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(Intent.EXTRA_SUBJECT, "阿米娅学期课表.ics")
            flags = Intent.FLAG_GRANT_READ_URI_PERMISSION
        }
        val chooser = Intent.createChooser(intent, "分享或保存课表日历 (.ics)").apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        context.startActivity(chooser)
    }

    private fun escapeIcsText(text: String): String {
        return text
            .replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\r\n", "\\n")
            .replace("\n", "\\n")
    }
}
