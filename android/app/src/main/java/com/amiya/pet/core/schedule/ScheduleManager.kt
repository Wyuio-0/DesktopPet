package com.amiya.pet.core.schedule

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.*
import java.util.regex.Pattern

object ScheduleManager {

    private val defaultSections = mapOf(
        "1" to "08:00", "2" to "08:50", "3" to "09:50", "4" to "10:40", "5" to "11:30",
        "6" to "14:05", "7" to "14:55", "8" to "15:45", "9" to "16:35",
        "10" to "18:30", "11" to "19:20", "12" to "20:10", "13" to "21:00"
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
                val map = mutableMapOf<String, String>()
                for (key in secObj.keys()) {
                    map[key] = secObj.getString(key)
                }
                if (map.isNotEmpty()) {
                    sections = map
                }
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
}

data class CourseInfo(
    val course: Course,
    val weekday: Int,
    val weekNo: Int,
    val startTime: Date
)

