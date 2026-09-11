package com.amiya.pet.core.schedule

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.*
import java.util.regex.Pattern
import com.amiya.pet.widget.ScheduleWidgetProvider

object ScheduleManager {

    private val defaultSections = mapOf(
        "1" to "08:00", "2" to "08:50", "3" to "09:50", "4" to "10:40", "5" to "11:30",
        "6" to "14:05", "7" to "14:55", "8" to "15:45", "9" to "16:40", "10" to "17:30",
        "11" to "18:30", "12" to "19:20", "13" to "20:10"
    )

    var termStart: Date? = null
    var sections: Map<String, String> = defaultSections.toMap()
    var remindMinutes: Int = 10
    var courses: List<Course> = emptyList()
    var notes: List<String> = emptyList()

    private fun getScheduleFile(context: Context): File {
        return File(context.filesDir, "schedule.json")
    }

    fun load(context: Context) {
        val file = getScheduleFile(context)
        if (!file.exists()) return
        try {
            val jsonStr = file.readText()
            val data = JSONObject(jsonStr)

            val termStartStr = data.optString("term_start", "")
            if (termStartStr.isNotEmpty()) {
                val format = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault())
                termStart = format.parse(termStartStr)
            }

            val secObj = data.optJSONObject("sections")
            if (secObj != null) {
                val map = defaultSections.toMutableMap()
                for (key in secObj.keys()) {
                    map[key] = secObj.getString(key)
                }
                if (map["9"] in listOf("16:30", "16:35")) {
                    map["9"] = "16:40"
                }
                if (map["10"] == "18:30") {
                    map["10"] = "17:30"
                }
                if (map["11"] == "19:20") {
                    map["11"] = "18:30"
                }
                if (map["12"] == "20:10") {
                    map["12"] = "19:20"
                }
                if (map["13"] == "21:00") {
                    map["13"] = "20:10"
                }
                sections = map
            } else {
                sections = defaultSections.toMap()
            }

            remindMinutes = data.optInt("remind_minutes", 10)

            val courseList = mutableListOf<Course>()
            val coursesArray = data.optJSONArray("courses") ?: JSONArray()
            for (i in 0 until coursesArray.length()) {
                val c = coursesArray.getJSONObject(i)
                courseList.add(Course(
                    name = c.optString("name", ""),
                    weekday = c.optInt("weekday", 1),
                    secStart = c.optInt("sec_start", 1),
                    secEnd = c.optInt("sec_end", 1),
                    weekStart = c.optInt("week_start", 1),
                    weekEnd = c.optInt("week_end", 1),
                    parity = c.optString("parity", "all"),
                    room = c.optString("room", ""),
                    teacher = c.optString("teacher", ""),
                    campus = c.optString("campus", ""),
                    note = c.optString("note", "")
                ))
            }
            courses = courseList

            val notesList = mutableListOf<String>()
            val notesArray = data.optJSONArray("notes") ?: JSONArray()
            for (i in 0 until notesArray.length()) {
                notesList.add(notesArray.getString(i))
            }
            notes = notesList
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun save(context: Context) {
        try {
            val data = JSONObject()
            
            val termStartStr = termStart?.let { SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(it) } ?: ""
            data.put("term_start", termStartStr)

            val secObj = JSONObject()
            for ((k, v) in sections) {
                secObj.put(k, v)
            }
            data.put("sections", secObj)
            data.put("remind_minutes", remindMinutes)

            val coursesArray = JSONArray()
            for (c in courses) {
                val cObj = JSONObject()
                cObj.put("name", c.name)
                cObj.put("weekday", c.weekday)
                cObj.put("sec_start", c.secStart)
                cObj.put("sec_end", c.secEnd)
                cObj.put("week_start", c.weekStart)
                cObj.put("week_end", c.weekEnd)
                cObj.put("parity", c.parity)
                cObj.put("room", c.room)
                cObj.put("teacher", c.teacher)
                cObj.put("campus", c.campus)
                cObj.put("note", c.note)
                coursesArray.put(cObj)
            }
            data.put("courses", coursesArray)

            val notesArray = JSONArray()
            for (n in notes) {
                notesArray.put(n)
            }
            data.put("notes", notesArray)

            getScheduleFile(context).writeText(data.toString(2))
            ScheduleWidgetProvider.sendUpdateBroadcast(context)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun getWeekNo(date: Date = Date()): Int? {
        val start = termStart ?: return null
        val diff = date.time - start.time
        if (diff < 0) return 0
        return (diff / (7 * 24 * 60 * 60 * 1000)).toInt() + 1
    }

    fun getCoursesOn(weekday: Int, weekNo: Int? = null): List<Course> {
        return courses.filter { it.weekday == weekday && (weekNo == null || it.activeOn(weekNo)) }
            .sortedBy { it.secStart }
    }

    // 从强智教务 json 解析
    fun importStrongZhi(rawJsonStr: String, termStartDateStr: String): Pair<Boolean, String> {
        try {
            val raw = JSONObject(rawJsonStr)
            val kbList = raw.optJSONArray("kbList") ?: JSONArray()
            val sjkList = raw.optJSONArray("sjkList") ?: JSONArray()

            val newCourses = mutableListOf<Course>()
            val newNotes = mutableListOf<String>()

            for (i in 0 until kbList.length()) {
                val rec = kbList.getJSONObject(i)
                val zcd = rec.optString("zcd", "")
                val jc = rec.optString("jc", "")
                val name = rec.optString("kcmc", "").trim()
                if (zcd.isEmpty() || jc.isEmpty() || name.isEmpty()) continue

                val weeks = parseWeeks(zcd) ?: continue
                val secs = parseSections(jc) ?: continue
                val weekday = rec.optInt("xqj", 0)
                if (weekday !in 1..7) continue

                val room = getRoom(rec)
                val teacher = rec.optString("xm", "").trim()
                val campus = rec.optString("xqmc", "").trim()
                val note = if (rec.optString("pkbj") == "0") "实验" else ""

                newCourses.add(Course(
                    name = name,
                    weekday = weekday,
                    secStart = secs.first,
                    secEnd = secs.second,
                    weekStart = weeks.first,
                    weekEnd = weeks.second,
                    parity = weeks.third,
                    room = room,
                    teacher = teacher,
                    campus = campus,
                    note = note
                ))
            }

            for (i in 0 until sjkList.length()) {
                val rec = sjkList.getJSONObject(i)
                val name = rec.optString("kcmc", "").trim()
                if (name.isNotEmpty()) {
                    newNotes.add("$name / ${rec.optString("jsxm", "")} / ${rec.optString("qsjsz", "")}")
                }
            }

            if (termStartDateStr.isNotEmpty()) {
                val format = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault())
                termStart = format.parse(termStartDateStr)
            }
            
            courses = newCourses
            notes = newNotes
            
            return Pair(true, "导入成功：共解析 ${newCourses.size} 节课")
        } catch (e: Exception) {
            e.printStackTrace()
            return Pair(false, "解析失败：${e.localizedMessage}")
        }
    }

    private fun parseWeeks(zcd: String): Triple<Int, Int, String>? {
        val m = Pattern.compile("(\\d+)\\s*-\\s*(\\d+)").matcher(zcd)
        if (!m.find()) return null
        val start = m.group(1)?.toIntOrNull() ?: return null
        val end = m.group(2)?.toIntOrNull() ?: return null
        val parity = if (zcd.contains("双")) "even" else if (zcd.contains("单")) "odd" else "all"
        return Triple(start, end, parity)
    }

    private fun parseSections(jc: String): Pair<Int, Int>? {
        val m = Pattern.compile("(\\d+)\\s*-\\s*(\\d+)").matcher(jc)
        if (!m.find()) return null
        val start = m.group(1)?.toIntOrNull() ?: return null
        val end = m.group(2)?.toIntOrNull() ?: return null
        return Pair(start, end)
    }

    private fun getRoom(rec: JSONObject): String {
        val cdmc = rec.optString("cdmc", "").trim()
        if (cdmc.isNotEmpty() && cdmc != "未排地点") return cdmc
        val xkbz = rec.optString("xkbz", "").trim()
        val m = Pattern.compile("([A-Za-z]?\\d{2,4}[A-Za-z]?\\d*)$").matcher(xkbz)
        if (m.find()) {
            return m.group(1) ?: cdmc.ifEmpty { "待定" }
        }
        return cdmc.ifEmpty { "待定" }
    }


    fun nextClass(now: Date = Date()): CourseInfo? {
        val weekNo = getWeekNo(now) ?: return null
        if (weekNo <= 0) return null
        
        val calendar = Calendar.getInstance()
        calendar.time = now
        val todayIdx = calendar.get(Calendar.DAY_OF_WEEK)
        // Calendar.SUNDAY = 1, MONDAY = 2... We need MONDAY=1, SUNDAY=7
        val isoweekday = if (todayIdx == Calendar.SUNDAY) 7 else todayIdx - 1

        for (offset in 0..7) {
            val weekday = isoweekday + offset
            if (weekday > 7) continue // Simplified: only checking current week
            
            val targetCal = Calendar.getInstance()
            targetCal.time = now
            targetCal.add(Calendar.DAY_OF_YEAR, offset)
            
            for (c in getCoursesOn(weekday, weekNo)) {
                val hm = c.startTime(weekNo, sections) ?: continue
                
                targetCal.set(Calendar.HOUR_OF_DAY, hm.first)
                targetCal.set(Calendar.MINUTE, hm.second)
                targetCal.set(Calendar.SECOND, 0)
                targetCal.set(Calendar.MILLISECOND, 0)
                
                if (targetCal.time.time > now.time) {
                    return CourseInfo(c, weekday, weekNo, targetCal.time)
                }
            }
        }
        return null
    }

    /**
     * 构建供 AI 对话系统提示词直接使用的学情与课表全景分析文本档案
     */
    fun buildScheduleAnalysisContext(context: Context? = null): String {
        if (context != null && courses.isEmpty()) {
            load(context)
        }
        if (courses.isEmpty()) {
            return ""
        }

        val sb = StringBuilder()
        sb.append("【博士已导入的真实课表与学情数据档案】：\n")

        val now = Date()
        val weekNo = getWeekNo(now) ?: 1
        val cal = Calendar.getInstance()
        cal.time = now
        val todayIdx = cal.get(Calendar.DAY_OF_WEEK)
        val todayWeekday = if (todayIdx == Calendar.SUNDAY) 7 else todayIdx - 1
        val weekdayNames = arrayOf("", "周一", "周二", "周三", "周四", "周五", "周六", "周日")

        sb.append("- 当前学期进度：第 $weekNo 周（今日是 ${weekdayNames.getOrElse(todayWeekday) { "周一" }}）\n")

        // 1. 课程全景统计
        val distinctCourses = courses.map { it.name }.distinct()
        sb.append("- 修读科目清单（共 ${distinctCourses.size} 门）：${distinctCourses.joinToString("、")}\n")

        // 2. 本周各日课程与负荷
        sb.append("- 本周（第 $weekNo 周）各日排课与课时负荷：\n")
        var totalWeekSessions = 0
        val busyDays = mutableListOf<String>()
        val freeDays = mutableListOf<String>()

        for (w in 1..7) {
            val dayCourses = getCoursesOn(w, weekNo)
            var daySessions = 0
            for (c in dayCourses) {
                daySessions += (c.secEnd - c.secStart + 1)
            }
            totalWeekSessions += daySessions
            val wName = weekdayNames[w]
            if (dayCourses.isEmpty()) {
                freeDays.add(wName)
                sb.append("  * $wName：无课（全天空闲，建议规划自主复习、大作业攻坚或整理作息）\n")
            } else {
                if (daySessions >= 6) {
                    busyDays.add("$wName($daySessions 节)")
                }
                val details = dayCourses.joinToString("；") { c ->
                    val roomStr = if (c.room.isNotEmpty() && c.room != "待定") "@${c.room}" else ""
                    val teacherStr = if (c.teacher.isNotEmpty()) "(${c.teacher})" else ""
                    "${c.secStart}-${c.secEnd}节《${c.name}》$teacherStr$roomStr"
                }
                sb.append("  * $wName：共 $daySessions 节课 [ $details ]\n")
            }
        }
        sb.append("- 本周总课时：共 $totalWeekSessions 节课。\n")
        if (busyDays.isNotEmpty()) {
            sb.append("- 高负荷繁忙日：${busyDays.joinToString("、")}（课时密集，需注意提前预习与课间精力恢复）\n")
        }
        if (freeDays.isNotEmpty()) {
            sb.append("- 较空闲日：${freeDays.joinToString("、")}（拥有整块自主掌控时间，适合用于深入钻研核心科目或休整放松）\n")
        }

        // 3. 今日课程与下一门课
        val todayCourses = getCoursesOn(todayWeekday, weekNo)
        if (todayCourses.isNotEmpty()) {
            val todayStr = todayCourses.joinToString("；") { c ->
                val time = sections[c.secStart.toString()] ?: ""
                val timeStr = if (time.isNotEmpty()) "($time)" else ""
                "${c.secStart}-${c.secEnd}节$timeStr《${c.name}》@${c.room.ifEmpty { "待定" }}"
            }
            sb.append("- 今日（${weekdayNames.getOrElse(todayWeekday) { "" }}）课程安排：$todayStr\n")
        } else {
            sb.append("- 今日（${weekdayNames.getOrElse(todayWeekday) { "" }}）课程安排：今天没有排课，可自由安排学习或休息。\n")
        }

        val next = nextClass(now)
        if (next != null) {
            val timeFmt = SimpleDateFormat("HH:mm", Locale.getDefault()).format(next.startTime)
            val dayStr = if (next.weekday == todayWeekday) "今天" else weekdayNames.getOrElse(next.weekday) { "" }
            sb.append("- 下一节即将开始的课程：$dayStr $timeFmt ${next.course.secStart}-${next.course.secEnd}节《${next.course.name}》@${next.course.room.ifEmpty { "待定" }}\n")
        }

        // 4. 实训与网课/实验备忘
        if (notes.isNotEmpty()) {
            sb.append("- 实践与实训环节：${notes.joinToString("；")}\n")
        }

        return sb.toString().trim()
    }
}

data class CourseInfo(
    val course: Course,
    val weekday: Int,
    val weekNo: Int,
    val startTime: Date
)

