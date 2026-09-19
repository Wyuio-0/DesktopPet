package com.amiya.pet.core.schedule

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.setValue
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.*
import java.util.regex.Pattern
import com.amiya.pet.widget.ScheduleWidgetProvider
data class DeleteCourseQuery(
    val name: String,
    val weekday: Int? = null,
    val secStart: Int? = null,
    val targetWeek: Int? = null,
    val room: String? = null,
    val deleteAllWeeks: Boolean = true
)

data class ModifyCourseQuery(
    val targetName: String,
    val targetWeekday: Int? = null,
    val targetSecStart: Int? = null,
    val targetWeek: Int? = null,
    val newName: String? = null,
    val newWeekday: Int? = null,
    val newSecStart: Int? = null,
    val newSecEnd: Int? = null,
    val newRoom: String? = null,
    val newCustomTime: String? = null,
    val newTeacher: String? = null,
    val newWeekStart: Int? = null,
    val newWeekEnd: Int? = null
)

data class ModifyCourseResult(
    val oldCourse: Course,
    val newCourse: Course
)

/**
 * 教学安排调整（如中秋/国庆等假期的调课代课、停课放假）
 * type: "substitute" (代课/调课) 或 "suspend" (停课)
 */
data class ScheduleAdjustment(
    val id: String = UUID.randomUUID().toString(),
    val date: String,              // "yyyy-MM-dd", 例如 "2026-09-20"
    val type: String = "substitute", // "substitute" 或 "suspend"
    val targetWeek: Int? = null,    // 若 substitute，按第几周课表执行，例如 5
    val targetWeekday: Int? = null, // 若 substitute，按周几课表执行，例如 2 (周二)
    val reason: String = ""        // 调整原因/展示标签，如 "按第5周周二"、"中秋节停课"、"国庆节停课"
)

object ScheduleManager {

    private val defaultSections = mapOf(
        "1" to "08:00", "2" to "08:50", "3" to "09:50", "4" to "10:40", "5" to "11:30",
        "6" to "14:05", "7" to "14:55", "8" to "15:45", "9" to "16:40", "10" to "17:30",
        "11" to "18:30", "12" to "19:20", "13" to "20:10"
    )

    var termStart: Date? = null
    var sections: Map<String, String> = defaultSections.toMap()
    var remindEnabled: Boolean = true
    var dismissRemindEnabled: Boolean = true
    var remindMinutes: Int = 20
    var weekStartDay: String = "sunday"
    var courses: List<Course> = emptyList()
    var notes: List<String> = emptyList()
    var adjustments: List<ScheduleAdjustment> = emptyList()
    var coursesVersion: Int by mutableIntStateOf(0)

    private fun getScheduleFile(context: Context): File {
        return File(context.filesDir, "schedule.json")
    }

    fun normalizeToSunday(date: Date): Date {
        val cal = Calendar.getInstance().apply {
            time = date
            val dow = get(Calendar.DAY_OF_WEEK) // SUNDAY=1, MONDAY=2, ... SATURDAY=7
            val diff = Calendar.SUNDAY - dow // 1 - dow
            add(Calendar.DAY_OF_YEAR, diff)
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        return cal.time
    }

    fun normalizeToMonday(date: Date): Date {
        val cal = Calendar.getInstance().apply {
            time = date
            val dow = get(Calendar.DAY_OF_WEEK) // SUNDAY=1, MONDAY=2, ... SATURDAY=7
            val diff = if (dow == Calendar.SUNDAY) -6 else Calendar.MONDAY - dow
            add(Calendar.DAY_OF_YEAR, diff)
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        return cal.time
    }

    fun ensureLoaded(context: Context) {
        if (termStart == null || courses.isEmpty()) {
            load(context)
        }
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
                val parsed = format.parse(termStartStr)
                termStart = parsed?.let { normalizeToSunday(it) }
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

            remindEnabled = data.optBoolean("remind_enabled", true)
            dismissRemindEnabled = data.optBoolean("dismiss_remind_enabled", true)
            remindMinutes = data.optInt("remind_minutes", 20)
            val wsd = data.optString("week_start_day", "sunday").lowercase(Locale.getDefault())
            weekStartDay = if (wsd in listOf("monday", "sunday")) wsd else "sunday"

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
                    note = c.optString("note", ""),
                    customTime = c.optString("custom_time", ""),
                    id = c.optString("id", UUID.randomUUID().toString())
                ))
            }
            courses = courseList

            val notesList = mutableListOf<String>()
            val notesArray = data.optJSONArray("notes") ?: JSONArray()
            for (i in 0 until notesArray.length()) {
                notesList.add(notesArray.getString(i))
            }
            notes = notesList

            val adjList = mutableListOf<ScheduleAdjustment>()
            val adjArray = data.optJSONArray("adjustments") ?: JSONArray()
            for (i in 0 until adjArray.length()) {
                val a = adjArray.getJSONObject(i)
                adjList.add(ScheduleAdjustment(
                    id = a.optString("id", UUID.randomUUID().toString()),
                    date = a.optString("date", ""),
                    type = a.optString("type", "substitute"),
                    targetWeek = if (a.has("target_week") && !a.isNull("target_week")) a.getInt("target_week") else null,
                    targetWeekday = if (a.has("target_weekday") && !a.isNull("target_weekday")) a.getInt("target_weekday") else null,
                    reason = a.optString("reason", "")
                ))
            }
            adjustments = adjList.filter { it.date.isNotEmpty() }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun save(context: Context) {
        try {
            val data = JSONObject()
            
            val termStartStr = termStart?.let { SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(normalizeToSunday(it)) } ?: ""
            data.put("term_start", termStartStr)

            val secObj = JSONObject()
            for ((k, v) in sections) {
                secObj.put(k, v)
            }
            data.put("sections", secObj)
            data.put("remind_enabled", remindEnabled)
            data.put("dismiss_remind_enabled", dismissRemindEnabled)
            data.put("remind_minutes", remindMinutes)
            data.put("week_start_day", weekStartDay)

            val coursesArray = JSONArray()
            for (c in courses) {
                val cObj = JSONObject()
                cObj.put("id", c.id)
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
                if (c.customTime.isNotEmpty()) {
                    cObj.put("custom_time", c.customTime)
                }
                coursesArray.put(cObj)
            }
            data.put("courses", coursesArray)

            val notesArray = JSONArray()
            for (n in notes) {
                notesArray.put(n)
            }
            data.put("notes", notesArray)

            val adjArray = JSONArray()
            for (a in adjustments) {
                val aObj = JSONObject()
                aObj.put("id", a.id)
                aObj.put("date", a.date)
                aObj.put("type", a.type)
                if (a.targetWeek != null) aObj.put("target_week", a.targetWeek)
                if (a.targetWeekday != null) aObj.put("target_weekday", a.targetWeekday)
                aObj.put("reason", a.reason)
                adjArray.put(aObj)
            }
            data.put("adjustments", adjArray)

            getScheduleFile(context).writeText(data.toString(2))
            ScheduleWidgetProvider.sendUpdateBroadcast(context)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun setWeekStartDay(day: String, context: Context) {
        ensureLoaded(context)
        val d = day.lowercase(Locale.getDefault())
        if (d in listOf("monday", "sunday")) {
            weekStartDay = d
            coursesVersion++
            save(context)
        }
    }

    fun addCourse(course: Course, context: Context) {
        ensureLoaded(context)
        if (termStart == null) {
            termStart = normalizeToSunday(Date())
        }
        courses = courses + course
        coursesVersion++
        save(context)
    }

    fun updateCourse(course: Course, context: Context) {
        ensureLoaded(context)
        courses = courses.map { if (it.id == course.id) course else it }
        coursesVersion++
        save(context)
    }

    fun deleteCourse(courseId: String, context: Context) {
        ensureLoaded(context)
        courses = courses.filterNot { it.id == courseId }
        coursesVersion++
        save(context)
    }

    /**
     * 批量导入课程数据（支持全量覆盖或增量去重合并）
     */
    fun importCourses(newCourses: List<Course>, overwrite: Boolean, context: Context) {
        ensureLoaded(context)
        if (termStart == null) {
            termStart = normalizeToSunday(Date())
        }
        if (overwrite) {
            courses = newCourses
        } else {
            val existingKeys = courses.map { "${it.name.trim()}_${it.weekday}_${it.secStart}" }.toSet()
            val filteredNew = newCourses.filterNot { "${it.name.trim()}_${it.weekday}_${it.secStart}" in existingKeys }
            courses = courses + filteredNew
        }
        coursesVersion++
        save(context)
    }

    /**
     * 智能定位与打分匹配课表已有日程/课程
     */
    fun findTargetCourse(
        name: String,
        weekday: Int? = null,
        secStart: Int? = null,
        targetWeek: Int? = null,
        room: String? = null
    ): Course? {
        if (courses.isEmpty()) return null
        val cleanQuery = name.replace(Regex("^(?:一门|一节|个|场|次)?(?:课程|日程|活动|课)?"), "")
            .replace(Regex("(?:课|课程)$"), "")
            .trim()

        var bestMatch: Course? = null
        var bestScore = -1

        for (c in courses) {
            var score = 0
            val cName = c.name.trim()
            val cleanCName = cName.replace(Regex("(?:课|课程)$"), "").trim()

            // 1. 名称匹配与评分 (0 ~ 100)
            if (cleanQuery.isNotEmpty()) {
                if (cName.equals(name, ignoreCase = true) || cleanCName.equals(cleanQuery, ignoreCase = true)) {
                    score += 100
                } else if (cName.contains(cleanQuery, ignoreCase = true) || cleanQuery.contains(cleanCName, ignoreCase = true)) {
                    score += 70
                } else if (cleanQuery.length >= 2 && (cleanCName.contains(cleanQuery.substring(0, 2)) || cleanQuery.contains(cleanCName.take(2)))) {
                    score += 40
                } else {
                    continue
                }
            } else {
                score += 20
            }

            // 2. 星期打分 (40 分)
            if (weekday != null) {
                if (c.weekday == weekday) {
                    score += 40
                } else {
                    continue
                }
            }

            // 3. 节次打分 (30 分)
            if (secStart != null) {
                if (c.secStart == secStart || (secStart in c.secStart..c.secEnd)) {
                    score += 30
                } else if (Math.abs(c.secStart - secStart) <= 2) {
                    score += 10
                }
            }

            // 4. 周次打分 (25 分)
            if (targetWeek != null) {
                if (c.activeOn(targetWeek)) {
                    score += 25
                    if (c.weekStart == c.weekEnd && c.weekStart == targetWeek) {
                        score += 10 // 单周活动额外加分
                    }
                }
            }

            // 5. 地点打分 (15 分)
            if (!room.isNullOrBlank() && c.room.isNotBlank()) {
                if (c.room.contains(room, ignoreCase = true) || room.contains(c.room, ignoreCase = true)) {
                    score += 15
                }
            }

            if (score > bestScore) {
                bestScore = score
                bestMatch = c
            }
        }

        return bestMatch
    }

    /**
     * 根据删除请求匹配并删除日程/课程
     */
    fun deleteCourseMatching(query: DeleteCourseQuery, context: Context): Course? {
        ensureLoaded(context)
        val target = findTargetCourse(
            name = query.name,
            weekday = query.weekday,
            secStart = query.secStart,
            targetWeek = query.targetWeek,
            room = query.room
        ) ?: return null

        if (query.deleteAllWeeks || target.weekStart == target.weekEnd || query.targetWeek == null) {
            deleteCourse(target.id, context)
            return target
        }

        val tWeek = query.targetWeek
        if (tWeek < target.weekStart || tWeek > target.weekEnd) {
            deleteCourse(target.id, context)
            return target
        }

        // 单周豁免：若删除的是某一具体周次
        if (tWeek == target.weekStart) {
            val updated = target.copy(weekStart = target.weekStart + 1)
            updateCourse(updated, context)
        } else if (tWeek == target.weekEnd) {
            val updated = target.copy(weekEnd = target.weekEnd - 1)
            updateCourse(updated, context)
        } else {
            val part1 = target.copy(id = UUID.randomUUID().toString(), weekEnd = tWeek - 1)
            val part2 = target.copy(id = UUID.randomUUID().toString(), weekStart = tWeek + 1)
            courses = courses.filterNot { it.id == target.id } + listOf(part1, part2)
            coursesVersion++
            save(context)
        }
        return target
    }

    /**
     * 根据修改请求匹配并修改日程/课程
     */
    fun modifyCourseMatching(query: ModifyCourseQuery, context: Context): ModifyCourseResult? {
        ensureLoaded(context)
        val target = findTargetCourse(
            name = query.targetName,
            weekday = query.targetWeekday,
            secStart = query.targetSecStart,
            targetWeek = query.targetWeek
        ) ?: return null

        var updated = target

        if (!query.newName.isNullOrBlank()) {
            updated = updated.copy(name = query.newName.trim())
        }
        if (query.newWeekday != null && query.newWeekday in 1..7) {
            updated = updated.copy(weekday = query.newWeekday)
        }
        if (query.newSecStart != null) {
            val start = query.newSecStart.coerceIn(1, 13)
            val end = (query.newSecEnd ?: start).coerceIn(start, 13)
            updated = updated.copy(secStart = start, secEnd = end)
        }
        if (!query.newCustomTime.isNullOrBlank()) {
            val ct = query.newCustomTime.trim()
            updated = updated.copy(customTime = ct)
            if (ct.contains("-")) {
                val parts = ct.split("-")
                if (parts.size >= 2) {
                    val snapped = snapTimeToSections(parts[0].trim(), parts[1].trim())
                    updated = updated.copy(secStart = snapped.first, secEnd = snapped.second)
                }
            }
        }
        if (!query.newRoom.isNullOrBlank()) {
            updated = updated.copy(room = query.newRoom.trim())
        }
        if (!query.newTeacher.isNullOrBlank()) {
            updated = updated.copy(teacher = query.newTeacher.trim())
        }
        if (query.newWeekStart != null) {
            val ws = query.newWeekStart.coerceAtLeast(1)
            val we = (query.newWeekEnd ?: ws).coerceAtLeast(ws)
            updated = updated.copy(weekStart = ws, weekEnd = we)
        }

        updateCourse(updated, context)
        return ModifyCourseResult(oldCourse = target, newCourse = updated)
    }

    /**
     * 将任意时间范围（如 "14:15", "15:30"）智能吸附到课表 13 节体系中的最近节次区间
     */
    fun snapTimeToSections(startTimeStr: String, endTimeStr: String): Pair<Int, Int> {
        fun parseToMins(t: String): Int {
            val parts = t.trim().split(":", "：")
            if (parts.size >= 2) {
                val h = parts[0].trim().toIntOrNull() ?: 0
                val m = parts[1].trim().toIntOrNull() ?: 0
                return h * 60 + m
            }
            return 0
        }

        val startMins = parseToMins(startTimeStr)
        val endMins = parseToMins(endTimeStr).let { if (it <= startMins) startMins + 45 else it }

        val secTimes = (1..13).map { sec ->
            val time = sections[sec.toString()] ?: defaultSections[sec.toString()] ?: "08:00"
            val sm = parseToMins(time)
            val em = sm + 45
            Triple(sec, sm, em)
        }

        // 找最接近或包含 startMins 的节次
        var bestStartSec = 1
        var minDiff = Int.MAX_VALUE
        for ((sec, sm, em) in secTimes) {
            if (startMins in sm..em) {
                bestStartSec = sec
                break
            }
            val diff = Math.min(Math.abs(startMins - sm), Math.abs(startMins - em))
            if (diff < minDiff) {
                minDiff = diff
                bestStartSec = sec
            }
        }

        // 找最接近或包含 endMins 的节次
        var bestEndSec = bestStartSec
        var minEndDiff = Int.MAX_VALUE
        for ((sec, sm, em) in secTimes) {
            if (sec < bestStartSec) continue
            if (endMins in sm..em) {
                bestEndSec = sec
                break
            }
            val diff = Math.min(Math.abs(endMins - sm), Math.abs(endMins - em))
            if (diff < minEndDiff) {
                minEndDiff = diff
                bestEndSec = sec
            }
        }

        return Pair(bestStartSec.coerceIn(1, 13), bestEndSec.coerceIn(bestStartSec, 13))
    }

    /**
     * 判断是否为日程活动（非固定全学期常规课程）
     */
    fun isActivity(name: String, customTime: String = "", userText: String = ""): Boolean {
        if (customTime.isNotBlank()) return true
        val actKeywords = listOf(
            "组会", "会议", "例会", "研讨会", "讲座", "报告", "实验", "答疑", "班会",
            "活动", "自习", "培训", "体测", "体检", "竞赛", "比赛", "面试", "聚餐",
            "值日", "值班", "彩排", "宣讲会", "日程", "聚会"
        )
        return actKeywords.any { name.contains(it) || userText.contains(it) }
    }

    /**
     * 解析中文或阿拉伯数字（支持 1~99，如 "三"、"十二"、"25"）
     */
    fun parseChineseOrArabicNumber(str: String): Int {
        val trimmed = str.trim()
        trimmed.toIntOrNull()?.let { return it }
        if (trimmed == "两") return 2
        if (trimmed.startsWith("十")) {
            val unit = when (trimmed.removePrefix("十")) {
                "一" -> 1; "二", "两" -> 2; "三" -> 3; "四" -> 4; "五" -> 5; "六" -> 6; "七" -> 7; "八" -> 8; "九" -> 9; else -> 0
            }
            return 10 + unit
        }
        if (trimmed.contains("十")) {
            val parts = trimmed.split("十")
            val tens = when (parts[0]) {
                "一" -> 1; "二", "两" -> 2; "三" -> 3; "四" -> 4; "五" -> 5; "六" -> 6; "七" -> 7; "八" -> 8; "九" -> 9; else -> 1
            }
            val ones = if (parts.size > 1 && parts[1].isNotEmpty()) {
                when (parts[1]) {
                    "一" -> 1; "二", "两" -> 2; "三" -> 3; "四" -> 4; "五" -> 5; "六" -> 6; "七" -> 7; "八" -> 8; "九" -> 9; else -> 0
                }
            } else 0
            return tens * 10 + ones
        }
        return when (trimmed) {
            "一" -> 1; "二", "两" -> 2; "三" -> 3; "四" -> 4; "五" -> 5; "六" -> 6; "七" -> 7; "八" -> 8; "九" -> 9; else -> 1
        }
    }

    /**
     * 智能计算与校验课程/活动的起止周次：
     * 核心规则：对于让 AI 添加的活动（组会、会议、讲座、实验、自定义时间等日程），
     * 只要用户未说明是“持续几周”或“从第几周到第几周”，就一律只添加一个时间段（单周 weekStart == weekEnd）。
     */
    fun resolveWeekRange(
        userText: String,
        name: String,
        customTime: String,
        suggestedStart: Int = 1,
        suggestedEnd: Int = 16,
        currentWeek: Int = getWeekNo() ?: 1,
        maxWeek: Int = courses.maxOfOrNull { it.weekEnd } ?: 16
    ): Pair<Int, Int> {
        val trimmed = userText.trim()
        val isAct = isActivity(name, customTime, trimmed)

        // 1. 检查是否有明确的起止周次范围，如 "第3周到第8周", "3-8周", "从3周至8周", "3~8周"
        val rangeMatcher = Pattern.compile("(?:从|自|第)?\\s*([0-9一二两三四五六七八九十]+)\\s*周?\\s*[~至到与和\\-]\\s*(?:从|自|第)?\\s*([0-9一二两三四五六七八九十]+)\\s*周").matcher(trimmed)
        if (rangeMatcher.find()) {
            val s = parseChineseOrArabicNumber(rangeMatcher.group(1) ?: "1")
            val e = parseChineseOrArabicNumber(rangeMatcher.group(2) ?: s.toString())
            val start = s.coerceAtLeast(1)
            val end = e.coerceAtLeast(start)
            return Pair(start, end)
        }

        // 2. 检查是否有明确的持续周数，如 "持续3周", "连开2周", "一共4周", "连着3周"
        val durationMatcher = Pattern.compile("(?:持续|连开|一共|共|连续|连着)\\s*([0-9一二两三四五六七八九十]+)\\s*周").matcher(trimmed)
        if (durationMatcher.find()) {
            val dur = parseChineseOrArabicNumber(durationMatcher.group(1) ?: "1").coerceAtLeast(1)
            val startWeek = when {
                trimmed.contains("下下周") || trimmed.contains("下下星期") -> currentWeek + 2
                trimmed.contains("下周") || trimmed.contains("下星期") || trimmed.contains("下礼拜") -> currentWeek + 1
                else -> {
                    val singleWeekMatcher = Pattern.compile("第\\s*([0-9一二两三四五六七八九十]+)\\s*周").matcher(trimmed)
                    if (singleWeekMatcher.find()) {
                        parseChineseOrArabicNumber(singleWeekMatcher.group(1) ?: currentWeek.toString())
                    } else {
                        currentWeek
                    }
                }
            }.coerceAtLeast(1)
            return Pair(startWeek, startWeek + dur - 1)
        }

        // 3. 检查是否有全学期/每周周期性描述，如 "每周", "每星期", "每个礼拜", "整学期", "整个学期", "全学期"
        val isWeekly = trimmed.contains("每周") || trimmed.contains("每星期") || trimmed.contains("每个礼拜") ||
                       trimmed.contains("整学期") || trimmed.contains("整个学期") || trimmed.contains("全学期")
        if (isWeekly) {
            val startWeek = if (isAct) currentWeek.coerceAtLeast(1) else 1
            return Pair(startWeek, maxWeek.coerceAtLeast(startWeek))
        }

        // 4. 活动（Activity）且未说明持续几周或起止周次：严格只添加一个时间段（单周）
        if (isAct) {
            val targetWeek = when {
                trimmed.contains("下下周") || trimmed.contains("下下星期") -> currentWeek + 2
                trimmed.contains("下周") || trimmed.contains("下星期") || trimmed.contains("下礼拜") -> currentWeek + 1
                trimmed.contains("这周") || trimmed.contains("本周") || trimmed.contains("这星期") || trimmed.contains("本星期") -> currentWeek
                else -> {
                    val singleWeekMatcher = Pattern.compile("第\\s*([0-9一二两三四五六七八九十]+)\\s*周").matcher(trimmed)
                    if (singleWeekMatcher.find()) {
                        parseChineseOrArabicNumber(singleWeekMatcher.group(1) ?: currentWeek.toString())
                    } else if (suggestedStart == suggestedEnd && suggestedStart > 0) {
                        // 若传入的模型解析建议已为明确的单周，则尊重建议
                        suggestedStart
                    } else {
                        currentWeek
                    }
                }
            }.coerceAtLeast(1)
            return Pair(targetWeek, targetWeek)
        }

        // 5. 常规学期专业课程
        val singleWeekMatcher = Pattern.compile("第\\s*([0-9一二两三四五六七八九十]+)\\s*周").matcher(trimmed)
        if (singleWeekMatcher.find()) {
            val w = parseChineseOrArabicNumber(singleWeekMatcher.group(1) ?: "1").coerceAtLeast(1)
            return Pair(w, w)
        }
        if (trimmed.contains("下周") || trimmed.contains("下星期")) {
            val w = (currentWeek + 1).coerceAtLeast(1)
            return Pair(w, w)
        }

        val s = if (suggestedStart in 1..maxWeek) suggestedStart else 1
        val e = if (suggestedEnd in s..maxWeek) suggestedEnd else maxWeek
        return Pair(s, e)
    }

    /**
     * 本地规则辅助解析自然语言课程与活动描述（作为 AI 代码块缺失时的安全兜底）
     */
    fun parseCourseFromNaturalLanguage(text: String): Course? {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) return null

        // 0. 负向意图过滤：若用户意图为删除、退课、修改、查课等，绝不误添加课程
        val negativeWords = listOf(
            "删除", "删掉", "删了", "退课", "取消", "移除", "不要这", "不要",
            "修改", "改一下", "改成", "改到", "不是这", "查一下", "看下课表", "今天有什么课", "有什么课", "不对"
        )
        if (negativeWords.any { trimmed.contains(it) }) {
            return null
        }

        // 1. 地点/教室精确提取（先提取地点，防止被课程名误吞或粘连）
        var room = ""
        val roomBoundaryMatcher = Pattern.compile("(?:在|@|教室(?:在|是)?|地点(?:在|是)?)\\s*([a-zA-Z0-9\\u4e00-\\u9fa5\\-]{2,12}?)(?=[的开上听做学有搞举行举办参加跑打，,。、\\s]|$)").matcher(trimmed)
        if (roomBoundaryMatcher.find()) {
            room = roomBoundaryMatcher.group(1)?.trim() ?: ""
        } else {
            val roomPatternMatcher = Pattern.compile("(?:在|@|教室(?:在|是)?|地点(?:在|是)?)\\s*([a-zA-Z0-9\\u4e00-\\u9fa5\\-]{1,12}?(?:楼[0-9A-Za-z\\-]*|室|教室|馆|栋|区[0-9A-Za-z\\-]+|操场|球场|[0-9]{3,4}|[教综信文生化美图东西南][一二三四五六七八九十0-9]+))").matcher(trimmed)
            if (roomPatternMatcher.find()) {
                room = roomPatternMatcher.group(1)?.trim() ?: ""
            }
        }
        room = room.removeSuffix("开").removeSuffix("去").removeSuffix("上").removeSuffix("参加").removeSuffix("有").removeSuffix("搞").removeSuffix("进行").removeSuffix("听").trim()
        if (room in listOf("学校", "这里", "那里", "上面", "这个")) {
            room = ""
        }

        // 2. 提取课程/活动名称
        var name = ""
        // A. 明确书名号/各种引号中的名称优先提取 《...》 / “...” / '...' / 「...」
        val bookMarkMatcher = Pattern.compile("[《“「]([^》”」]+)[》”」]").matcher(trimmed)
        if (bookMarkMatcher.find()) {
            name = bookMarkMatcher.group(1)?.trim() ?: ""
        }

        // B. 显式冒号/标签指定名称 (例如：“课程：高等数学”、“活动：羽毛球友谊赛”、“日程：例会”)
        if (name.isEmpty()) {
            val labelMatcher = Pattern.compile("(?:课程|日程|活动|主题)(?:名|名称)?\\s*[:：]\\s*([a-zA-Z0-9\\u4e00-\\u9fa5]{2,15}?)(?=[,，。、\\s在从第周]|$)").matcher(trimmed)
            if (labelMatcher.find()) {
                val cand = labelMatcher.group(1)?.trim() ?: ""
                val timeWords = listOf("上午", "下午", "晚上", "中午", "今天", "明天", "后天", "这周", "下周", "周一", "周二", "周三", "周四", "周五", "周六", "周日")
                if (cand !in listOf("课程", "日程", "活动", "这个", "上面", "时间", "安排") && timeWords.none { cand.contains(it) }) {
                    name = cand
                }
            }
        }

        // 预清理问候语与无用前缀以辅助后续句式识别
        var raw = trimmed
        while (true) {
            val cleaned = raw
                .replaceFirst(Regex("^(?:阿米娅|请问|请|麻烦您|麻烦你|麻烦帮我|请帮我|麻烦|帮我|可以帮我|帮|给我)+[,，\\s]*"), "")
                .replaceFirst(Regex("^(?:添加|录入|加上?|补上?|有一门|有一节|加一门|加一节|加个|新加|新建|安排|记一下|记录)+[,，\\s]*"), "")
                .replaceFirst(Regex("^(?:一门|一节|个|场|次)?(?:课程|日程|活动|事项)?[:：\\s]*"), "")
            if (cleaned == raw) break
            raw = cleaned
        }

        // C. 句式：“在 [地点] 的 [课程/活动名]” (例如：“周三第3-4节在教三201的高等数学”)
        if (name.isEmpty()) {
            val deMatcher = Pattern.compile("(?:在|@)\\s*[a-zA-Z0-9\\u4e00-\\u9fa5\\-]{2,15}?\\s*的\\s*([a-zA-Z0-9\\u4e00-\\u9fa5]{2,15}?)(?:课|课程)?(?=[,，。、\\s]|$)").matcher(raw)
            if (deMatcher.find()) {
                name = deMatcher.group(1)?.trim() ?: ""
            }
        }

        // D. 句式：“在 [地点] [开/上/听/做/学/有/搞/举行/举办/参加] [课程/活动名]” (例如：“在综合楼402开实验室组会”、“在西十二上操作系统”)
        if (name.isEmpty()) {
            val vMatcher = Pattern.compile("(?:在|@)\\s*[a-zA-Z0-9\\u4e00-\\u9fa5\\-]{2,15}?\\s*(?:开|上|听|做|学|有|搞|举行|举办|参加)\\s*(?:一门|一节|个|场|场次|次)?\\s*([a-zA-Z0-9\\u4e00-\\u9fa5]{2,15}?)(?:课|课程)?(?=[,，。、\\s]|$)").matcher(raw)
            if (vMatcher.find()) {
                name = vMatcher.group(1)?.trim() ?: ""
            }
        }

        // E. 句式：“[课程/活动名] 在 [地点]” (例如：“高等数学在东九B101”、“例会在行政楼”)
        if (name.isEmpty() && room.isNotEmpty()) {
            val cMatcher = Pattern.compile("(?:[，,、\\s:：]|^)(?:开|上|听|做|学|有|加|录入)?\\s*([a-zA-Z0-9\\u4e00-\\u9fa5]{2,15}?)(?:课|课程)?\\s*(?:在|@)\\s*" + Pattern.quote(room)).matcher(raw)
            if (cMatcher.find()) {
                val cand = cMatcher.group(1)?.trim() ?: ""
                val timeWords = listOf("上午", "下午", "晚上", "中午", "今天", "明天", "后天", "这周", "下周", "周一", "周二", "周三", "周四", "周五", "周六", "周日")
                if (timeWords.none { cand.contains(it) } && !Pattern.compile("[0-9]+[点节分]").matcher(cand).find()) {
                    name = cand
                }
            }
        }

        // F. 专属具体活动词匹配 (排除宽泛的“活动”、“日程”)
        if (name.isEmpty()) {
            val actKeywords = listOf(
                "实验室组会", "组会", "教研会", "研讨会", "班会", "例会", "座谈会", "晚会", "宣讲会", "会议", "聚会",
                "早会", "晚自习", "自习",
                "学术讲座", "讲座", "学术报告", "报告",
                "物理实验", "化学实验", "生物实验", "实验", "答疑",
                "培训", "体测", "体检", "竞赛", "比赛", "面试", "聚餐",
                "四六级考试", "四六级", "英语四级", "英语六级", "期末考", "期中考", "模拟考", "考试",
                "值日", "值班", "彩排", "跑步打卡", "跑步", "打球", "运动"
            )
            for (kw in actKeywords) {
                if (raw.contains(kw)) {
                    val actMatcher = Pattern.compile("(?:(?:开|举办|进行|参加|去|听|做|上|搞|有|考|复习)\\s*(?:个|场|次)?)?\\s*([\\u4e00-\\u9fa5]{0,6}?" + Pattern.quote(kw) + ")").matcher(raw)
                    if (actMatcher.find()) {
                        var cand = actMatcher.group(1)?.trim() ?: kw
                        if (room.isNotEmpty() && cand.contains(room)) {
                            cand = cand.replace(room, "")
                        }
                        cand = cand.replace(Regex("^(?:在|去|开|上|参加|有|搞|进行|听|个|场|次|门|考|点)+"), "").trim()
                        cand = cand.replace(Regex("^(?:周[一二三四五六日天七]|星期[一二三四五六日天七]|上午|下午|晚上|中午|[0-9]{1,2}点)+"), "").trim()
                        if (cand.contains(kw)) {
                            name = cand
                            break
                        }
                    } else {
                        // 检查是否在 room 之后
                        if (room.isNotEmpty() && raw.contains(room)) {
                            val afterRoom = raw.substringAfter(room)
                            if (afterRoom.contains(kw)) {
                                var cand = afterRoom.replace(Regex("^(?:在|去|开|上|参加|有|搞|进行|听|个|场|次|门|考|点)+"), "").trim()
                                cand = cand.split(Regex("[,，。、\\s持续]"))[0]
                                if (cand.contains(kw)) {
                                    name = cand
                                    break
                                }
                            }
                        }
                        name = kw
                        break
                    }
                }
            }
        }

        // G. 常见动词 [有/上/加/补/去上] [课程名] (例如：“周二3-4节有大学物理”)
        if (name.isEmpty()) {
            val verbMatcher = Pattern.compile("(?<![早中晚])(?:有|上|加|补|去上)(?![午海])\\s*(?:一门|一节|个|场)?\\s*([a-zA-Z0-9\\u4e00-\\u9fa5]{2,12}?)(?:课|课程)?(?=[,，。、\\s在@从第周点]|$)").matcher(raw)
            if (verbMatcher.find()) {
                val cand = verbMatcher.group(1)?.trim() ?: ""
                val timeWords = listOf("上午", "下午", "晚上", "中午", "今天", "明天", "后天", "这周", "下周", "周一", "周二", "周三", "周四", "周五", "周六", "周日")
                if (!Pattern.compile("^[0-9一两二三四五六七八九十]+[点节分时]").matcher(cand).find() &&
                    cand !in listOf("课程", "日程", "活动", "这个", "上面", "时间", "安排") &&
                    timeWords.none { cand.contains(it) }) {
                    name = cand
                }
            }
        }

        // H. 节次后紧跟课程名 (例如：“周五第5节自习”)
        if (name.isEmpty()) {
            val secMatcher = Pattern.compile("(?:[0-9]{1,2}\\s*[~至到与和/\\-]?\\s*[0-9]{1,2}?\\s*节)\\s*([a-zA-Z0-9\\u4e00-\\u9fa5]{2,12}?)(?:课|课程)?(?=[,，。、\\s]|$)").matcher(raw)
            if (secMatcher.find()) {
                val cand = secMatcher.group(1)?.trim() ?: ""
                if (cand !in listOf("课程", "日程", "活动", "这个", "上面", "时间", "安排")) {
                    name = cand
                }
            }
        }

        // I. 句首直接是课程名 (例如：“高等数学，周二第1-2节”)
        if (name.isEmpty()) {
            val startMatcher = Pattern.compile("^([a-zA-Z0-9\\u4e00-\\u9fa5]{2,12}?)(?:课|课程)?(?=[,，。、\\s在@从第周点]|$)").matcher(raw)
            if (startMatcher.find()) {
                val cand = startMatcher.group(1)?.trim() ?: ""
                val timeWords = listOf("上午", "下午", "晚上", "中午", "今天", "明天", "后天", "这周", "下周", "周一", "周二", "周三", "周四", "周五", "周六", "周日")
                if (cand !in listOf("课程", "日程", "活动", "这个", "上面", "时间", "安排") && timeWords.none { cand.contains(it) }) {
                    name = cand
                }
            }
        }

        // 清理 name 前后缀与噪音
        if (name.isNotEmpty()) {
            name = name.replace(Regex("^(?:在|@|个|次|场|开|去|参加|有|门|一门|一节|一个|这门|这节|加|加上|考|点)+"), "").trim()
            name = name.replace(Regex("(?:持续[0-9一两二三四五六七八九十]+周.*|[，,。、].*)$"), "").trim()
            name = name.replace(Regex("^(?:周[一二三四五六日天七]|星期[一二三四五六日天七]|上午|下午|晚上|中午|[0-9]{1,2}点)+"), "").trim()
            name = name.replace(Regex("(?:[0-9]{1,2}[:点][0-9]{2}|[0-9]{1,2}点)+.*$"), "").trim()
            if (name.endsWith("课") && name.length >= 3 && !name.endsWith("网球课")) {
                name = name.dropLast(1)
            }
        }

        // 非法名称防御
        val invalidNames = setOf("课表", "课", "这节课", "我的课", "一节", "一门", "活动", "这个活动", "日程", "安排", "这个", "上面", "新日程", "")
        if (name.isEmpty() || name in invalidNames || (name.startsWith("午") && name.length <= 3) || name.matches(Regex("^[0-9]+$"))) {
            return null
        }

        // 2. 星期
        val weekday = when {
            trimmed.contains("周一") || trimmed.contains("星期一") || trimmed.contains("礼拜一") -> 1
            trimmed.contains("周二") || trimmed.contains("星期二") || trimmed.contains("礼拜二") -> 2
            trimmed.contains("周三") || trimmed.contains("星期三") || trimmed.contains("礼拜三") -> 3
            trimmed.contains("周四") || trimmed.contains("星期四") || trimmed.contains("礼拜四") -> 4
            trimmed.contains("周五") || trimmed.contains("星期五") || trimmed.contains("礼拜五") -> 5
            trimmed.contains("周六") || trimmed.contains("星期六") || trimmed.contains("礼拜六") -> 6
            trimmed.contains("周日") || trimmed.contains("周天") || trimmed.contains("星期日") || trimmed.contains("星期天") || trimmed.contains("礼拜日") || trimmed.contains("礼拜天") -> 7
            else -> {
                val cal = Calendar.getInstance()
                val d = cal.get(Calendar.DAY_OF_WEEK)
                if (d == Calendar.SUNDAY) 7 else d - 1
            }
        }

        // 3. 节次与精确时间（支持智能吸附）
        var secStart = 1
        var secEnd = 2
        var customTime = ""

        // A. 尝试提取精准数字时钟时间，例如 "14:15-15:30", "14:15至15:30", "14:15到15:30", "14:15~15:30"
        val digitalTimeMatcher = Pattern.compile("([0-9]{1,2})[:点：]([0-9]{2})\\s*[~至到与和/到\\-]\\s*([0-9]{1,2})[:点：]([0-9]{2})").matcher(trimmed)
        // B. 尝试提取中文时钟时间，例如 "下午两点十五到三点半", "晚上7点到8点30分"
        val chineseTimeMatcher = Pattern.compile("(下午|晚上|中午|上午|早晨|清晨)?\\s*([0-9一两二三四五六七八九十]{1,2})[点:：时]\\s*([0-9]{1,2}|半|一刻|三刻)?(?:分)?\\s*[~至到与和/到\\-]\\s*(?:下午|晚上|中午|上午)?\\s*([0-9一两二三四五六七八九十]{1,2})[点:：时]\\s*([0-9]{1,2}|半|一刻|三刻)?(?:分)?").matcher(trimmed)

        if (digitalTimeMatcher.find()) {
            val sh = digitalTimeMatcher.group(1)?.toIntOrNull() ?: 8
            val sm = digitalTimeMatcher.group(2)?.toIntOrNull() ?: 0
            val eh = digitalTimeMatcher.group(3)?.toIntOrNull() ?: (sh + 1)
            val em = digitalTimeMatcher.group(4)?.toIntOrNull() ?: 0
            val stStr = "%02d:%02d".format(Locale.getDefault(), sh, sm)
            val etStr = "%02d:%02d".format(Locale.getDefault(), eh, em)
            customTime = "$stStr-$etStr"
            val snapped = snapTimeToSections(stStr, etStr)
            secStart = snapped.first
            secEnd = snapped.second
        } else if (chineseTimeMatcher.find()) {
            fun parseH(hStr: String, isPm: Boolean): Int {
                var h = when(hStr) {
                    "一", "1" -> 1; "二", "两", "2" -> 2; "三", "3" -> 3; "四", "4" -> 4; "五", "5" -> 5
                    "六", "6" -> 6; "七", "7" -> 7; "八", "8" -> 8; "九", "9" -> 9; "十", "10" -> 10
                    "十一", "11" -> 11; "十二", "12" -> 12
                    else -> hStr.toIntOrNull() ?: 8
                }
                if (isPm && h < 12) h += 12
                return h
            }
            fun parseM(mStr: String?): Int {
                return when(mStr) {
                    "半" -> 30
                    "一刻" -> 15
                    "三刻" -> 45
                    null, "" -> 0
                    else -> mStr.toIntOrNull() ?: 0
                }
            }
            val isPm = trimmed.contains("下午") || trimmed.contains("晚上")
            val sh = parseH(chineseTimeMatcher.group(2) ?: "8", isPm)
            val sm = parseM(chineseTimeMatcher.group(3))
            val eh = parseH(chineseTimeMatcher.group(4) ?: (sh + 1).toString(), isPm)
            val em = parseM(chineseTimeMatcher.group(5))
            val stStr = "%02d:%02d".format(Locale.getDefault(), sh, sm)
            val etStr = "%02d:%02d".format(Locale.getDefault(), eh, em)
            customTime = "$stStr-$etStr"
            val snapped = snapTimeToSections(stStr, etStr)
            secStart = snapped.first
            secEnd = snapped.second
        } else {
            val secRangeMatcher = Pattern.compile("(?:第)?([0-9]{1,2})\\s*[~至到与和\\-]\\s*([0-9]{1,2})\\s*节").matcher(trimmed)
            if (secRangeMatcher.find()) {
                secStart = secRangeMatcher.group(1)?.toIntOrNull() ?: 1
                secEnd = secRangeMatcher.group(2)?.toIntOrNull() ?: secStart
            } else {
                val singleSecMatcher = Pattern.compile("(?:第)?([0-9]{1,2})\\s*节").matcher(trimmed)
                if (singleSecMatcher.find()) {
                    secStart = singleSecMatcher.group(1)?.toIntOrNull() ?: 1
                    secEnd = (secStart + 1).coerceAtMost(13)
                } else if (trimmed.contains("下午两点") || trimmed.contains("14:00") || trimmed.contains("14点")) {
                    secStart = 6; secEnd = 7
                } else if (trimmed.contains("上午八点") || trimmed.contains("8:00") || trimmed.contains("8点")) {
                    secStart = 1; secEnd = 2
                } else if (trimmed.contains("上午十点") || trimmed.contains("10:00") || trimmed.contains("10点")) {
                    secStart = 3; secEnd = 4
                } else if (trimmed.contains("晚上七点") || trimmed.contains("19:00") || trimmed.contains("19点")) {
                    secStart = 11; secEnd = 12
                }
            }
        }
        secStart = secStart.coerceIn(1, 13)
        secEnd = secEnd.coerceIn(secStart, 13)

        // 4. 地点/教室兜底补充
        if (room.isEmpty()) {
            val roomMatcher = Pattern.compile("(?:在|@|教室(?:在|是)?|地点(?:在|是)?)\\s*([a-zA-Z0-9\\u4e00-\\u9fa5]{2,15}?(?:楼|室|教室|馆|栋|区|[0-9]{3,4}|[教综信文生化美图][一二三四五六七八九十0-9]+))").matcher(trimmed)
            if (roomMatcher.find()) {
                room = roomMatcher.group(1)?.trim() ?: ""
            }
        }

        // 5. 教师/负责人
        var teacher = ""
        val teacherMatcher = Pattern.compile("([\\u4e00-\\u9fa5]{2,4})(?:老师|教授|学长|学姐|主持)").matcher(trimmed)
        if (teacherMatcher.find()) {
            teacher = teacherMatcher.group(1) ?: ""
        }

        val maxWeek = courses.maxOfOrNull { it.weekEnd } ?: 16
        val curWeek = getWeekNo() ?: 1
        val weekRange = resolveWeekRange(trimmed, name, customTime, 1, maxWeek, curWeek, maxWeek)
        return Course(
            name = name,
            weekday = weekday,
            secStart = secStart,
            secEnd = secEnd,
            weekStart = weekRange.first,
            weekEnd = weekRange.second,
            parity = "all",
            room = room,
            teacher = teacher,
            customTime = customTime,
            note = if (customTime.isNotEmpty()) "AI活动录入" else "AI智能录入"
        )
    }

    /**
     * 解析自然语言中的星期指示词
     */
    fun parseWeekdayFromText(text: String, currentWeekday: Int = Calendar.getInstance().let {
        val d = it.get(Calendar.DAY_OF_WEEK)
        if (d == Calendar.SUNDAY) 7 else d - 1
    }): Int? {
        return when {
            text.contains("大后天") -> (currentWeekday + 2) % 7 + 1
            text.contains("后天") -> (currentWeekday + 1) % 7 + 1
            text.contains("明天") -> currentWeekday % 7 + 1
            text.contains("今天") -> currentWeekday
            text.contains("周一") || text.contains("星期一") || text.contains("礼拜一") -> 1
            text.contains("周二") || text.contains("星期二") || text.contains("礼拜二") -> 2
            text.contains("周三") || text.contains("星期三") || text.contains("礼拜三") -> 3
            text.contains("周四") || text.contains("星期四") || text.contains("礼拜四") -> 4
            text.contains("周五") || text.contains("星期五") || text.contains("礼拜五") -> 5
            text.contains("周六") || text.contains("星期六") || text.contains("礼拜六") -> 6
            text.contains("周日") || text.contains("周天") || text.contains("星期日") || text.contains("星期天") || text.contains("礼拜日") || text.contains("礼拜天") -> 7
            else -> null
        }
    }

    /**
     * 解析自然语言中的周次指示词
     */
    fun parseWeekFromText(text: String, currentWeek: Int = getWeekNo() ?: 1): Int? {
        if (text.contains("下下周") || text.contains("下下星期")) return currentWeek + 2
        if (text.contains("下周") || text.contains("下星期") || text.contains("下礼拜")) return currentWeek + 1
        if (text.contains("这周") || text.contains("本周") || text.contains("这星期") || text.contains("本星期")) return currentWeek
        val m = Pattern.compile("第\\s*([0-9一二两三四五六七八九十]+)\\s*周").matcher(text)
        if (m.find()) {
            return parseChineseOrArabicNumber(m.group(1) ?: currentWeek.toString())
        }
        return null
    }

    /**
     * 解析自然语言中的节次/时段信息
     */
    fun parseSectionsOrTimeFromText(text: String): Triple<Int?, Int?, String> {
        val digMatcher = Pattern.compile("([0-9]{1,2})[:点：]([0-9]{2})\\s*[~至到与和/到\\-]\\s*([0-9]{1,2})[:点：]([0-9]{2})").matcher(text)
        if (digMatcher.find()) {
            val sh = digMatcher.group(1)?.toIntOrNull() ?: 8
            val sm = digMatcher.group(2)?.toIntOrNull() ?: 0
            val eh = digMatcher.group(3)?.toIntOrNull() ?: (sh + 1)
            val em = digMatcher.group(4)?.toIntOrNull() ?: 0
            val stStr = "%02d:%02d".format(Locale.getDefault(), sh, sm)
            val etStr = "%02d:%02d".format(Locale.getDefault(), eh, em)
            val snapped = snapTimeToSections(stStr, etStr)
            return Triple(snapped.first, snapped.second, "$stStr-$etStr")
        }
        val secRangeMatcher = Pattern.compile("(?:第)?([0-9]{1,2})\\s*[~至到与和\\-]\\s*([0-9]{1,2})\\s*节").matcher(text)
        if (secRangeMatcher.find()) {
            val s = secRangeMatcher.group(1)?.toIntOrNull()
            val e = secRangeMatcher.group(2)?.toIntOrNull() ?: s
            return Triple(s, e, "")
        }
        val singleSecMatcher = Pattern.compile("(?:第)?([0-9]{1,2})\\s*节").matcher(text)
        if (singleSecMatcher.find()) {
            val s = singleSecMatcher.group(1)?.toIntOrNull()
            return Triple(s, s, "")
        }
        if (text.contains("下午两点") || text.contains("14:00") || text.contains("14点")) return Triple(6, 7, "14:00-15:30")
        if (text.contains("下午三点") || text.contains("15:00") || text.contains("15点")) return Triple(7, 8, "15:00-16:30")
        if (text.contains("下午四点") || text.contains("16:00") || text.contains("16点")) return Triple(8, 9, "16:00-17:30")
        if (text.contains("晚上七点") || text.contains("19:00") || text.contains("19点")) return Triple(11, 12, "19:00-20:30")
        if (text.contains("上午八点") || text.contains("8:00") || text.contains("8点")) return Triple(1, 2, "08:00-09:35")
        if (text.contains("上午十点") || text.contains("10:00") || text.contains("10点")) return Triple(3, 4, "10:00-11:35")
        if (text.contains("下午")) return Triple(6, 7, "")
        if (text.contains("上午")) return Triple(1, 2, "")
        if (text.contains("晚上")) return Triple(11, 12, "")
        return Triple(null, null, "")
    }

    /**
     * 解析自然语言中的地点/教室
     */
    fun parseRoomFromText(text: String): String {
        val roomMatcher = Pattern.compile("([a-zA-Z0-9\\u4e00-\\u9fa5\\-]{2,15}?(?:楼[0-9A-Za-z\\-]*|室|教室|馆|栋|区|[0-9]{3,4}|[教综信文生化美图东西南][一二三四五六七八九十0-9]+))").matcher(text)
        if (roomMatcher.find()) {
            val cand = roomMatcher.group(1)?.trim() ?: ""
            val invalidWords = listOf("星期", "礼拜", "自习", "会议", "组会", "例会", "时间", "安排")
            if (invalidWords.none { cand.contains(it) }) {
                return cand
            }
        }
        return ""
    }

    /**
     * 本地 NLP 解析自然语言删除与取消日程请求
     */
    fun parseDeleteFromNaturalLanguage(text: String, context: Context): Course? {
        val trimmed = text.trim()
        val delKeywords = listOf("删除", "删掉", "删了", "退课", "取消", "移除", "去掉", "不开", "不上了")
        if (delKeywords.none { trimmed.contains(it) }) return null

        ensureLoaded(context)
        var raw = trimmed
            .replaceFirst(Regex("^(?:阿米娅|请问|请|麻烦您|麻烦你|麻烦帮我|请帮我|麻烦|帮我|可以帮我|帮|给我)+[,，\\s]*"), "")

        var targetStr = ""
        val m1 = Pattern.compile("(?:把|将)\\s*([^,，。!！?？]+?)\\s*(?:从课表|从日程)?\\s*(?:取消|删除|删掉|删了|退课|移除|去掉|不开)").matcher(raw)
        if (m1.find()) {
            targetStr = m1.group(1)?.trim() ?: ""
        } else {
            val m2 = Pattern.compile("(?:取消|删除|删掉|删了|退课|移除|去掉)\\s*(?:一门|一节|个|场|次)?\\s*(?:从课表|从日程)?\\s*([^,，。!！?？]+)").matcher(raw)
            if (m2.find()) {
                var cand = m2.group(1)?.trim() ?: ""
                cand = cand.replace(Regex("^(?:掉|了|吧|一下)+"), "").trim()
                if (cand.length >= 2 && cand !in listOf("一下", "这个", "上面", "课表", "日程")) {
                    targetStr = cand
                }
            }
            if (targetStr.isEmpty()) {
                val m3 = Pattern.compile("([^,，。!！?？]+?)\\s*(?:退课|不开了|不开|取消|删除|删了|删掉)").matcher(raw)
                if (m3.find()) {
                    targetStr = m3.group(1)?.trim() ?: ""
                }
            }
        }

        val subject = if (targetStr.isNotEmpty()) targetStr else raw

        val weekday = parseWeekdayFromText(subject) ?: parseWeekdayFromText(raw)
        val curWeek = getWeekNo() ?: 1
        val targetWeek = parseWeekFromText(subject, curWeek) ?: parseWeekFromText(raw, curWeek)
        val (secStart, _, _) = parseSectionsOrTimeFromText(subject)
        val room = parseRoomFromText(subject)

        var candName = ""
        val matchedInCourses = courses.firstOrNull { c ->
            subject.contains(c.name) || raw.contains(c.name) ||
            (c.name.length >= 2 && subject.contains(c.name.take(2)))
        }
        if (matchedInCourses != null) {
            candName = matchedInCourses.name
        } else {
            candName = subject
                .replace(Regex("^(?:周[一二三四五六日天七]|星期[一二三四五六日天七]|明天|后天|今天|下周[一二三四五六日天七]?|第[0-9一二两三四五六七八九十]+周|下午|上午|晚上|中午|[0-9]{1,2}点|[0-9]{1,2}节|第[0-9]{1,2}(?:-[0-9]{1,2})?节)+"), "")
                .replace(Regex("^(?:在|@|的|一门|一节|个|场|次|课)+"), "")
            if (room.isNotEmpty()) {
                candName = candName.replace(room, "")
            }
            candName = candName.replace(Regex("(?:课|课程|教室|地点)$"), "").trim()
        }

        val deleteAll = trimmed.contains("退课") || trimmed.contains("整门") || targetWeek == null ||
                        courses.any { it.name == candName && it.weekStart == it.weekEnd }

        val query = DeleteCourseQuery(
            name = candName,
            weekday = weekday,
            secStart = secStart,
            targetWeek = targetWeek,
            room = room,
            deleteAllWeeks = deleteAll
        )

        return deleteCourseMatching(query, context)
    }

    /**
     * 本地 NLP 解析自然语言修改与调整日程请求
     */
    fun parseModifyFromNaturalLanguage(text: String, context: Context): ModifyCourseResult? {
        val trimmed = text.trim()
        val modKeywords = listOf("改到", "改成", "改在", "改至", "推迟到", "推迟至", "提前到", "提前至", "调整到", "调整为", "换到", "换成")
        val kwFound = modKeywords.firstOrNull { trimmed.contains(it) } ?: return null

        ensureLoaded(context)
        var raw = trimmed
            .replaceFirst(Regex("^(?:阿米娅|请问|请|麻烦您|麻烦你|麻烦帮我|请帮我|麻烦|帮我|可以帮我|帮|给我)+[,，\\s]*"), "")

        val parts = raw.split(kwFound, limit = 2)
        if (parts.size < 2) return null

        var targetRaw = parts[0].trim().replaceFirst(Regex("^(?:把|将)\\s*"), "").trim()
        targetRaw = targetRaw.replace(Regex("(?:的时间|地点|教室)$"), "").trim()
        val newRaw = parts[1].trim()

        val curWeek = getWeekNo() ?: 1
        val targetWeekday = parseWeekdayFromText(targetRaw)
        val targetWeek = parseWeekFromText(targetRaw, curWeek)
        val (targetSec, _, _) = parseSectionsOrTimeFromText(targetRaw)

        var targetName = ""
        val matchedInCourses = courses.firstOrNull { c ->
            targetRaw.contains(c.name) || (c.name.length >= 2 && targetRaw.contains(c.name.take(2)))
        }
        if (matchedInCourses != null) {
            targetName = matchedInCourses.name
        } else {
            targetName = targetRaw
                .replace(Regex("^(?:周[一二三四五六日天七]|星期[一二三四五六日天七]|明天|后天|今天|下周[一二三四五六日天七]?|第[0-9一二两三四五六七八九十]+周|下午|上午|晚上|中午|[0-9]{1,2}点|[0-9]{1,2}节|第[0-9]{1,2}(?:-[0-9]{1,2})?节)+"), "")
                .replace(Regex("^(?:在|@|的|一门|一节|个|场|次|课)+"), "")
                .replace(Regex("(?:课|课程|教室|地点)$"), "").trim()
        }

        val newWeekday = parseWeekdayFromText(newRaw)
        val (newSecStart, newSecEnd, newCustomTime) = parseSectionsOrTimeFromText(newRaw)
        val newRoom = parseRoomFromText(newRaw)
        val newWeek = parseWeekFromText(newRaw, curWeek)

        var newName: String? = null
        if (kwFound in listOf("改成", "换成") && newRoom.isEmpty() && newSecStart == null && newWeekday == null) {
            newName = newRaw.replace(Regex("^(?:一门|一节|个|场|次)?"), "").replace(Regex("(?:课|课程)$"), "").trim()
        }

        val query = ModifyCourseQuery(
            targetName = targetName,
            targetWeekday = targetWeekday,
            targetSecStart = targetSec,
            targetWeek = targetWeek,
            newName = newName,
            newWeekday = newWeekday,
            newSecStart = newSecStart,
            newSecEnd = newSecEnd,
            newRoom = if (newRoom.isNotEmpty()) newRoom else null,
            newCustomTime = if (newCustomTime.isNotEmpty()) newCustomTime else null,
            newWeekStart = newWeek,
            newWeekEnd = newWeek
        )

        return modifyCourseMatching(query, context)
    }

    fun getWeekNo(date: Date = Date()): Int? {
        val start = termStart ?: return null
        val normStart = normalizeToSunday(start)
        val normTarget = normalizeToSunday(date)
        val diffMs = normTarget.time - normStart.time
        if (diffMs < 0) return 0
        val days = (diffMs / (24L * 3600 * 1000)).toInt()
        return (days / 7) + 1
    }

    fun setTermStartDate(date: Date, context: Context) {
        termStart = normalizeToSunday(date)
        coursesVersion++
        save(context)
    }

    fun getCoursesOn(weekday: Int, weekNo: Int? = null): List<Course> {
        return courses.filter { it.weekday == weekday && (weekNo == null || it.activeOn(weekNo)) }
            .sortedBy { it.secStart }
    }

    fun getIsoWeekday(date: Date = Date()): Int {
        val cal = Calendar.getInstance().apply { time = date }
        val dow = cal.get(Calendar.DAY_OF_WEEK) // SUNDAY=1, MONDAY=2, ... SATURDAY=7
        return if (dow == Calendar.SUNDAY) 7 else dow - 1
    }

    /**
     * 获取指定公历日期真实生效的课程列表（已深度融合假期调课/停课教学安排调整）。
     */
    fun getCoursesForDay(date: Date = Date()): List<Course> {
        val dateStr = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(date)
        val adj = adjustments.find { it.date == dateStr }
        if (adj != null) {
            if (adj.type == "suspend") {
                return emptyList()
            }
            if (adj.type == "substitute") {
                val targetWd = adj.targetWeekday ?: getIsoWeekday(date)
                val targetWk = adj.targetWeek ?: (getWeekNo(date) ?: 1)
                return getCoursesOn(targetWd, targetWk)
            }
        }
        val weekNo = getWeekNo(date) ?: 1
        val isoWd = getIsoWeekday(date)
        return getCoursesOn(isoWd, weekNo)
    }

    /**
     * 为课表周视图网格返回该格的课程与生效的调整规则（若有）。
     */
    fun getCoursesForGrid(date: Date, defaultWeekday: Int, defaultWeekNo: Int): Pair<List<Course>, ScheduleAdjustment?> {
        val dateStr = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(date)
        val adj = adjustments.find { it.date == dateStr }
        if (adj != null) {
            if (adj.type == "suspend") {
                return Pair(emptyList(), adj)
            }
            if (adj.type == "substitute") {
                val targetWd = adj.targetWeekday ?: defaultWeekday
                val targetWk = adj.targetWeek ?: defaultWeekNo
                return Pair(getCoursesOn(targetWd, targetWk), adj)
            }
        }
        return Pair(getCoursesOn(defaultWeekday, defaultWeekNo), null)
    }

    /**
     * 批量合并导入教学安排调整（覆盖同日期的旧调整）
     */
    fun addAdjustments(newAdjustments: List<ScheduleAdjustment>, context: Context) {
        ensureLoaded(context)
        val datesToAdd = newAdjustments.map { it.date }.toSet()
        adjustments = adjustments.filterNot { it.date in datesToAdd } + newAdjustments
        coursesVersion++
        save(context)
    }

    /**
     * 清空所有教学安排调整
     */
    fun clearAdjustments(context: Context) {
        ensureLoaded(context)
        adjustments = emptyList()
        coursesVersion++
        save(context)
    }

    /**
     * 从教务处通知文本中高精度提取调课/停课教学安排调整。
     */
    fun parseAdjustmentsFromNotice(text: String, baseYear: Int? = null): List<ScheduleAdjustment> {
        val yearPattern = Pattern.compile("(20\\d{2})年")
        val ym = yearPattern.matcher(text)
        val year = baseYear ?: if (ym.find()) ym.group(1)?.toIntOrNull() ?: Calendar.getInstance().get(Calendar.YEAR) else Calendar.getInstance().get(Calendar.YEAR)

        val cnNumMap = mapOf(
            "一" to 1, "二" to 2, "三" to 3, "四" to 4, "五" to 5, "六" to 6, "日" to 7, "天" to 7,
            "1" to 1, "2" to 2, "3" to 3, "4" to 4, "5" to 5, "6" to 6, "7" to 7
        )

        val result = mutableListOf<ScheduleAdjustment>()

        // 1. 调课换课: 9月20日（周日），教学安排按第5周周二课表执行
        val p1 = Pattern.compile("(\\d{1,2})月(\\d{1,2})日(?:[（(][^）)]*[）)])?[，, ]*(?:教学安排)?(?:均|都|各单位)?按(?:第(\\d+)周)?(?:的)?周([一二三四五六日天1-7])(?:课表)?执行")
        val m1 = p1.matcher(text)
        while (m1.find()) {
            val month = m1.group(1)?.toIntOrNull() ?: continue
            val day = m1.group(2)?.toIntOrNull() ?: continue
            val tw = m1.group(3)?.toIntOrNull()
            val wdStr = m1.group(4) ?: "1"
            val twd = cnNumMap[wdStr] ?: 1
            val dateStr = String.format(Locale.getDefault(), "%04d-%02d-%02d", year, month, day)
            val reason = if (tw != null) "按第${tw}周周$wdStr" else "按周$wdStr"
            result.add(ScheduleAdjustment(
                date = dateStr,
                type = "substitute",
                targetWeek = tw,
                targetWeekday = twd,
                reason = reason
            ))
        }

        // 2. 连续多天停课: 国庆节：10月1日-7日，所有课程停上
        val p2Range = Pattern.compile("(\\d{1,2})月(\\d{1,2})日\\s*[-~至到]\\s*(?:(\\d{1,2})月)?(\\d{1,2})日(?:[（(][^）)]*[）)])?[^。；;\\n]*?停[上课]")
        val m2 = p2Range.matcher(text)
        while (m2.find()) {
            val mStart = m2.group(1)?.toIntOrNull() ?: continue
            val dStart = m2.group(2)?.toIntOrNull() ?: continue
            val mEnd = m2.group(3)?.toIntOrNull() ?: mStart
            val dEnd = m2.group(4)?.toIntOrNull() ?: continue

            val matchFull = m2.group(0) ?: ""
            val holidayReason = when {
                matchFull.contains("中秋") || text.substring(0, m2.start()).takeLast(30).contains("中秋") -> "中秋节停课"
                matchFull.contains("国庆") || text.substring(0, m2.start()).takeLast(30).contains("国庆") -> "国庆节停课"
                matchFull.contains("元旦") || text.substring(0, m2.start()).takeLast(30).contains("元旦") -> "元旦停课"
                matchFull.contains("五一") || matchFull.contains("劳动") || text.substring(0, m2.start()).takeLast(30).contains("五一") -> "五一停课"
                matchFull.contains("端午") || text.substring(0, m2.start()).takeLast(30).contains("端午") -> "端午节停课"
                matchFull.contains("清明") || text.substring(0, m2.start()).takeLast(30).contains("清明") -> "清明节停课"
                else -> "停课"
            }

            val startCal = Calendar.getInstance().apply {
                set(year, mStart - 1, dStart, 0, 0, 0)
                set(Calendar.MILLISECOND, 0)
            }
            val endCal = Calendar.getInstance().apply {
                set(year, mEnd - 1, dEnd, 0, 0, 0)
                set(Calendar.MILLISECOND, 0)
            }
            while (!startCal.after(endCal)) {
                val dateStr = String.format(Locale.getDefault(), "%04d-%02d-%02d",
                    startCal.get(Calendar.YEAR),
                    startCal.get(Calendar.MONTH) + 1,
                    startCal.get(Calendar.DAY_OF_MONTH)
                )
                if (result.none { it.date == dateStr }) {
                    result.add(ScheduleAdjustment(
                        date = dateStr,
                        type = "suspend",
                        reason = holidayReason
                    ))
                }
                startCal.add(Calendar.DAY_OF_YEAR, 1)
            }
        }

        // 3. 单日停课: 9月25日，所有课程停上
        val p3Single = Pattern.compile("(\\d{1,2})月(\\d{1,2})日(?:[（(][^）)]*[）)])?(?!\\s*[-~至到])[^。；;\\n]*?停[上课]")
        val m3 = p3Single.matcher(text)
        while (m3.find()) {
            val month = m3.group(1)?.toIntOrNull() ?: continue
            val day = m3.group(2)?.toIntOrNull() ?: continue
            val dateStr = String.format(Locale.getDefault(), "%04d-%02d-%02d", year, month, day)

            val matchFull = m3.group(0) ?: ""
            val holidayReason = when {
                matchFull.contains("中秋") || text.substring(0, m3.start()).takeLast(30).contains("中秋") -> "中秋节停课"
                matchFull.contains("国庆") || text.substring(0, m3.start()).takeLast(30).contains("国庆") -> "国庆节停课"
                matchFull.contains("元旦") || text.substring(0, m3.start()).takeLast(30).contains("元旦") -> "元旦停课"
                matchFull.contains("五一") || matchFull.contains("劳动") || text.substring(0, m3.start()).takeLast(30).contains("五一") -> "五一停课"
                matchFull.contains("端午") || text.substring(0, m3.start()).takeLast(30).contains("端午") -> "端午节停课"
                matchFull.contains("清明") || text.substring(0, m3.start()).takeLast(30).contains("清明") -> "清明节停课"
                else -> "停课"
            }

            if (result.none { it.date == dateStr }) {
                result.add(ScheduleAdjustment(
                    date = dateStr,
                    type = "suspend",
                    reason = holidayReason
                ))
            }
        }

        return result.sortedBy { it.date }
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
                val parsed = format.parse(termStartDateStr)
                termStart = parsed?.let { normalizeToSunday(it) }
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

        for (offset in 0..7) {
            val targetCal = Calendar.getInstance()
            targetCal.time = now
            targetCal.add(Calendar.DAY_OF_YEAR, offset)

            val targetDate = targetCal.time
            val dayCourses = getCoursesForDay(targetDate)
            val dayIsoWd = getIsoWeekday(targetDate)
            val dayWeekNo = getWeekNo(targetDate) ?: weekNo

            for (c in dayCourses) {
                val hm = c.startTime(dayWeekNo, sections) ?: continue

                val classCal = Calendar.getInstance().apply {
                    time = targetDate
                    set(Calendar.HOUR_OF_DAY, hm.first)
                    set(Calendar.MINUTE, hm.second)
                    set(Calendar.SECOND, 0)
                    set(Calendar.MILLISECOND, 0)
                }

                if (classCal.time.time > now.time) {
                    return CourseInfo(c, dayIsoWd, dayWeekNo, classCal.time)
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

        // 3. 今日课程与下一门课（感知调课与停课）
        val todayCourses = getCoursesForDay(now)
        if (todayCourses.isNotEmpty()) {
            val todayStr = todayCourses.joinToString("；") { c ->
                val time = sections[c.secStart.toString()] ?: ""
                val timeStr = if (time.isNotEmpty()) "($time)" else ""
                "${c.secStart}-${c.secEnd}节$timeStr《${c.name}》@${c.room.ifEmpty { "待定" }}"
            }
            sb.append("- 今日（${weekdayNames.getOrElse(todayWeekday) { "" }}）课程安排：$todayStr\n")
        } else {
            val todayAdj = adjustments.find { it.date == SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(now) }
            if (todayAdj?.type == "suspend") {
                sb.append("- 今日（${weekdayNames.getOrElse(todayWeekday) { "" }}）课程安排：今日因【${todayAdj.reason.ifEmpty { "法定节假日" }}】停课放假，无排课。\n")
            } else {
                sb.append("- 今日（${weekdayNames.getOrElse(todayWeekday) { "" }}）课程安排：今天没有排课，可自由安排学习或休息。\n")
            }
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

        // 5. 教学安排与调课/停课备忘
        if (adjustments.isNotEmpty()) {
            sb.append("\n【教学安排与调课/停课备忘（已生效）】：\n")
            for (a in adjustments.sortedBy { it.date }) {
                val desc = if (a.type == "suspend") "停课放假" else "调课（按第${a.targetWeek ?: ""}周周${a.targetWeekday ?: ""}课表）"
                val reasonStr = if (a.reason.isNotEmpty()) "【${a.reason}】" else ""
                sb.append("- ${a.date}$reasonStr：$desc\n")
            }
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

