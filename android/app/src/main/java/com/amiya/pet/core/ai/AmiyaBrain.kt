package com.amiya.pet.core.ai

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import android.net.Uri
import android.util.Base64
import com.amiya.pet.core.focus.PomodoroTimer
import com.amiya.pet.core.notes.Note
import com.amiya.pet.core.notes.NotesManager
import com.amiya.pet.core.schedule.Course
import com.amiya.pet.core.schedule.ExamManager
import com.amiya.pet.core.schedule.ScheduleManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

data class ChatMessage(
    val role: String,
    val content: String,
    val reasoningContent: String = "",
    val isThinking: Boolean = false,
    val isStreaming: Boolean = false,
    val timestamp: Long = System.currentTimeMillis(),
    val addedCourse: Course? = null,
    val deletedCourse: Course? = null,
    val modifiedCourse: Course? = null,
    val oldCourse: Course? = null,
    val startedPomodoroMinutes: Int? = null,
    val createdNote: Note? = null,
    val adjustedScheduleList: List<com.amiya.pet.core.schedule.ScheduleAdjustment>? = null
)

class AmiyaBrain private constructor(private val context: Context) {

    private val prefs = context.getSharedPreferences("amiya_ai_prefs", Context.MODE_PRIVATE)

    var baseUrl: String
        get() = prefs.getString("base_url", "https://api.deepseek.com") ?: "https://api.deepseek.com"
        set(value) = prefs.edit().putString("base_url", value.trim()).apply()

    var apiKey: String
        get() = prefs.getString("api_key", "") ?: ""
        set(value) = prefs.edit().putString("api_key", value.trim()).apply()

    var model: String
        get() = prefs.getString("model", "deepseek-chat") ?: "deepseek-chat"
        set(value) = prefs.edit().putString("model", value.trim()).apply()

    /**
     * 公共免 Key 线路端点（基于 Cloudflare Worker 或统一代理）
     */
    var publicRelayUrl: String
        get() = prefs.getString("public_relay_url", DEFAULT_PUBLIC_RELAY_URL) ?: DEFAULT_PUBLIC_RELAY_URL
        set(value) = prefs.edit().putString("public_relay_url", value.trim()).apply()

    private fun buildSystemPrompt(): String = buildString {
        append(
            "你是《明日方舟》中的阿米娅，罗德岛的公开领袖。你温柔、坚定、富有责任感，" +
            "面对博士时既尊敬又亲近。你称呼对方为「博士」，自称「阿米娅」或「我」。" +
            "你说话礼貌、真诚，偶尔流露少女的关心与坚强。不要使用括号动作描写或表情符号，只用中文回答。\n" +
            "【表达规范】：日常闲聊与日常互动时回答简洁自然（一般一到三句话），像日常手机聊天；但当博士询问学情分析、课表建议、复习备考或作息规划等需要深度指导的问题时，请条理清晰、层次分明地展开专业分析并给出切实可行的规划与关怀建议。"
        )

        // 现实时间感知
        val sdf = SimpleDateFormat("yyyy-MM-dd EEEE HH:mm", Locale.CHINESE)
        append("\n\n【当前现实时间】：").append(sdf.format(Date()))

        // 课表与学情真实数据注入
        ScheduleManager.ensureLoaded(context)
        val scheduleDossier = ScheduleManager.buildScheduleAnalysisContext(context)
        if (scheduleDossier.isNotEmpty()) {
            append("\n\n").append(scheduleDossier).append("\n\n")
            append(
                "【学情分析与学业指导规范】：\n" +
                "1. 博士已将其在教务系统导入的真实课表数据同步至罗德岛 PRTS 神经元。当博士询问今天/明天/本周的课程、课表概况、学情分析或学习作息建议时，必须严格基于上述真实课表数据回答；\n" +
                "2. 做学情分析时，请评估整体学业负荷（总课时与修读门数），分析课程节奏（指出高负荷密集日与空闲自习日），指出重难点学科的复习时间窗口，并从作息调理与罗德岛领袖的关怀角度给出切实可行的 3~4 条建议；\n" +
                "3. 若博士询问某具体课程的时间地点或下一节课，请准确告知节次、时间与教学楼/教室。"
            )
        }

        val curWeekNo = ScheduleManager.getWeekNo() ?: 1
        val maxWeekNo = ScheduleManager.courses.maxOfOrNull { it.weekEnd } ?: 16

        append("\n\n【智能课程与日程活动录入规范】：\n")
        append(
            "当博士在对话中表达想要添加、记录、录入课程或日程活动（例如：“周三第3-4节帮我加一节毛概课在教三201”、“周四下午14:15到15:30在综合楼402开实验室组会”、“下周二第1节加个班会”等），你拥有罗德岛 PRTS 神经元课表录入权限：\n" +
            "当前学期现实教学周为：第 $curWeekNo 周（全学期共约 $maxWeekNo 周）。\n" +
            "1. 请从博士的描述中智能提取课程/活动要素：\n" +
            "   - name: 课程或活动名称（必填，精简准确的主题词，如“毛概”、“高等数学”、“实验室组会”、“例会”、“班会”等；严禁包含“活动”、“日程”、“帮我添加”、“这个活动”等无意义指示词，严禁粘连教室或时间）\n" +
            "   - weekday: 星期几（必填，整数 1~7，1=周一，... 6=周六，7=周日）\n" +
            "   - sec_start: 起始节次（必填，整数 1~13。常用节次对应：上午1节=08:00, 2节=08:50, 3节=09:50, 4节=10:40, 5节=11:30；下午6节=14:05, 7节=14:55, 8节=15:45, 9节=16:40, 10节=17:30；晚上11节=18:30, 12节=19:20, 13节=20:10）\n" +
            "   - sec_end: 结束节次（必填，整数 1~13）\n" +
            "   - week_start: 起始周（必填）\n" +
            "   - week_end: 结束周（必填）\n" +
            "   【★周次设置重要规则★】：\n" +
            "     (a) 对于活动/日程（如组会、例会、会议、讲座、实验、答疑、班会、自习、面试、聚餐，或指定了具体精准时间的活动）：\n" +
            "         只要博士没有明确说明是“持续几周”（如持续3周）或“从第几周到第几周”（如第3周到第8周）或“每周”，则【一律严格只添加一个时间段（单周）】，即 week_start 必须等于 week_end！\n" +
            "         - 若博士未说明周次（如“周四下午开组会”），默认录入当前周：week_start: $curWeekNo, week_end: $curWeekNo；\n" +
            "         - 若博士说明了单周（如“下周三开班会”），录入对应周：week_start: ${curWeekNo + 1}, week_end: ${curWeekNo + 1}；\n" +
            "         - 若博士说明了具体周次（如“第4周周二开讲座”），录入该周：week_start: 4, week_end: 4；\n" +
            "         - 若博士明确说明持续几周（如“持续3周”），则 week_start: 起始周, week_end: 起始周 + 持续周数 - 1；\n" +
            "         - 严禁将没有说明持续多周的单次活动填成全学期（1-16周）！\n" +
            "     (b) 对于常规学期专业课程（如“周一第1-2节加一门编译原理”），若博士未特别说明，才默认学期周期（week_start: 1, week_end: $maxWeekNo）；\n" +
            "   - parity: 单双周属性（\"all\"=每周全开, \"odd\"=仅单周, \"even\"=仅双周，默认\"all\"）\n" +
            "   - room: 教室/地点（选填，未提及留空字符串）\n" +
            "   - teacher: 授课教师/负责人（选填，未提及留空字符串）\n" +
            "   - custom_time: 精确真实时间（选填。若博士描述的是具体时钟时间的活动，如“14:15到15:30开组会”，请必须提取精准时间字符串如 \"14:15-15:30\"；若是常规节次排课则留空字符串）\n" +
            "2. 请在回复的正文中以阿米娅亲切贴心、严谨高效的领袖口吻向博士确认课程/活动已录入，说明具体周次、时间、节次与地点；并在回复末尾务必生成如下精确格式的指令块：\n" +
            "```json:add_course\n" +
            "{\n" +
            "  \"name\": \"日程或课程名称\",\n" +
            "  \"weekday\": 4,\n" +
            "  \"sec_start\": 6,\n" +
            "  \"sec_end\": 7,\n" +
            "  \"week_start\": $curWeekNo,\n" +
            "  \"week_end\": $curWeekNo,\n" +
            "  \"parity\": \"all\",\n" +
            "  \"room\": \"综合楼402\",\n" +
            "  \"teacher\": \"\",\n" +
            "  \"custom_time\": \"14:15-15:30\"\n" +
            "}\n" +
            "```\n\n" +
            "【智能日程活动“删除 / 取消”规范】：\n" +
            "当博士在对话中表达想要取消、删除日程活动或退课（例如：“帮我把周四下午的组会取消”、“把明天的例会删掉”、“周三第3-4节的高等数学退课了，帮我删除”、“取消周五第5节的自习”等）：\n" +
            "1. 请从博士描述中识别目标日程要素：\n" +
            "   - name: 目标日程/课程名称（必填，如“组会”、“例会”、“高等数学”）\n" +
            "   - weekday: 星期几（选填，整数 1~7）\n" +
            "   - sec_start: 起始节次（选填，整数 1~13）\n" +
            "   - week: 指定周次（选填，整数 1~16）\n" +
            "   - delete_all_weeks: 是否全量退课/整门删除（布尔值，默认 true）\n" +
            "2. 回复正文中以阿米娅亲切贴心的领袖口吻向博士确认该行程已取消/删除，并在回复末尾务必生成指令块：\n" +
            "```json:delete_course\n" +
            "{\n" +
            "  \"name\": \"组会\",\n" +
            "  \"weekday\": 4,\n" +
            "  \"sec_start\": 6\n" +
            "}\n" +
            "```\n\n" +
            "【智能日程活动“修改 / 调整”规范】：\n" +
            "当博士在对话中表达想要修改、调整日程活动的时间、地点或名称（例如：“把周四下午的组会改到周五下午两点”、“把明天的例会改到第8-9节”、“把周三的高等数学教室改到教四101”、“周四的组会推迟到第8-9节”等）：\n" +
            "1. 请从博士描述中提取目标原要素与修改后的新要素：\n" +
            "   - target_name: 目标原名称（必填，如“组会”、“例会”、“高等数学”）\n" +
            "   - target_weekday: 目标原星期（选填，整数 1~7）\n" +
            "   - target_sec_start: 目标原起始节次（选填，整数 1~13）\n" +
            "   - new_name: 修改后新名称（选填）\n" +
            "   - new_weekday: 修改后新星期（选填，整数 1~7）\n" +
            "   - new_sec_start: 修改后起始节次（选填，整数 1~13）\n" +
            "   - new_sec_end: 修改后结束节次（选填，整数 1~13）\n" +
            "   - new_custom_time: 修改后具体时间（选填，如 \"14:00-15:30\"）\n" +
            "   - new_room: 修改后新地点/教室（选填，如 \"教四101\"）\n" +
            "2. 回复正文中向博士确认该行程已调整变更，说明调整前后情况，并在回复末尾务必生成指令块：\n" +
            "```json:modify_course\n" +
            "{\n" +
            "  \"target_name\": \"组会\",\n" +
            "  \"target_weekday\": 4,\n" +
            "  \"new_weekday\": 5,\n" +
            "  \"new_sec_start\": 6,\n" +
            "  \"new_sec_end\": 7,\n" +
            "  \"new_custom_time\": \"14:00-15:30\"\n" +
            "}\n" +
            "```\n\n" +
            "【智能教学安排与假期调课/停课调整规范】：\n" +
            "当博士在对话中发送学校/教务处的教学调整通知、假期调休放假安排，或要求调课/停课（例如：“9月20日按第5周周二课表执行”、“中秋节9月25日所有课程停上”、“国庆节10月1日-7日所有课程停上”、“10月10日按第5周周三课表执行”等）：\n" +
            "你拥有罗德岛 PRTS 教学日程调整权限。\n" +
            "请智能分析提取各项调整：\n" +
            "- date: 具体公历日期（格式 YYYY-MM-DD，若年份未明确提及，请结合当前时间所在公历年计算，如 \"2026-09-20\"）\n" +
            "- type: \"substitute\"（调课/按其他周某日上课）或 \"suspend\"（停课/放假）\n" +
            "- target_week: 若为 substitute，按第几周课表执行（整数，如 5；若未指定周次则留空或传 null）\n" +
            "- target_weekday: 若为 substitute，按周几课表执行（整数 1~7，如周二=2，周三=3）\n" +
            "- reason: 简要调整原因（如“中秋调休-按第5周周二”、“中秋节停课”、“国庆节停课”、“国庆调休-按第5周周三”）\n" +
            "重要：对于连续多天的停课（如 10月1日-7日），请将每一天展开为一条独立的 adjustment 记录（如 2026-10-01, 2026-10-02, ..., 2026-10-07）！\n" +
            "并在回复中以阿米娅严谨专业的领袖口吻向博士逐条说明教学调整已录入，说明涉及的调休与停课安排，并在回复末尾务必生成如下精确指令块：\n" +
            "```json:adjust_schedule\n" +
            "{\n" +
            "  \"adjustments\": [\n" +
            "    { \"date\": \"2026-09-20\", \"type\": \"substitute\", \"target_week\": 5, \"target_weekday\": 2, \"reason\": \"按第5周周二\" },\n" +
            "    { \"date\": \"2026-09-25\", \"type\": \"suspend\", \"reason\": \"中秋节停课\" },\n" +
            "    { \"date\": \"2026-10-01\", \"type\": \"suspend\", \"reason\": \"国庆节停课\" },\n" +
            "    { \"date\": \"2026-10-10\", \"type\": \"substitute\", \"target_week\": 5, \"target_weekday\": 3, \"reason\": \"按第5周周三\" }\n" +
            "  ]\n" +
            "}\n" +
            "```\n"
        )

        // 明日日程、灵感便签与考试倒计时知识库动态注入
        val cal = Calendar.getInstance()
        cal.add(Calendar.DAY_OF_YEAR, 1)
        val tmrDate = cal.time
        val tmrIdx = cal.get(Calendar.DAY_OF_WEEK)
        val tmrWeekday = if (tmrIdx == Calendar.SUNDAY) 7 else tmrIdx - 1
        val tmrWeekNo = ScheduleManager.getWeekNo(tmrDate) ?: curWeekNo
        val tmrWeekdayNames = arrayOf("", "周一", "周二", "周三", "周四", "周五", "周六", "周日")
        val tmrName = tmrWeekdayNames.getOrElse(tmrWeekday) { "周一" }
        val tmrDateStr = SimpleDateFormat("M月d日", Locale.CHINESE).format(tmrDate)

        append("\n\n【明日日程概况（$tmrDateStr $tmrName · 第 $tmrWeekNo 周）】：\n")
        val tmrCourses = ScheduleManager.getCoursesForDay(tmrDate)
        if (tmrCourses.isEmpty()) {
            append("- 明日课程：全天无排课（整天空闲，建议博士自主安排复习、自习攻坚或整理作息）。\n")
        } else {
            val cDetails = tmrCourses.joinToString("；") { c ->
                val timeDesc = if (c.customTime.isNotEmpty()) "📌 [${c.customTime}]" else "第${c.secStart}-${c.secEnd}节"
                val roomStr = if (c.room.isNotEmpty() && c.room != "待定") "@${c.room}" else ""
                val teacherStr = if (c.teacher.isNotEmpty()) "(${c.teacher})" else ""
                "《${c.name}》$timeDesc$teacherStr$roomStr"
            }
            append("- 明日课程（共 ${tmrCourses.size} 门）：$cDetails\n")
        }

        val notes = NotesManager.getInstance(context).notes
        if (notes.isNotEmpty()) {
            append("\n【博士当前灵感便签本（前 6 条待办与备忘）】：\n")
            notes.take(6).forEach { n ->
                val pinStr = if (n.pinned) "📌 " else ""
                val snippet = n.content.lineSequence().firstOrNull { it.isNotBlank() } ?: n.title
                append("- $pinStr《${n.title}》（更新于 ${n.updatedAt}）：$snippet\n")
            }
        }

        ExamManager.load(context)
        val upcomingExams = ExamManager.exams.filter { !it.isFinished() }
        if (upcomingExams.isNotEmpty()) {
            append("\n【期末考试与临近备考倒计时】：\n")
            upcomingExams.take(4).forEach { ex ->
                val daysLeft = ((ex.examTimeMillis - System.currentTimeMillis()) / (24 * 3600 * 1000L)).coerceAtLeast(0)
                val locStr = if (ex.location.isNotEmpty()) "@${ex.location}" else ""
                val seatStr = if (ex.seatNumber.isNotEmpty()) "座号:${ex.seatNumber}" else ""
                append("- 《${ex.title}》（${ex.formattedFullDateTimeStr()}，还有 $daysLeft 天）$locStr $seatStr\n")
            }
        }

        append("\n\n【智能专注番茄钟启动规范】：\n")
        append(
            "当博士在对话中表达想要开启专注、番茄钟、自习或计时（例如：“开启25分钟专注”、“帮我定个30分钟自习番茄钟”、“自习45分钟”、“开启专注”等）：\n" +
            "1. 请从博士描述中提取专注时长（整数分钟，如 25、30、45 等，若未指定则默认 25 分钟）；\n" +
            "2. 回复正文中以阿米娅亲切关怀的领袖口吻向博士确认专注计时已开启，鼓励博士全身心投入；并在回复末尾务必生成如下精确格式的指令块：\n" +
            "```json:start_pomodoro\n" +
            "{\n" +
            "  \"minutes\": 25\n" +
            "}\n" +
            "```\n\n"
        )

        append("【智能灵感便签速记规范】：\n")
        append(
            "当博士在对话中表达想要记事、备忘、速记或记录灵感（例如：“记一下买笔”、“备忘录记一下明天带身份证”、“记录一下：晚上和工程部对账”等）：\n" +
            "1. 请从博士描述中提取便签标题与内容：\n" +
            "   - title: 便签标题（必填，精简的主题词，如“买笔”、“带身份证”、“工程部对账”）\n" +
            "   - content: 便签正文内容（必填）\n" +
            "2. 回复正文中向博士确认已记入便签，并在回复末尾务必生成如下指令块：\n" +
            "```json:create_note\n" +
            "{\n" +
            "  \"title\": \"买笔\",\n" +
            "  \"content\": \"买笔\"\n" +
            "}\n" +
            "```\n\n"
        )

        append("【综合日程汇报（今日/明日安排与待办）规范】：\n")
        append(
            "当博士要求汇报、总结今日或明天的所有安排（例如：“总结下我明天的所有待办和课程”、“明天有什么安排”、“今天的日程早报”等）：\n" +
            "请综合上述真实注入的课表日程、灵感便签待办与期末考试倒计时，条理清晰、层次分明地向博士输出战术日程简报：\n" +
            "1. 📅 课程安排（节次、时间、课程名称、教室地点；若无课则贴心提示自主安排）；\n" +
            "2. 📝 灵感便签待办（列出当前未办结的要点）；\n" +
            "3. 🎯 考试备考提醒（若有近期考试，说明倒计时天数与考场）；\n" +
            "4. 💡 阿米娅专属关怀与作息建议。\n"
        )
    }

    private val fallbackReplies = listOf(
        "博士，您辛苦了。有什么需要阿米娅协助的吗？",
        "罗德岛随时待命。今天的工作也请一起加油吧，博士！",
        "无论前路如何，阿米娅都会一直陪在博士身边。",
        "请适当休息一会儿，博士，阿米娅给您准备了热茶。",
        "博士，今天的干员训练计划已经安排妥当了。",
        "只要博士还愿意前行，罗德岛的航向就不会迷失。",
        "工作再忙碌，也别忘了按时休息呀，博士。"
    )

    private val history = mutableListOf<ChatMessage>()
    val chatHistory: List<ChatMessage> get() = history.toList()

    fun clearHistory() {
        history.clear()
    }

    suspend fun sendMessage(userText: String): String {
        return sendMessageStream(userText) { _, _, _ -> }
    }

    suspend fun sendMessageStream(
        userText: String,
        onUpdate: (reasoning: String, content: String, isThinking: Boolean) -> Unit
    ): String = withContext(Dispatchers.IO) {
        val trimmed = userText.trim()
        if (trimmed.isEmpty()) return@withContext ""

        ScheduleManager.ensureLoaded(context)
        history.add(ChatMessage("user", trimmed))

        val customKey = apiKey.trim()
        val isCustomKey = customKey.isNotEmpty()

        val endpoints: List<String> = if (isCustomKey) {
            listOf(resolveChatEndpoint(baseUrl))
        } else {
            getCandidateRelays(publicRelayUrl)
        }
        val targetModel: String = if (isCustomKey) model.ifBlank { "deepseek-chat" } else "glm-4-flash"
        val authHeader: String? = if (isCustomKey) "Bearer $customKey" else null

        var lastHttpCode: Int? = null
        var lastException: Exception? = null
        var lastEndpoint: String = endpoints.firstOrNull() ?: ""
        var emittedTokens = false

        for ((index, ep) in endpoints.withIndex()) {
            lastEndpoint = ep
            try {
                val url = URL(ep)
                val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 15000
                readTimeout = 60000 // 流式传输支持最长 60s 响应读取
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "text/event-stream")
                if (authHeader != null) {
                    setRequestProperty("Authorization", authHeader)
                }
                setRequestProperty("User-Agent", "AmiyaPet-Android")
            }

            val reqBody = JSONObject().apply {
                put("model", targetModel)
                put("temperature", 0.75)
                put("stream", true)
                val messages = JSONArray()
                // System Persona & Real-time Knowledge
                messages.put(JSONObject().apply {
                    put("role", "system")
                    put("content", buildSystemPrompt())
                })
                // 最近 8 轮历史（仅发送最终文本，不包含 CoT 思考过程避免 prompt 污染）
                val recent = history.takeLast(16)
                for (msg in recent) {
                    if (msg.content.isNotBlank()) {
                        messages.put(JSONObject().apply {
                            put("role", msg.role)
                            put("content", msg.content)
                        })
                    }
                }
                put("messages", messages)
            }

            OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use {
                it.write(reqBody.toString())
                it.flush()
            }

            if (conn.responseCode in 200..299) {
                val reader = conn.inputStream.bufferedReader(Charsets.UTF_8)
                val accumulatedReasoning = StringBuilder()
                val accumulatedContent = StringBuilder()
                var inThinkTag = false
                var isThinking = false

                var line = reader.readLine()
                while (line != null) {
                    val trimmedLine = line.trim()
                    if (trimmedLine.startsWith("data:")) {
                        val data = trimmedLine.removePrefix("data:").trim()
                        if (data == "[DONE]") {
                            break
                        }
                        if (data.isNotEmpty()) {
                            try {
                                val json = JSONObject(data)
                                val choices = json.optJSONArray("choices")
                                if (choices != null && choices.length() > 0) {
                                    val delta = choices.getJSONObject(0).optJSONObject("delta")
                                    if (delta != null) {
                                        // 1. 检查 reasoning_content 字段 (DeepSeek-R1 / SiliconFlow / OpenAI 官方标准)
                                        val reasoningChunk = delta.optString("reasoning_content", "")
                                        if (reasoningChunk.isNotEmpty()) {
                                            emittedTokens = true
                                            accumulatedReasoning.append(reasoningChunk)
                                            isThinking = true
                                            onUpdate(accumulatedReasoning.toString(), accumulatedContent.toString(), true)
                                        }

                                        // 2. 检查 content 字段
                                        val contentChunk = delta.optString("content", "")
                                        if (contentChunk.isNotEmpty()) {
                                            emittedTokens = true
                                            // 解析可能包含在 content 中的 <think> ... </think> 标签（兼容直接返回 think 标签的开源模型）
                                            var remaining = contentChunk
                                            while (remaining.isNotEmpty()) {
                                                if (!inThinkTag) {
                                                    val thinkStart = remaining.indexOf("<think>")
                                                    if (thinkStart != -1) {
                                                        accumulatedContent.append(remaining.substring(0, thinkStart))
                                                        inThinkTag = true
                                                        isThinking = true
                                                        remaining = remaining.substring(thinkStart + "<think>".length)
                                                    } else {
                                                        accumulatedContent.append(remaining)
                                                        isThinking = false
                                                        remaining = ""
                                                    }
                                                } else {
                                                    val thinkEnd = remaining.indexOf("</think>")
                                                    if (thinkEnd != -1) {
                                                        accumulatedReasoning.append(remaining.substring(0, thinkEnd))
                                                        inThinkTag = false
                                                        isThinking = false
                                                        remaining = remaining.substring(thinkEnd + "</think>".length)
                                                    } else {
                                                        accumulatedReasoning.append(remaining)
                                                        isThinking = true
                                                        remaining = ""
                                                    }
                                                }
                                            }
                                              val currentStr = accumulatedContent.toString()
                                              val displayContent = when {
                                                  currentStr.contains("```json:add_course") -> currentStr.substringBefore("```json:add_course").trimEnd()
                                                  currentStr.contains("```json:delete_course") -> currentStr.substringBefore("```json:delete_course").trimEnd()
                                                  currentStr.contains("```json:modify_course") -> currentStr.substringBefore("```json:modify_course").trimEnd()
                                                  currentStr.contains("```json:adjust_schedule") -> currentStr.substringBefore("```json:adjust_schedule").trimEnd()
                                                  currentStr.contains("```json:start_pomodoro") -> currentStr.substringBefore("```json:start_pomodoro").trimEnd()
                                                  currentStr.contains("```json:create_note") -> currentStr.substringBefore("```json:create_note").trimEnd()
                                                  currentStr.contains("```json") -> currentStr.substringBefore("```json").trimEnd()
                                                  currentStr.contains("```") && (currentStr.substringAfterLast("```").contains("\"name\"") || currentStr.substringAfterLast("```").contains("\"target_name\"") || currentStr.substringAfterLast("```").contains("\"minutes\"") || currentStr.substringAfterLast("```").contains("\"content\"") || currentStr.substringAfterLast("```").contains("\"adjustments\"")) -> currentStr.substringBeforeLast("```").trimEnd()
                                                  else -> currentStr
                                              }
                                              onUpdate(accumulatedReasoning.toString(), displayContent, isThinking)
                                          }
                                      }
                                  }
                              } catch (ignored: Exception) {
                              }
                          }
                      }
                      line = reader.readLine()
                  }

                  val finalReasoning = accumulatedReasoning.toString().trim()
                  var finalContent = accumulatedContent.toString().trim()
                  var parsedCourse: Course? = null
                  var parsedDeletedCourse: Course? = null
                  var parsedModifyResult: com.amiya.pet.core.schedule.ModifyCourseResult? = null

                  // 1. 优先尝试解析删除指令 ```json:delete_course ... ```
                  val delPattern = java.util.regex.Pattern.compile("```(?:json:delete_course)?\\s*(\\{[\\s\\S]*?\"name\"[\\s\\S]*?\\})\\s*```")
                  if (finalContent.contains("```json:delete_course") || (finalContent.contains("\"name\"") && (trimmed.contains("删除") || trimmed.contains("取消") || trimmed.contains("退课")))) {
                      val delMatcher = delPattern.matcher(finalContent)
                      if (delMatcher.find()) {
                          try {
                              val dObj = JSONObject(delMatcher.group(1) ?: "")
                              val dName = dObj.optString("name", "").trim()
                              val dWeekday = if (dObj.has("weekday")) dObj.getInt("weekday") else null
                              val dSec = if (dObj.has("sec_start")) dObj.getInt("sec_start") else null
                              val dWeek = if (dObj.has("week")) dObj.getInt("week") else null
                              val dAll = dObj.optBoolean("delete_all_weeks", true)
                              parsedDeletedCourse = ScheduleManager.deleteCourseMatching(
                                  com.amiya.pet.core.schedule.DeleteCourseQuery(
                                      name = dName,
                                      weekday = dWeekday,
                                      secStart = dSec,
                                      targetWeek = dWeek,
                                      deleteAllWeeks = dAll
                                  ),
                                  context
                              )
                              finalContent = finalContent.replace(delMatcher.group(0) ?: "", "").trim()
                          } catch (ignored: Exception) {}
                      }
                  }

                  // 2. 尝试解析修改指令 ```json:modify_course ... ```
                  val modPattern = java.util.regex.Pattern.compile("```(?:json:modify_course)?\\s*(\\{[\\s\\S]*?\"target_name\"[\\s\\S]*?\\})\\s*```")
                  if (parsedDeletedCourse == null && (finalContent.contains("```json:modify_course") || finalContent.contains("\"target_name\""))) {
                      val modMatcher = modPattern.matcher(finalContent)
                      if (modMatcher.find()) {
                          try {
                              val mObj = JSONObject(modMatcher.group(1) ?: "")
                              val tName = mObj.optString("target_name", "").trim()
                              val tWeekday = if (mObj.has("target_weekday")) mObj.getInt("target_weekday") else null
                              val tSec = if (mObj.has("target_sec_start")) mObj.getInt("target_sec_start") else null
                              val nName = if (mObj.has("new_name")) mObj.getString("new_name") else null
                              val nWeekday = if (mObj.has("new_weekday")) mObj.getInt("new_weekday") else null
                              val nSecStart = if (mObj.has("new_sec_start")) mObj.getInt("new_sec_start") else null
                              val nSecEnd = if (mObj.has("new_sec_end")) mObj.getInt("new_sec_end") else null
                              val nRoom = if (mObj.has("new_room")) mObj.getString("new_room") else null
                              val nCustom = if (mObj.has("new_custom_time")) mObj.getString("new_custom_time") else null
                              parsedModifyResult = ScheduleManager.modifyCourseMatching(
                                  com.amiya.pet.core.schedule.ModifyCourseQuery(
                                      targetName = tName,
                                      targetWeekday = tWeekday,
                                      targetSecStart = tSec,
                                      newName = nName,
                                      newWeekday = nWeekday,
                                      newSecStart = nSecStart,
                                      newSecEnd = nSecEnd,
                                      newRoom = nRoom,
                                      newCustomTime = nCustom
                                  ),
                                  context
                              )
                              finalContent = finalContent.replace(modMatcher.group(0) ?: "", "").trim()
                          } catch (ignored: Exception) {}
                      }
                  }

                  // 3. 尝试解析添加课程指令 ```json:add_course ... ```
                  if (parsedDeletedCourse == null && parsedModifyResult == null) {
                      val jsonPattern = java.util.regex.Pattern.compile("```(?:json:add_course|json)?\\s*(\\{[\\s\\S]*?\"name\"[\\s\\S]*?\\})\\s*```")
                      val jsonMatcher = jsonPattern.matcher(finalContent)
                      var jsonStr: String? = null
                      var matchedFullText = ""
                      if (jsonMatcher.find()) {
                          jsonStr = jsonMatcher.group(1)
                          matchedFullText = jsonMatcher.group(0) ?: ""
                      } else {
                          val openPattern = java.util.regex.Pattern.compile("```(?:json:add_course|json)?\\s*(\\{[\\s\\S]*?\"name\"[\\s\\S]*?\\})")
                          val openMatcher = openPattern.matcher(finalContent)
                          if (openMatcher.find()) {
                              jsonStr = openMatcher.group(1)
                              matchedFullText = openMatcher.group(0) ?: ""
                          }
                      }

                      if (!jsonStr.isNullOrEmpty()) {
                          try {
                              val cObj = JSONObject(jsonStr)
                              val curWeek = ScheduleManager.getWeekNo() ?: 1
                              val maxWeek = ScheduleManager.courses.maxOfOrNull { it.weekEnd } ?: 16
                              val customTime = cObj.optString("custom_time", "").trim()
                              var sStart = cObj.optInt("sec_start", 1).coerceIn(1, 13)
                              var sEnd = cObj.optInt("sec_end", sStart).coerceIn(sStart, 13)
                              if (customTime.isNotEmpty() && customTime.contains("-")) {
                                  val times = customTime.split("-")
                                  if (times.size >= 2) {
                                      val snapped = ScheduleManager.snapTimeToSections(times[0].trim(), times[1].trim())
                                      sStart = snapped.first
                                      sEnd = snapped.second
                                  }
                              }
                              val name = cObj.optString("name", "新日程").trim()
                              val sWStart = cObj.optInt("week_start", curWeek).coerceAtLeast(1)
                              val sWEnd = cObj.optInt("week_end", if (ScheduleManager.isActivity(name, customTime, trimmed)) sWStart else maxWeek).coerceAtLeast(1)
                              val weekRange = ScheduleManager.resolveWeekRange(trimmed, name, customTime, sWStart, sWEnd, curWeek, maxWeek)

                              parsedCourse = Course(
                                  name = name,
                                  weekday = cObj.optInt("weekday", 1).coerceIn(1, 7),
                                  secStart = sStart,
                                  secEnd = sEnd,
                                  weekStart = weekRange.first,
                                  weekEnd = weekRange.second,
                                  parity = cObj.optString("parity", "all"),
                                  room = cObj.optString("room", "").trim(),
                                  teacher = cObj.optString("teacher", "").trim(),
                                  customTime = customTime,
                                  note = if (customTime.isNotEmpty()) "AI活动录入" else "AI智能录入"
                              )
                              finalContent = finalContent.replace(matchedFullText, "").trim()
                          } catch (e: Exception) {
                              e.printStackTrace()
                          }
                      }
                  }

                  // 4. 解析番茄钟专注指令 ```json:start_pomodoro ... ```
                  var parsedPomodoroMinutes: Int? = null
                  val pomoPattern = java.util.regex.Pattern.compile("```(?:json:start_pomodoro)?\\s*(\\{[\\s\\S]*?\"minutes\"[\\s\\S]*?\\})\\s*```")
                  if (finalContent.contains("```json:start_pomodoro") || (finalContent.contains("\"minutes\"") && (trimmed.contains("专注") || trimmed.contains("番茄钟") || trimmed.contains("自习")))) {
                      val pomoMatcher = pomoPattern.matcher(finalContent)
                      if (pomoMatcher.find()) {
                          try {
                              val pObj = JSONObject(pomoMatcher.group(1) ?: "")
                              val mins = pObj.optInt("minutes", 25).coerceIn(1, 180)
                              parsedPomodoroMinutes = mins
                              PomodoroTimer.startFocus(mins)
                              finalContent = finalContent.replace(pomoMatcher.group(0) ?: "", "").trim()
                          } catch (e: Exception) {
                              e.printStackTrace()
                          }
                      }
                  }

                  // 5. 解析灵感便签指令 ```json:create_note ... ```
                  var parsedCreatedNote: Note? = null
                  val notePattern = java.util.regex.Pattern.compile("```(?:json:create_note)?\\s*(\\{[\\s\\S]*?\"content\"[\\s\\S]*?\\})\\s*```")
                  if (finalContent.contains("```json:create_note") || (finalContent.contains("\"content\"") && (trimmed.contains("记一下") || trimmed.contains("备忘") || trimmed.contains("便签")))) {
                      val noteMatcher = notePattern.matcher(finalContent)
                      if (noteMatcher.find()) {
                          try {
                              val nObj = JSONObject(noteMatcher.group(1) ?: "")
                              val nContent = nObj.optString("content", "").trim()
                              var nTitle = nObj.optString("title", "").trim()
                              if (nTitle.isEmpty()) {
                                  nTitle = if (nContent.length > 15) nContent.take(15) + "…" else nContent
                              }
                              if (nContent.isNotEmpty()) {
                                  parsedCreatedNote = NotesManager.getInstance(context).createNote(nTitle, nContent)
                              }
                              finalContent = finalContent.replace(noteMatcher.group(0) ?: "", "").trim()
                          } catch (e: Exception) {
                              e.printStackTrace()
                          }
                      }
                  }

                  // 6. 解析教学安排与调课/停课调整指令 ```json:adjust_schedule ... ```
                  var parsedAdjustments: List<com.amiya.pet.core.schedule.ScheduleAdjustment>? = null
                  val adjPattern = java.util.regex.Pattern.compile("```(?:json:adjust_schedule)?\\s*(\\{[\\s\\S]*?\"adjustments\"[\\s\\S]*?\\})\\s*```")
                  if (finalContent.contains("```json:adjust_schedule") || finalContent.contains("\"adjustments\"")) {
                      val adjMatcher = adjPattern.matcher(finalContent)
                      if (adjMatcher.find()) {
                          try {
                              val rootObj = JSONObject(adjMatcher.group(1) ?: "")
                              val arr = rootObj.optJSONArray("adjustments") ?: JSONArray()
                              val list = mutableListOf<com.amiya.pet.core.schedule.ScheduleAdjustment>()
                              for (i in 0 until arr.length()) {
                                  val item = arr.getJSONObject(i)
                                  val d = item.optString("date", "").trim()
                                  val t = item.optString("type", "substitute").trim()
                                  val tw = if (item.has("target_week") && !item.isNull("target_week")) item.getInt("target_week") else null
                                  val twd = if (item.has("target_weekday") && !item.isNull("target_weekday")) item.getInt("target_weekday") else null
                                  val r = item.optString("reason", "").trim()
                                  if (d.isNotEmpty()) {
                                      list.add(com.amiya.pet.core.schedule.ScheduleAdjustment(
                                          date = d,
                                          type = t,
                                          targetWeek = tw,
                                          targetWeekday = twd,
                                          reason = r
                                      ))
                                  }
                              }
                              if (list.isNotEmpty()) {
                                  ScheduleManager.addAdjustments(list, context)
                                  parsedAdjustments = list
                              }
                              finalContent = finalContent.replace(adjMatcher.group(0) ?: "", "").trim()
                          } catch (e: Exception) {
                              e.printStackTrace()
                          }
                      }
                  }

                  // 7. 本地轻量 NLP 正则规则辅助兜底（若模型未输出代码块）
                  val delKeywords = listOf("删除", "删掉", "删了", "退课", "取消", "移除", "去掉", "不开", "不上了")
                  val modKeywords = listOf("改到", "改成", "改在", "改至", "推迟到", "推迟至", "提前到", "提前至", "调整到", "调整为", "换到", "换成")

                  if (parsedDeletedCourse == null && parsedModifyResult == null && parsedCourse == null) {
                      if (delKeywords.any { trimmed.contains(it) }) {
                          parsedDeletedCourse = ScheduleManager.parseDeleteFromNaturalLanguage(trimmed, context)
                      } else if (modKeywords.any { trimmed.contains(it) }) {
                          parsedModifyResult = ScheduleManager.parseModifyFromNaturalLanguage(trimmed, context)
                      } else if (trimmed.contains("加一门") || trimmed.contains("加一节") || trimmed.contains("添加") || trimmed.contains("录入") ||
                          trimmed.contains("组会") || trimmed.contains("会议") || trimmed.contains("例会") || trimmed.contains("实验") ||
                          trimmed.contains("活动") || trimmed.contains("讲座") || trimmed.contains("答疑") ||
                          (trimmed.contains("课") && (trimmed.contains("周") || trimmed.contains("星期") || trimmed.contains("节"))) ||
                          (trimmed.contains("周") && (trimmed.contains("点") || trimmed.contains(":")))) {
                          parsedCourse = ScheduleManager.parseCourseFromNaturalLanguage(trimmed)
                      }
                  }

                  if (parsedAdjustments == null) {
                      val isNoticeInput = trimmed.contains("教学安排") || trimmed.contains("课表执行") ||
                              ((trimmed.contains("停上") || trimmed.contains("停课")) && trimmed.contains("月")) ||
                              (trimmed.contains("调课") && trimmed.contains("月"))
                      if (isNoticeInput) {
                          val noticeList = ScheduleManager.parseAdjustmentsFromNotice(trimmed)
                          if (noticeList.isNotEmpty()) {
                              ScheduleManager.addAdjustments(noticeList, context)
                              parsedAdjustments = noticeList
                          }
                      }
                  }

                  if (parsedPomodoroMinutes == null && (trimmed.contains("专注") || trimmed.contains("番茄钟") || (trimmed.contains("自习") && (trimmed.contains("开启") || trimmed.contains("开始") || trimmed.contains("来个"))))) {
                      val minsMatch = Regex("(\\d+)\\s*(?:分钟|min|m)").find(trimmed)
                      val mins = minsMatch?.groupValues?.get(1)?.toIntOrNull()?.coerceIn(1, 180) ?: 25
                      parsedPomodoroMinutes = mins
                      PomodoroTimer.startFocus(mins)
                  }

                  if (parsedCreatedNote == null && (trimmed.contains("记一下") || trimmed.contains("备忘") || trimmed.contains("记便签") || trimmed.contains("记录一下"))) {
                      val cleanText = trimmed
                          .replace(Regex("^(?:阿米娅|请|帮我|麻烦)?(?:记一下|备忘录记一下|备忘|记录一下|记便签|随手记)[:：\\s]*"), "")
                          .trim()
                      if (cleanText.isNotEmpty()) {
                          val title = if (cleanText.length > 15) cleanText.take(15) + "…" else cleanText
                          parsedCreatedNote = NotesManager.getInstance(context).createNote(title, cleanText)
                      }
                  }

                  // 清理可能残留的 json 指令块
                  finalContent = finalContent
                      .substringBefore("```json:add_course")
                      .substringBefore("```json:delete_course")
                      .substringBefore("```json:modify_course")
                      .substringBefore("```json:adjust_schedule")
                      .substringBefore("```json:start_pomodoro")
                      .substringBefore("```json:create_note")
                      .substringBefore("```json")
                      .trim()

                  if (parsedCourse != null) {
                      ScheduleManager.addCourse(parsedCourse, context)
                  }

                  val finalReply = if (finalContent.isNotEmpty()) finalContent else if (finalReasoning.isNotEmpty()) "（思考完毕）" else "博士，阿米娅在听呢。"

                  history.add(ChatMessage(
                      role = "assistant",
                      content = finalReply,
                      reasoningContent = finalReasoning,
                      addedCourse = parsedCourse,
                      deletedCourse = parsedDeletedCourse,
                      modifiedCourse = parsedModifyResult?.newCourse,
                      oldCourse = parsedModifyResult?.oldCourse,
                      startedPomodoroMinutes = parsedPomodoroMinutes,
                      createdNote = parsedCreatedNote,
                      adjustedScheduleList = parsedAdjustments
                  ))
                  onUpdate(finalReasoning, finalReply, false)
                  return@withContext finalReply
                } else {
                    lastHttpCode = conn.responseCode
                    if (index < endpoints.size - 1) {
                        continue
                    }
                }
            } catch (e: Exception) {
                lastException = e
                if (emittedTokens || index == endpoints.size - 1) {
                    break
                }
                continue
            }
        }

        // 所有候选端点均失败或容灾轮询结束：进入智能错误诊断与离线兜底
        var parsedCourse: Course? = null
        var parsedDeletedCourse: Course? = null
        var parsedModifyResult: com.amiya.pet.core.schedule.ModifyCourseResult? = null
        var parsedPomodoroMinutes: Int? = null
        var parsedCreatedNote: Note? = null
        var parsedAdjustments: List<com.amiya.pet.core.schedule.ScheduleAdjustment>? = null

        val delKeywords = listOf("删除", "删掉", "删了", "退课", "取消", "移除", "去掉", "不开", "不上了")
        val modKeywords = listOf("改到", "改成", "改在", "改至", "推迟到", "推迟至", "提前到", "提前至", "调整到", "调整为", "换到", "换成")

        val reply: String
        if (delKeywords.any { trimmed.contains(it) }) {
            parsedDeletedCourse = ScheduleManager.parseDeleteFromNaturalLanguage(trimmed, context)
            reply = if (parsedDeletedCourse != null) {
                "好的博士！阿米娅已经在离线模式下帮您把《${parsedDeletedCourse.name}》从课表中删除了。"
            } else {
                "博士，阿米娅在课表中没有找到符合条件的待删除课程。"
            }
        } else if (modKeywords.any { trimmed.contains(it) }) {
            parsedModifyResult = ScheduleManager.parseModifyFromNaturalLanguage(trimmed, context)
            reply = if (parsedModifyResult != null) {
                val old = parsedModifyResult.oldCourse
                val now = parsedModifyResult.newCourse
                val timeDesc = if (now.customTime.isNotEmpty()) "📌 [${now.customTime}]" else "周${now.weekday} 第${now.secStart}-${now.secEnd}节"
                "好的博士！阿米娅已经在离线模式下将《${old.name}》调整为：$timeDesc @${now.room.ifEmpty { "待定" }}。"
            } else {
                "博士，阿米娅没有在课表中定位到要调整的目标课程。"
            }
        } else if (trimmed.contains("加一门") || trimmed.contains("加一节") || trimmed.contains("添加") || trimmed.contains("录入") ||
            trimmed.contains("组会") || trimmed.contains("会议") || trimmed.contains("例会") || trimmed.contains("实验") ||
            trimmed.contains("活动") || trimmed.contains("讲座") || trimmed.contains("答疑") ||
            (trimmed.contains("课") && (trimmed.contains("周") || trimmed.contains("星期") || trimmed.contains("节"))) ||
            (trimmed.contains("周") && (trimmed.contains("点") || trimmed.contains(":")))) {
            parsedCourse = ScheduleManager.parseCourseFromNaturalLanguage(trimmed)
            reply = if (parsedCourse != null) {
                ScheduleManager.addCourse(parsedCourse, context)
                val timeDesc = if (parsedCourse.customTime.isNotEmpty()) "📌 [${parsedCourse.customTime}] (对应第${parsedCourse.secStart}-${parsedCourse.secEnd}节)" else "第${parsedCourse.secStart}-${parsedCourse.secEnd}节"
                "好的博士！阿米娅已经在离线状态下为您将《${parsedCourse.name}》（周${parsedCourse.weekday} $timeDesc @${parsedCourse.room.ifEmpty { "待定" }}）记录到课表了。"
            } else {
                val err = lastHttpCode?.let { diagnoseHttpError(it, lastEndpoint, isCustomKey) }
                    ?: lastException?.let { diagnoseNetworkError(it, lastEndpoint, isCustomKey) }
                    ?: "通信连接异常"
                "（$err）"
            }
        } else if (trimmed.contains("教学安排") || trimmed.contains("课表执行") ||
            ((trimmed.contains("停上") || trimmed.contains("停课")) && trimmed.contains("月")) ||
            (trimmed.contains("调课") && trimmed.contains("月"))) {
            val noticeList = ScheduleManager.parseAdjustmentsFromNotice(trimmed)
            if (noticeList.isNotEmpty()) {
                ScheduleManager.addAdjustments(noticeList, context)
                parsedAdjustments = noticeList
                val summary = noticeList.take(4).joinToString("\n") { "• ${it.date} ➔ ${if (it.type == "suspend") "停课" else it.reason}" }
                val more = if (noticeList.size > 4) "\n… 等共 ${noticeList.size} 天教学安排调整" else ""
                reply = "好的博士！阿米娅已在离线状态下为您将教学安排调整同步至课表：\n$summary$more\n课表周视图与日程提醒已实时生效。"
            } else {
                reply = "博士，阿米娅收到了教学安排通知，但未识别出具体的调课或停课日期，您可以具体说明是哪一天的课程如何调整。"
            }
        } else if (trimmed.contains("专注") || trimmed.contains("番茄钟") || (trimmed.contains("自习") && (trimmed.contains("开启") || trimmed.contains("开始") || trimmed.contains("来个")))) {
            val minsMatch = Regex("(\\d+)\\s*(?:分钟|min|m)").find(trimmed)
            val mins = minsMatch?.groupValues?.get(1)?.toIntOrNull()?.coerceIn(1, 180) ?: 25
            parsedPomodoroMinutes = mins
            PomodoroTimer.startFocus(mins)
            reply = "好的博士！阿米娅已为您开启 $mins 分钟番茄钟专注。桌面悬浮桌宠与通知栏已同步开始倒计时，请专心工作，阿米娅会一直陪伴在您身边的。"
        } else if (trimmed.contains("记一下") || trimmed.contains("备忘") || trimmed.contains("记便签") || trimmed.contains("记录一下")) {
            val cleanText = trimmed
                .replace(Regex("^(?:阿米娅|请|帮我|麻烦)?(?:记一下|备忘录记一下|备忘|记录一下|记便签|随手记)[:：\\s]*"), "")
                .trim()
            if (cleanText.isNotEmpty()) {
                val title = if (cleanText.length > 15) cleanText.take(15) + "…" else cleanText
                parsedCreatedNote = NotesManager.getInstance(context).createNote(title, cleanText)
                reply = "好的博士！阿米娅已经在灵感便签本中为您记下了《$title》。"
            } else {
                reply = "好的博士，请问具体要记下什么内容呢？阿米娅随时为您记录。"
            }
        } else if ((trimmed.contains("明天") || trimmed.contains("明日")) && (trimmed.contains("总结") || trimmed.contains("待办") || trimmed.contains("课程") || trimmed.contains("安排") || trimmed.contains("课") || trimmed.contains("日程"))) {
            reply = buildOfflineAgendaSummary(isTomorrow = true)
        } else if ((trimmed.contains("今天") || trimmed.contains("今日")) && (trimmed.contains("总结") || trimmed.contains("待办") || trimmed.contains("课程") || trimmed.contains("安排") || trimmed.contains("课") || trimmed.contains("日程"))) {
            reply = buildOfflineAgendaSummary(isTomorrow = false)
        } else {
            val diag = if (lastHttpCode != null) {
                diagnoseHttpError(lastHttpCode, lastEndpoint, isCustomKey)
            } else if (lastException != null) {
                diagnoseNetworkError(lastException, lastEndpoint, isCustomKey)
            } else {
                null
            }
            reply = if (diag != null) "（$diag）" else fallbackReplies.random()
        }

        history.add(ChatMessage(
            role = "assistant",
            content = reply,
            addedCourse = parsedCourse,
            deletedCourse = parsedDeletedCourse,
            modifiedCourse = parsedModifyResult?.newCourse,
            oldCourse = parsedModifyResult?.oldCourse,
            startedPomodoroMinutes = parsedPomodoroMinutes,
            createdNote = parsedCreatedNote,
            adjustedScheduleList = parsedAdjustments
        ))
        onUpdate("", reply, false)
        reply
    }

    private fun buildOfflineAgendaSummary(isTomorrow: Boolean): String {
        val cal = Calendar.getInstance()
        if (isTomorrow) {
            cal.add(Calendar.DAY_OF_YEAR, 1)
        }
        val targetDate = cal.time
        val targetIdx = cal.get(Calendar.DAY_OF_WEEK)
        val targetWeekday = if (targetIdx == Calendar.SUNDAY) 7 else targetIdx - 1
        val curWeekNo = ScheduleManager.getWeekNo(Date()) ?: 1
        val targetWeekNo = ScheduleManager.getWeekNo(targetDate) ?: curWeekNo
        val weekdayNames = arrayOf("", "周一", "周二", "周三", "周四", "周五", "周六", "周日")
        val dayName = weekdayNames.getOrElse(targetWeekday) { "周一" }
        val dateStr = SimpleDateFormat("M月d日", Locale.CHINESE).format(targetDate)
        val label = if (isTomorrow) "明日" else "今日"

        val sb = StringBuilder()
        sb.append("博士，这是为您整理的${label}（$dateStr $dayName · 第 $targetWeekNo 周）综合日程简报：\n\n")

        // 1. 课程安排
        val courses = ScheduleManager.getCoursesOn(targetWeekday, targetWeekNo)
        sb.append("📅 课程安排：\n")
        if (courses.isEmpty()) {
            sb.append("  - 全天无排课，整天空闲！博士可以自由规划自习、大作业攻坚或好好休息。\n")
        } else {
            courses.forEach { c ->
                val timeDesc = if (c.customTime.isNotEmpty()) "📌 [${c.customTime}]" else "第${c.secStart}-${c.secEnd}节"
                val roomStr = if (c.room.isNotEmpty() && c.room != "待定") " @${c.room}" else ""
                val teacherStr = if (c.teacher.isNotEmpty()) " (${c.teacher})" else ""
                sb.append("  - $timeDesc 《${c.name}》$roomStr$teacherStr\n")
            }
        }

        // 2. 待办与灵感便签
        val notes = NotesManager.getInstance(context).notes
        if (notes.isNotEmpty()) {
            sb.append("\n📝 灵感便签待办（最新）：\n")
            notes.take(4).forEach { n ->
                val pinStr = if (n.pinned) "📌 " else ""
                val snippet = n.content.lineSequence().firstOrNull { it.isNotBlank() } ?: n.title
                sb.append("  - $pinStr《${n.title}》：$snippet\n")
            }
        }

        // 3. 考试倒计时
        ExamManager.load(context)
        val upcomingExams = ExamManager.exams.filter { !it.isFinished() }
        if (upcomingExams.isNotEmpty()) {
            sb.append("\n🎯 近期备考提醒：\n")
            upcomingExams.take(2).forEach { ex ->
                val daysLeft = ((ex.examTimeMillis - System.currentTimeMillis()) / (24 * 3600 * 1000L)).coerceAtLeast(0)
                sb.append("  - 《${ex.title}》还有 $daysLeft 天（${ex.formattedDateStr()} ${ex.formattedTimeRangeStr()}）\n")
            }
        }

        sb.append("\n💡 阿米娅提示：无论任务多繁重，也请记得适当喝水、保持充足睡眠。阿米娅会一直支持您的！")
        return sb.toString()
    }

    suspend fun testConnection(testBaseUrl: String, testModel: String, testApiKey: String): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val base = testBaseUrl.trim()
        if (base.isEmpty()) return@withContext Pair(false, "接口地址不能为空")
        val m = testModel.trim()
        if (m.isEmpty()) return@withContext Pair(false, "模型名称不能为空")

        val hasCustom = testApiKey.trim().isNotEmpty()
        val urlStr = if (hasCustom) {
            resolveChatEndpoint(base)
        } else {
            resolveChatEndpoint(publicRelayUrl.trim().ifBlank { DEFAULT_PUBLIC_RELAY_URL })
        }
        val t0 = System.currentTimeMillis()

        try {
            val url = URL(urlStr)
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 8000
                readTimeout = 8000
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                if (hasCustom) {
                    setRequestProperty("Authorization", "Bearer ${testApiKey.trim()}")
                }
                setRequestProperty("User-Agent", "AmiyaPet-Android")
            }

            val reqBody = JSONObject().apply {
                put("model", m)
                put("messages", JSONArray().apply {
                    put(JSONObject().apply {
                        put("role", "user")
                        put("content", "hi")
                    })
                })
                put("max_tokens", 1)
            }

            OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use {
                it.write(reqBody.toString())
                it.flush()
            }

            val code = conn.responseCode
            val elapsed = System.currentTimeMillis() - t0
            if (code in 200..299) {
                Pair(true, "连接成功 (HTTP $code，耗时: ${elapsed}ms)")
            } else {
                var detail = ""
                try {
                    val errStream = conn.errorStream ?: conn.inputStream
                    val errText = errStream?.bufferedReader(Charsets.UTF_8)?.readText() ?: ""
                    if (errText.isNotEmpty()) {
                        val errObj = JSONObject(errText)
                        val errInfo = errObj.optJSONObject("error")
                        detail = errInfo?.optString("message", "") ?: errObj.optString("message", "")
                    }
                } catch (ignored: Exception) {}

                val diag = diagnoseHttpError(code, urlStr, hasCustom)
                val msg = if (detail.isNotEmpty() && detail.length < 80 && !diag.contains(detail)) {
                    "$diag [$detail] (耗时: ${elapsed}ms)"
                } else {
                    "$diag (耗时: ${elapsed}ms)"
                }
                Pair(false, msg)
            }
        } catch (e: Exception) {
            val elapsed = System.currentTimeMillis() - t0
            val diag = diagnoseNetworkError(e, urlStr, hasCustom)
            Pair(false, "$diag (耗时: ${elapsed}ms)")
        }
    }

    /**
     * 多模态视觉解析课表图片（支持直接传入图片字节数据）
     * 自动下采样压缩并转换为 Base64，调用 OpenAI/GLM-4V 兼容的多模态接口解析课程表
     */
    suspend fun parseScheduleFromImage(
        context: Context,
        imageBytes: ByteArray,
        customVisionModel: String? = null
    ): Result<List<Course>> = withContext(Dispatchers.IO) {
        try {
            // 1. 优化图像（处理 EXIF 旋转、长边最大 1600px 限制，转为 Base64）
            val base64DataUrl = decodeAndCompressImage(imageBytes)
                ?: return@withContext Result.failure(Exception("无法读取或解码所选图片，请重新选择"))

            // 2. 路由 Vision 模型与端点
            val customKey = apiKey.trim()
            val isCustomKey = customKey.isNotEmpty()

            val endpoints: List<String> = if (isCustomKey) {
                listOf(resolveChatEndpoint(baseUrl))
            } else {
                getCandidateRelays(publicRelayUrl)
            }

            // 确定 Vision 模型：若指定了 customVisionModel 则优先使用；
            // 否则若当前 baseUrl 是 BigModel 则使用 glm-4v-flash；
            // 若当前 model 本身就是 vision 模型（包含 4v、vision、vl、4o 等）则使用当前 model；
            // 默认推荐智谱视觉模型 glm-4v-flash
            val targetModel: String = when {
                !customVisionModel.isNullOrBlank() -> customVisionModel.trim()
                model.contains("4v", ignoreCase = true) || model.contains("vision", ignoreCase = true) ||
                    model.contains("-vl", ignoreCase = true) || model.contains("4o", ignoreCase = true) -> model
                baseUrl.contains("bigmodel.cn") -> "glm-4v-flash"
                baseUrl.contains("openai.com") -> "gpt-4o-mini"
                baseUrl.contains("dashscope.aliyuncs.com") -> "qwen-vl-plus"
                else -> "glm-4v-flash"
            }

            val authHeader: String? = if (isCustomKey) "Bearer $customKey" else null

            val prompt = """
            你是一个专业的教务课表识别与排课分析专家。请仔细分析这张课表图片（包含课程表网格、周次、时间、星期几、课程名称、教室/地点、任课教师等信息）。
            
            请尽可能完整、准确地提取出图中的所有课程，输出纯 JSON 数组，必须包裹在 ```json:import_courses 和 ``` 代码块中。
            输出格式规范如下：
            [
              {
                "name": "课程名称（如：高等数学。去掉无用的前缀后缀，只保留规范课程名）",
                "weekday": 1, // 星期几，整数 1 到 7。1=周一，2=周二，3=周三，4=周四，5=周五，6=周六，7=周日。必须严格根据课表顶部的星期列对齐！
                "sec_start": 1, // 起始节次，整数 1 到 13。例如第1-2节填 1，第3-4节填 3，第6-7节填 6，等等
                "sec_end": 2, // 结束节次，整数 1 到 13。例如第1-2节填 2，第3-4节填 4
                "week_start": 1, // 起始周，整数。例如“1-16周”填 1；未注明默认 1
                "week_end": 16, // 结束周，整数。例如“1-16周”填 16；未注明默认 16
                "parity": "all", // 单双周："all"=每周/全周, "odd"=单周, "even"=双周
                "room": "教学楼/教室（如：教四101、综B203，若未标明可填空字符串）",
                "teacher": "授课教师姓名（若未标明可填空字符串）",
                "note": "备注说明（选填）"
              }
            ]
            
            【特别注意事项】：
            1. 星期数字请严格遵循：1=周一, 2=周二, 3=周三, 4=周四, 5=周五, 6=周六, 7=周日。
            2. 同一门课程在不同星期或不同节次上课，请拆分为多个独立的课程时段对象。
            3. 请仔细核对每门课所处的横行（节次）与纵列（星期），确保不遗漏、不错位。
            4. 必须且仅在 ```json:import_courses ... ``` 标记的代码块内输出合法的 JSON 数组。
            """.trimIndent()

            val reqBody = JSONObject().apply {
                put("model", targetModel)
                put("temperature", 0.1)
                val messages = JSONArray()
                val userMsg = JSONObject().apply {
                    put("role", "user")
                    val contents = JSONArray()
                    contents.put(JSONObject().apply {
                        put("type", "text")
                        put("text", prompt)
                    })
                    contents.put(JSONObject().apply {
                        put("type", "image_url")
                        put("image_url", JSONObject().apply {
                            put("url", base64DataUrl)
                        })
                    })
                    put("content", contents)
                }
                messages.put(userMsg)
                put("messages", messages)
            }

            var lastException: Exception? = null
            var lastCode: Int? = null
            var lastErrDetail = ""

            for (ep in endpoints) {
                try {
                    val url = URL(ep)
                    val conn = (url.openConnection() as HttpURLConnection).apply {
                        requestMethod = "POST"
                        connectTimeout = 20000
                        readTimeout = 60000
                        doOutput = true
                        setRequestProperty("Content-Type", "application/json; charset=utf-8")
                        if (authHeader != null) {
                            setRequestProperty("Authorization", authHeader)
                        }
                        setRequestProperty("User-Agent", "AmiyaPet-Android")
                    }

                    OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use {
                        it.write(reqBody.toString())
                        it.flush()
                    }

                    val code = conn.responseCode
                    lastCode = code
                    if (code in 200..299) {
                        val respText = conn.inputStream.bufferedReader(Charsets.UTF_8).readText()
                        val jsonResp = JSONObject(respText)
                        val choices = jsonResp.optJSONArray("choices")
                        val content = choices?.optJSONObject(0)?.optJSONObject("message")?.optString("content", "") ?: ""
                        val courses = parseCoursesFromAiResponse(content)
                        if (courses.isNotEmpty()) {
                            return@withContext Result.success(courses)
                        } else {
                            return@withContext Result.failure(Exception("AI 未能从课表图片中识别出有效课程，请确保图片清晰且包含课表表格与文字。"))
                        }
                    } else {
                        val errStream = conn.errorStream ?: conn.inputStream
                        lastErrDetail = errStream?.bufferedReader(Charsets.UTF_8)?.readText() ?: ""
                    }
                } catch (e: Exception) {
                    lastException = e
                }
            }

            val errDesc = lastCode?.let { diagnoseHttpError(it, endpoints.firstOrNull() ?: "", isCustomKey) }
                ?: lastException?.let { diagnoseNetworkError(it, endpoints.firstOrNull() ?: "", isCustomKey) }
                ?: "请求失败"
            Result.failure(Exception(if (lastErrDetail.isNotEmpty()) "$errDesc ($lastErrDetail)" else errDesc))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 多模态视觉解析课表图片（Uri 重载方法）
     */
    suspend fun parseScheduleFromImage(
        context: Context,
        imageUri: Uri,
        customVisionModel: String? = null
    ): Result<List<Course>> {
        val bytes = try {
            context.contentResolver.openInputStream(imageUri)?.use { it.readBytes() }
        } catch (e: Exception) {
            null
        } ?: return Result.failure(Exception("无法读取所选图片数据，请重新选择"))
        return parseScheduleFromImage(context, bytes, customVisionModel)
    }

    private fun decodeAndCompressImage(bytes: ByteArray): String? {
        try {
            // 1. 读取 EXIF 旋转角度
            val orientation = try {
                val exif = ExifInterface(ByteArrayInputStream(bytes))
                exif.getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)
            } catch (ignored: Exception) {
                ExifInterface.ORIENTATION_NORMAL
            }

            // 2. 获取原始宽高
            val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)

            val reqMaxDim = 1600
            var inSampleSize = 1
            val maxOriginal = Math.max(options.outWidth, options.outHeight)
            if (maxOriginal > reqMaxDim) {
                while (maxOriginal / inSampleSize > reqMaxDim * 1.5) {
                    inSampleSize *= 2
                }
            }

            // 3. 采样解码
            options.inJustDecodeBounds = false
            options.inSampleSize = inSampleSize
            val rawBmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)
                ?: return null

            // 4. 处理 EXIF 旋转
            val matrix = Matrix()
            when (orientation) {
                ExifInterface.ORIENTATION_ROTATE_90 -> matrix.postRotate(90f)
                ExifInterface.ORIENTATION_ROTATE_180 -> matrix.postRotate(180f)
                ExifInterface.ORIENTATION_ROTATE_270 -> matrix.postRotate(270f)
                ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.postScale(-1f, 1f)
                ExifInterface.ORIENTATION_FLIP_VERTICAL -> matrix.postScale(1f, -1f)
            }

            // 5. 比例缩放至最大边 <= 1600px
            val currentMax = Math.max(rawBmp.width, rawBmp.height)
            if (currentMax > reqMaxDim) {
                val scale = reqMaxDim.toFloat() / currentMax.toFloat()
                matrix.postScale(scale, scale)
            }

            val finalBmp = if (!matrix.isIdentity) {
                val transformed = Bitmap.createBitmap(rawBmp, 0, 0, rawBmp.width, rawBmp.height, matrix, true)
                if (transformed != rawBmp) {
                    rawBmp.recycle()
                }
                transformed
            } else {
                rawBmp
            }

            // 6. 压缩为 JPEG 85% 并转换为 Base64 Data URL
            val baos = ByteArrayOutputStream()
            finalBmp.compress(Bitmap.CompressFormat.JPEG, 85, baos)
            finalBmp.recycle()
            val outBytes = baos.toByteArray()
            val b64 = Base64.encodeToString(outBytes, Base64.NO_WRAP)
            return "data:image/jpeg;base64,$b64"
        } catch (e: Exception) {
            android.util.Log.e("AmiyaBrain", "decodeAndCompressImage failed", e)
            return null
        }
    }

    fun parseCoursesFromAiResponse(rawResponse: String): List<Course> {
        val list = mutableListOf<Course>()
        val jsonContent = when {
            rawResponse.contains("```json:import_courses") -> {
                rawResponse.substringAfter("```json:import_courses").substringBefore("```").trim()
            }
            rawResponse.contains("```json") -> {
                rawResponse.substringAfter("```json").substringBefore("```").trim()
            }
            rawResponse.contains("```") -> {
                rawResponse.substringAfter("```").substringBefore("```").trim()
            }
            rawResponse.contains("[") && rawResponse.contains("]") -> {
                val start = rawResponse.indexOf('[')
                val end = rawResponse.lastIndexOf(']')
                if (end > start) rawResponse.substring(start, end + 1).trim() else ""
            }
            else -> ""
        }
        if (jsonContent.isEmpty()) return emptyList()

        try {
            val array = JSONArray(jsonContent)
            for (i in 0 until array.length()) {
                val obj = array.optJSONObject(i) ?: continue
                val name = obj.optString("name", "").trim()
                if (name.isEmpty()) continue

                val weekday = when {
                    obj.has("weekday") -> obj.optInt("weekday", 1)
                    obj.has("day") -> obj.optInt("day", 1)
                    else -> 1
                }.coerceIn(1, 7)

                val secStart = when {
                    obj.has("sec_start") -> obj.optInt("sec_start", 1)
                    obj.has("secStart") -> obj.optInt("secStart", 1)
                    obj.has("start_section") -> obj.optInt("start_section", 1)
                    else -> 1
                }.coerceIn(1, 13)

                val secEnd = when {
                    obj.has("sec_end") -> obj.optInt("sec_end", secStart)
                    obj.has("secEnd") -> obj.optInt("secEnd", secStart)
                    obj.has("end_section") -> obj.optInt("end_section", secStart)
                    else -> secStart
                }.coerceIn(secStart, 13)

                val weekStart = when {
                    obj.has("week_start") -> obj.optInt("week_start", 1)
                    obj.has("weekStart") -> obj.optInt("weekStart", 1)
                    else -> 1
                }.coerceAtLeast(1)

                val weekEnd = when {
                    obj.has("week_end") -> obj.optInt("week_end", 16)
                    obj.has("weekEnd") -> obj.optInt("weekEnd", 16)
                    else -> 16
                }.coerceAtLeast(weekStart)

                val rawParity = obj.optString("parity", "all").lowercase(Locale.getDefault())
                val parity = when {
                    rawParity.contains("odd") || rawParity.contains("单") -> "odd"
                    rawParity.contains("even") || rawParity.contains("双") -> "even"
                    else -> "all"
                }

                val room = obj.optString("room", obj.optString("classroom", obj.optString("location", ""))).trim()
                val teacher = obj.optString("teacher", obj.optString("instructor", "")).trim()
                val note = obj.optString("note", "").trim()

                list.add(
                    Course(
                        name = name,
                        weekday = weekday,
                        secStart = secStart,
                        secEnd = secEnd,
                        weekStart = weekStart,
                        weekEnd = weekEnd,
                        parity = parity,
                        room = room,
                        teacher = teacher,
                        note = note
                    )
                )
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return list
    }

    companion object {
        val DEFAULT_PUBLIC_RELAYS = listOf(
            "https://wmntwvrw57.sealosbja.site/v1/chat/completions",
            "https://amiya-ai-relay.wyuio-0.workers.dev/v1/chat/completions"
        )
        const val DEFAULT_PUBLIC_RELAY_URL = "https://wmntwvrw57.sealosbja.site/v1/chat/completions"

        fun resolveChatEndpoint(base: String): String {
            val trimmed = base.trim().removeSuffix("/")
            return when {
                trimmed.endsWith("/chat/completions") -> trimmed
                trimmed.contains("/paas/v4") -> "$trimmed/chat/completions"
                trimmed.endsWith("/v1") -> "$trimmed/chat/completions"
                else -> "$trimmed/v1/chat/completions"
            }
        }

        fun getCandidateRelays(customRelay: String? = null): List<String> {
            val list = mutableListOf<String>()
            if (!customRelay.isNullOrBlank()) {
                val resolved = resolveChatEndpoint(customRelay.trim())
                list.add(resolved)
            }
            for (relay in DEFAULT_PUBLIC_RELAYS) {
                val resolved = resolveChatEndpoint(relay)
                if (!list.contains(resolved)) {
                    list.add(resolved)
                }
            }
            return list
        }

        fun diagnoseNetworkError(e: Throwable, targetUrl: String = "", hasCustomKey: Boolean = false): String {
            val msg = e.message?.lowercase() ?: ""
            val eStr = e.toString().lowercase()
            val isDomestic = listOf("bigmodel.cn", "deepseek.com", "moonshot.cn", "aliyuncs.com", "dashscope", "sealos", "bja.site")
                .any { targetUrl.lowercase().contains(it) }

            if ("ssl" in eStr || "cert" in eStr) {
                return "安全握手失败：SSL 证书校验异常，通常由 VPN/代理或中间人拦截引起。建议将 AI 服务商域名加入代理软件的「直连」规则。"
            }
            if ("unknownhost" in eStr || "dns" in eStr || "nodename" in eStr) {
                return "域名解析失败：DNS 无法解析接口地址，请检查网络连接或系统代理分流规则。"
            }
            if ("timeout" in msg || "timed out" in msg || "sockettimeoutexception" in eStr) {
                if (isDomestic) {
                    return "连接超时：国内模型接口响应超时。若开启了 VPN/代理，国内域名可能被绕路延迟，建议将该域名设为「直连」规则。"
                }
                return "连接超时：无法在规定时间内连上模型端点，请检查网络稳定性或代理设置。"
            }
            if ("refused" in msg || "connection refused" in eStr) {
                if (listOf("localhost", "127.0.0.1", "10.0.2.2").any { targetUrl.lowercase().contains(it) }) {
                    return "连接被拒绝 (本地服务未启动)：无法连接到本地 Ollama，请确保本地 Ollama 正在运行且端口正确。"
                }
                return "连接被拒绝：目标端点拒绝连接，请检查端口与网络代理分流设置。"
            }
            if (!hasCustomKey) {
                return "公共 AI 线路暂不可用/网络连接异常，建议在「模型配置」中点击「智谱 GLM [永久免费]」一键换用专属免翻线路。"
            }
            return "网络连接出错了，博士稍后再试：${e.javaClass.simpleName}"
        }

        fun diagnoseHttpError(statusCode: Int, targetUrl: String = "", hasCustomKey: Boolean = false): String {
            return when (statusCode) {
                401 -> "API 认证失败 [HTTP 401]：您的 API Key 无效或未生效，请在「模型配置」中核对密钥。"
                403 -> "访问被拒绝 [HTTP 403]：该模型接口无权限或 IP 受限，请检查服务商控制台权限与账户余额。"
                404 -> "接口端点未找到 [HTTP 404]：请检查模型配置中的接口地址（Base URL）是否正确。"
                429 -> "请求频控 [HTTP 429]：当前模型额度已耗尽或请求过于频繁，请稍后再试或检查账户余额。"
                in listOf(500, 502, 503, 504) -> {
                    if (!hasCustomKey) {
                        "公共免 Key 线路临时维护中 [HTTP $statusCode]，多节点轮询均未响应。建议在设置中点击「智谱 GLM [永久免费]」标签一键换用个人专属免翻线路。"
                    } else {
                        "服务商服务端暂时不可用 [HTTP $statusCode]，请稍后重试或检查服务商状态页。"
                    }
                }
                else -> "HTTP 请求异常 [HTTP $statusCode]，请检查网络或服务商状态。"
            }
        }

        @Volatile
        private var INSTANCE: AmiyaBrain? = null

        fun getInstance(context: Context): AmiyaBrain {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: AmiyaBrain(context.applicationContext).also { INSTANCE = it }
            }
        }
    }
}
