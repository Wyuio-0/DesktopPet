package com.amiya.pet.ui

import android.widget.Toast
import com.amiya.pet.service.AppBackgroundService
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.amiya.pet.core.schedule.Course
import com.amiya.pet.core.schedule.ScheduleManager
import java.text.SimpleDateFormat
import java.util.*

private val COURSE_COLORS = listOf(
    Color(0xFF4285F4), Color(0xFF34A853), Color(0xFFEA4335),
    Color(0xFFFBBC05), Color(0xFFAB47BC), Color(0xFF00ACC1),
    Color(0xFF8D6E63), Color(0xFFFF7043), Color(0xFF26A69A), Color(0xFF7E57C2)
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScheduleScreen(
    currentWeek: Int,
    onWeekChange: (Int) -> Unit,
    showImportDialog: Boolean = false,
    onDismissImportDialog: () -> Unit = {},
    onOpenImportDialog: () -> Unit = {},
    showImageImportDialog: Boolean = false,
    onDismissImageImportDialog: () -> Unit = {},
    onOpenImageImportDialog: () -> Unit = {},
    showReminderDialog: Boolean = false,
    onDismissReminderDialog: () -> Unit = {},
    showAddCourseDialog: Boolean = false,
    onDismissAddCourseDialog: () -> Unit = {},
    onOpenAddCourseDialog: () -> Unit = {},
    onConsultAi: (String) -> Unit = {}
) {
    val context = LocalContext.current
    var refreshTrigger by remember { mutableIntStateOf(0) }
    var showInternalImageImportDialog by remember { mutableStateOf(false) }
    
    // 首次进入立即同步加载，确保无论冷启动还是热切页，内存数据绝对最新
    var isDataLoaded by remember {
        ScheduleManager.load(context)
        mutableStateOf(true)
    }

    val courses = remember(refreshTrigger, isDataLoaded, ScheduleManager.coursesVersion) {
        ScheduleManager.courses
    }
    
    val colorMap = remember(refreshTrigger, courses) {
        val map = mutableMapOf<String, Color>()
        var idx = 0
        courses.forEach { 
            if (!map.containsKey(it.name)) {
                map[it.name] = COURSE_COLORS[idx % COURSE_COLORS.size]
                idx++
            }
        }
        map
    }

    // 交互弹窗状态
    var selectedCourseForDetail by remember { mutableStateOf<Course?>(null) }
    var editingCourse by remember { mutableStateOf<Course?>(null) }
    var showCourseEditDialog by remember { mutableStateOf(false) }
    var deletingCourse by remember { mutableStateOf<Course?>(null) }
    var newCourseWeekday by remember { mutableIntStateOf(1) }
    var newCourseSection by remember { mutableIntStateOf(1) }

    val cal = Calendar.getInstance()
    val todayIdx = cal.get(Calendar.DAY_OF_WEEK)
    val currentIsoWeekday = if (todayIdx == Calendar.SUNDAY) 7 else todayIdx - 1

    LaunchedEffect(refreshTrigger) {
        ScheduleManager.load(context)
        isDataLoaded = true
    }

    // 响应外部顶栏触发的添加课程
    LaunchedEffect(showAddCourseDialog) {
        if (showAddCourseDialog) {
            editingCourse = null
            newCourseWeekday = currentIsoWeekday
            newCourseSection = 1
            showCourseEditDialog = true
            onDismissAddCourseDialog()
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        if (courses.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.padding(24.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.DateRange,
                        contentDescription = null,
                        tint = Color.Gray,
                        modifier = Modifier.size(48.dp)
                    )
                    Spacer(Modifier.height(12.dp))
                    Text(
                        text = "暂无课表数据",
                        color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f),
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        text = "💡 支持手动录入课程或一键导入教务课表，阿米娅将自动为您规划作息与学情分析",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.85f),
                        textAlign = TextAlign.Center
                    )
                    Spacer(Modifier.height(20.dp))
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Button(
                            onClick = { showInternalImageImportDialog = true },
                            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                        ) {
                            Icon(Icons.Default.DocumentScanner, contentDescription = null, tint = Color.Black, modifier = Modifier.size(16.dp))
                            Spacer(Modifier.width(4.dp))
                            Text("📸 AI 截图导入", color = Color.Black, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                        }
                        OutlinedButton(
                            onClick = {
                                editingCourse = null
                                newCourseWeekday = currentIsoWeekday
                                newCourseSection = 1
                                showCourseEditDialog = true
                            }
                        ) {
                            Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(Modifier.width(4.dp))
                            Text("手动录入", fontSize = 13.sp)
                        }
                        OutlinedButton(
                            onClick = onOpenImportDialog
                        ) {
                            Icon(Icons.Default.Download, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(Modifier.width(4.dp))
                            Text("JSON", fontSize = 13.sp)
                        }
                    }
                }
            }
        } else {
            TimetableGrid(
                weekNo = currentWeek,
                refreshTrigger = refreshTrigger,
                colorMap = colorMap,
                onPrevWeek = { if (currentWeek > 1) onWeekChange(currentWeek - 1) },
                onNextWeek = { onWeekChange(currentWeek + 1) },
                onSelectCourse = { selectedCourseForDetail = it },
                onAddCourseAt = { wd, sec ->
                    editingCourse = null
                    newCourseWeekday = wd
                    newCourseSection = sec
                    showCourseEditDialog = true
                }
            )
        }
    }
    
    if (showImportDialog) {
        var jsonInput by remember { mutableStateOf("") }
        var dateInput by remember { mutableStateOf(SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())) }
        var resultMsg by remember { mutableStateOf("") }
        
        AlertDialog(
            onDismissRequest = onDismissImportDialog,
            containerColor = MaterialTheme.colorScheme.surface,
            title = { Text("导入强智教务课表", color = MaterialTheme.colorScheme.onSurface) },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    Text("请在下方粘贴抓包得到的课表 JSON 数据：", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurface)
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = jsonInput,
                        onValueChange = { jsonInput = it },
                        modifier = Modifier.fillMaxWidth().height(150.dp),
                        textStyle = LocalTextStyle.current.copy(color = MaterialTheme.colorScheme.onSurface)
                    )
                    Spacer(Modifier.height(12.dp))
                    Text("开学日期 (第一周周一，格式 YYYY-MM-DD)：", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurface)
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = dateInput,
                        onValueChange = { dateInput = it },
                        modifier = Modifier.fillMaxWidth(),
                        textStyle = LocalTextStyle.current.copy(color = MaterialTheme.colorScheme.onSurface)
                    )
                    if (resultMsg.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Text(resultMsg, color = if(resultMsg.contains("成功")) Color(0xFF4CAF50) else MaterialTheme.colorScheme.error, fontSize = 13.sp)
                        if (resultMsg.contains("成功")) {
                            Spacer(Modifier.height(10.dp))
                            Button(
                                onClick = {
                                    onDismissImportDialog()
                                    onConsultAi("阿米娅，我已经成功导入了新学期课表，请结合我的课表数据为我做一次全面的学情分析：包括课程负荷评估、每周节奏分析与自习备考作息建议！")
                                },
                                modifier = Modifier.fillMaxWidth(),
                                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                            ) {
                                Icon(Icons.Default.AutoAwesome, contentDescription = null, modifier = Modifier.size(16.dp), tint = Color.Black)
                                Spacer(Modifier.width(6.dp))
                                Text("立即让阿米娅分析课表 ✨", color = Color.Black, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            },
            confirmButton = {
                Button(onClick = {
                    if (jsonInput.isEmpty() || dateInput.isEmpty()) {
                        resultMsg = "请输入完整信息"
                        return@Button
                    }
                    val (success, msg) = ScheduleManager.importStrongZhi(jsonInput, dateInput)
                    resultMsg = msg
                    if (success) {
                        ScheduleManager.save(context)
                        refreshTrigger++
                    }
                }) {
                    Text("开始导入")
                }
            },
            dismissButton = {
                TextButton(onClick = onDismissImportDialog) { Text("关闭") }
            }
        )
    }

    if (showImageImportDialog || showInternalImageImportDialog) {
        ImageScheduleImportDialog(
            onDismiss = {
                onDismissImageImportDialog()
                showInternalImageImportDialog = false
            },
            onImportSuccess = { count ->
                refreshTrigger++
                onDismissImageImportDialog()
                showInternalImageImportDialog = false
                onConsultAi("阿米娅，我已经通过课表截图成功导入了 $count 门课程，请结合我的最新课表数据为我做一次全面的学情分析：包括课程负荷评估、每周节奏分析与自习备考作息建议！")
            },
            onConsultAi = onConsultAi
        )
    }

    if (showReminderDialog) {
        CourseReminderDialog(
            onDismiss = onDismissReminderDialog,
            onSave = { enabled, dismissEnabled, mins ->
                ScheduleManager.remindEnabled = enabled
                ScheduleManager.dismissRemindEnabled = dismissEnabled
                ScheduleManager.remindMinutes = mins
                ScheduleManager.save(context)
                Toast.makeText(context, "课表提醒设置已保存", Toast.LENGTH_SHORT).show()
                onDismissReminderDialog()
            }
        )
    }

    if (selectedCourseForDetail != null) {
        val course = selectedCourseForDetail!!
        CourseDetailDialog(
            course = course,
            color = colorMap[course.name] ?: MaterialTheme.colorScheme.primary,
            onDismiss = { selectedCourseForDetail = null },
            onEdit = {
                val c = selectedCourseForDetail!!
                selectedCourseForDetail = null
                editingCourse = c
                showCourseEditDialog = true
            },
            onDelete = {
                val c = selectedCourseForDetail!!
                selectedCourseForDetail = null
                deletingCourse = c
            }
        )
    }

    if (deletingCourse != null) {
        val target = deletingCourse!!
        DeleteConfirmationDialog(
            courseName = target.name,
            onDismiss = { deletingCourse = null },
            onConfirm = {
                ScheduleManager.deleteCourse(target.id, context)
                Toast.makeText(context, "已删除课程《${target.name}》", Toast.LENGTH_SHORT).show()
                deletingCourse = null
                refreshTrigger++
            }
        )
    }

    if (showCourseEditDialog) {
        CourseEditDialog(
            initialCourse = editingCourse,
            defaultWeekday = newCourseWeekday,
            defaultSection = newCourseSection,
            onDismiss = {
                showCourseEditDialog = false
                editingCourse = null
            },
            onSave = { savedCourse ->
                if (editingCourse != null) {
                    ScheduleManager.updateCourse(savedCourse, context)
                    Toast.makeText(context, "已更新课程《${savedCourse.name}》", Toast.LENGTH_SHORT).show()
                } else {
                    ScheduleManager.addCourse(savedCourse, context)
                    Toast.makeText(context, "已添加新课程《${savedCourse.name}》", Toast.LENGTH_SHORT).show()
                }
                showCourseEditDialog = false
                editingCourse = null
                refreshTrigger++
            }
        )
    }
}

private data class LayoutCourse(
    val course: Course,
    val slotIdx: Int,
    val totalSlots: Int
)

private fun layoutDayCourses(courses: List<Course>): List<LayoutCourse> {
    if (courses.isEmpty()) return emptyList()
    val sorted = courses.sortedWith(compareBy({ it.secStart }, { -(it.secEnd - it.secStart) }))
    val clusters = mutableListOf<MutableList<Course>>()
    for (c in sorted) {
        var placed = false
        for (cl in clusters) {
            if (cl.any { maxOf(c.secStart, it.secStart) <= minOf(c.secEnd, it.secEnd) }) {
                cl.add(c)
                placed = true
                break
            }
        }
        if (!placed) {
            clusters.add(mutableListOf(c))
        }
    }

    val result = mutableListOf<LayoutCourse>()
    for (cl in clusters) {
        val slots = mutableListOf<Int>()
        val cSlots = mutableMapOf<Course, Int>()
        for (c in cl) {
            var assigned = false
            for (sIdx in slots.indices) {
                if (slots[sIdx] < c.secStart) {
                    slots[sIdx] = c.secEnd
                    cSlots[c] = sIdx
                    assigned = true
                    break
                }
            }
            if (!assigned) {
                cSlots[c] = slots.size
                slots.add(c.secEnd)
            }
        }
        val total = slots.size
        for (c in cl) {
            result.add(LayoutCourse(c, cSlots[c] ?: 0, total))
        }
    }
    return result
}

@Composable
fun TimetableGrid(
    weekNo: Int,
    refreshTrigger: Int,
    colorMap: Map<String, Color>,
    onPrevWeek: () -> Unit,
    onNextWeek: () -> Unit,
    onSelectCourse: (Course) -> Unit,
    onAddCourseAt: (weekday: Int, section: Int) -> Unit
) {
    val isMondayFirst = ScheduleManager.weekStartDay == "monday"
    val weekDays = if (isMondayFirst) listOf("一", "二", "三", "四", "五", "六", "日") else listOf("日", "一", "二", "三", "四", "五", "六")
    val dayOrder = if (isMondayFirst) listOf(1, 2, 3, 4, 5, 6, 7) else listOf(7, 1, 2, 3, 4, 5, 6)

    val courses = remember(refreshTrigger, ScheduleManager.coursesVersion) {
        ScheduleManager.courses
    }

    var showTime by remember { mutableStateOf(false) }

    val realWeekNo = ScheduleManager.getWeekNo() ?: 1
    val cal = Calendar.getInstance()
    val todayIdx = cal.get(Calendar.DAY_OF_WEEK)
    val currentIsoWeekday = if (todayIdx == Calendar.SUNDAY) 7 else todayIdx - 1
    val isCurrentWeek = (weekNo == realWeekNo)
    val currentMins = cal.get(Calendar.HOUR_OF_DAY) * 60 + cal.get(Calendar.MINUTE)

    val dates = remember(weekNo, refreshTrigger, ScheduleManager.termStart, ScheduleManager.weekStartDay) {
        val today = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val currentDow = today.get(Calendar.DAY_OF_WEEK) // SUNDAY=1, MONDAY=2, ... SATURDAY=7
        val offsetToStart = if (isMondayFirst) {
            if (currentDow == Calendar.SUNDAY) 6 else currentDow - Calendar.MONDAY
        } else {
            currentDow - Calendar.SUNDAY
        }
        val curWeekStart = (today.clone() as Calendar).apply {
            add(Calendar.DAY_OF_YEAR, -offsetToStart)
        }
        val curWeekNo = ScheduleManager.getWeekNo() ?: 1
        val weekDiff = weekNo - curWeekNo
        val targetStart = (curWeekStart.clone() as Calendar).apply {
            add(Calendar.DAY_OF_YEAR, weekDiff * 7)
        }
        val result = mutableListOf<String>()
        val sdf = java.text.SimpleDateFormat("M.d", java.util.Locale.getDefault())
        for (i in 0..6) {
            result.add(sdf.format(targetStart.time))
            targetStart.add(Calendar.DAY_OF_YEAR, 1)
        }
        result
    }

    // Gesture state
    var dragAccumulator by remember { mutableFloatStateOf(0f) }

    Column(modifier = Modifier.fillMaxSize()) {
        Row(modifier = Modifier.fillMaxWidth().padding(start = 38.dp, end = 8.dp)) {
            weekDays.forEachIndexed { idx, it ->
                val isToday = isCurrentWeek && currentIsoWeekday == dayOrder[idx]
                Column(
                    modifier = Modifier.weight(1f)
                        .clip(RoundedCornerShape(6.dp))
                        .background(if (isToday) MaterialTheme.colorScheme.primary.copy(alpha=0.25f) else Color.Transparent)
                        .then(if (isToday) Modifier.border(1.dp, MaterialTheme.colorScheme.primary.copy(alpha=0.6f), RoundedCornerShape(6.dp)) else Modifier)
                        .padding(vertical = 2.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = it,
                        color = if (isToday) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
                        fontSize = 12.sp,
                        fontWeight = if (isToday) FontWeight.Bold else FontWeight.Normal
                    )
                    if (dates[idx].isNotEmpty()) {
                        Text(
                            text = dates[idx],
                            color = if (isToday) MaterialTheme.colorScheme.primary else Color.Gray,
                            fontSize = 9.sp,
                            fontWeight = if (isToday) FontWeight.Bold else FontWeight.Normal
                        )
                    }
                }
            }
        }
        Spacer(Modifier.height(4.dp))
        BoxWithConstraints(modifier = Modifier.weight(1f).fillMaxWidth().padding(end = 8.dp, bottom = 16.dp)
            .pointerInput(Unit) {
                detectHorizontalDragGestures(
                    onDragEnd = { dragAccumulator = 0f },
                    onDragCancel = { dragAccumulator = 0f }
                ) { change, dragAmount ->
                    change.consume()
                    dragAccumulator += dragAmount
                    if (dragAccumulator > 150f) {
                        onPrevWeek()
                        dragAccumulator = 0f
                    } else if (dragAccumulator < -150f) {
                        onNextWeek()
                        dragAccumulator = 0f
                    }
                }
            }
        ) {
            val isConstrained = maxHeight < 560.dp
            val rowH = if (isConstrained) 46.dp else maxHeight / 13
            val totalGridH = rowH * 13
            val gridScrollState = rememberScrollState()

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(if (isConstrained) totalGridH else maxHeight)
                    .then(if (isConstrained) Modifier.verticalScroll(gridScrollState) else Modifier)
            ) {
                // Background grid lines and row numbers
                Column(modifier = Modifier.fillMaxSize()) {
                    for (i in 1..13) {
                        val rawTimeInfo = ScheduleManager.sections[i.toString()] ?: ""
                        var isCurrentSlot = false
                        var isTimeNow = false
                        if (rawTimeInfo.contains(":")) {
                            try {
                                val timePart = rawTimeInfo.split("\n").first().split("-").first().trim()
                                val parts = timePart.split(":")
                                val startMins = parts[0].toInt() * 60 + parts[1].toInt()
                                val nextStartMins = if (i < 13) {
                                    val nextTime = ScheduleManager.sections[(i + 1).toString()] ?: ""
                                    if (nextTime.contains(":")) {
                                        val np = nextTime.split("\n").first().split("-").first().trim().split(":")
                                        np[0].toInt() * 60 + np[1].toInt()
                                    } else startMins + 45
                                } else startMins + 45

                                if (currentMins in startMins until nextStartMins) {
                                    isTimeNow = true
                                    if (isCurrentWeek) {
                                        isCurrentSlot = true
                                    }
                                }
                            } catch(e: Exception){}
                        }

                        Box(modifier = Modifier.fillMaxWidth().height(rowH).background(if (isCurrentSlot) MaterialTheme.colorScheme.primary.copy(alpha=0.15f) else Color.Transparent)) {
                            Box(
                                modifier = Modifier
                                    .width(38.dp)
                                    .fillMaxHeight()
                                    .clickable { showTime = !showTime }
                                    .background(
                                        if (isCurrentSlot) MaterialTheme.colorScheme.primary.copy(alpha=0.35f)
                                        else if (isTimeNow) MaterialTheme.colorScheme.primary.copy(alpha=0.15f)
                                        else Color.Transparent
                                    )
                                    .align(Alignment.CenterStart),
                                contentAlignment = Alignment.Center
                            ) {
                                val rawTimeText = ScheduleManager.sections[i.toString()] ?: "$i"
                                val displayTime = if (!showTime) i.toString() else {
                                    if (rawTimeText.contains("-") || rawTimeText.contains("\n")) {
                                        rawTimeText.replace("-", "\n")
                                    } else if (rawTimeText.contains(":")) {
                                        try {
                                            val parts = rawTimeText.split(":")
                                            val h = parts[0].toInt()
                                            val m = parts[1].toInt()
                                            val endM = h * 60 + m + 45
                                            val eH = endM / 60
                                            val eM = endM % 60
                                            "$rawTimeText\n${String.format(Locale.getDefault(), "%02d:%02d", eH, eM)}"
                                        } catch(e: Exception) { rawTimeText }
                                    } else rawTimeText
                                }
                                Text(
                                    text = displayTime,
                                    color = if (isCurrentSlot || isTimeNow) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onBackground.copy(alpha = 0.65f),
                                    fontSize = if (showTime) 9.sp else 11.sp,
                                    lineHeight = 11.sp,
                                    fontWeight = if (isCurrentSlot || isTimeNow) FontWeight.Bold else FontWeight.Normal,
                                    textAlign = TextAlign.Center
                                )
                            }
                            Box(modifier = Modifier.fillMaxSize().padding(start = 38.dp)) {
                                Spacer(modifier = Modifier.fillMaxWidth().height(1.dp).background(MaterialTheme.colorScheme.onSurface.copy(alpha = 0.12f)).align(Alignment.TopCenter))
                            }
                        }
                    }
                }
                // Courses overlay & Empty clickable slots
                Row(modifier = Modifier.matchParentSize().padding(start = 38.dp)) {
                    for (wd in dayOrder) {
                        Box(modifier = Modifier.weight(1f).fillMaxHeight()) {
                            val dayCourses = ScheduleManager.getCoursesOn(wd, weekNo)
                            val layoutCourses = remember(dayCourses) { layoutDayCourses(dayCourses) }

                            // 1. Clickable empty slots to quickly add a course
                            for (sec in 1..13) {
                                val isOccupied = dayCourses.any { sec in it.secStart..it.secEnd }
                                if (!isOccupied) {
                                    Box(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .offset(y = rowH * (sec - 1))
                                            .height(rowH)
                                            .clickable { onAddCourseAt(wd, sec) }
                                    )
                                }
                            }

                            // 2. Render active courses with collision sub-columns
                            for (lc in layoutCourses) {
                                CourseBlock(
                                    course = lc.course,
                                    color = colorMap[lc.course.name] ?: Color.Gray,
                                    rowH = rowH,
                                    slotIdx = lc.slotIdx,
                                    totalSlots = lc.totalSlots,
                                    onClick = { onSelectCourse(lc.course) }
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun CourseBlock(
    course: Course,
    color: Color,
    rowH: androidx.compose.ui.unit.Dp,
    slotIdx: Int = 0,
    totalSlots: Int = 1,
    onClick: () -> Unit
) {
    val topOff = rowH * (course.secStart - 1)
    val height = rowH * (course.secEnd - course.secStart + 1)
    val isAiAdded = course.note.contains("AI")

    BoxWithConstraints(modifier = Modifier.fillMaxSize()) {
        val totalW = maxWidth
        val subW = totalW / totalSlots
        val xOff = subW * slotIdx

        Box(
            modifier = Modifier
                .offset(x = xOff, y = topOff)
                .size(width = subW, height = height)
                .padding(1.dp)
                .clip(RoundedCornerShape(6.dp))
                .background(color)
                .clickable(onClick = onClick)
                .padding(2.dp)
        ) {
            Column(modifier = Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally) {
                if (course.customTime.isNotBlank()) {
                    val timeDisplay = if (height > rowH * 1.5f && course.customTime.contains("-")) {
                        val parts = course.customTime.split("-")
                        "📌${parts[0]}\n~${parts[1]}"
                    } else {
                        "📌${course.customTime}"
                    }
                    Text(
                        text = timeDisplay,
                        color = Color(0xFFFFEB3B),
                        fontSize = if (totalSlots > 1) 6.5.sp else 7.5.sp,
                        fontWeight = FontWeight.ExtraBold,
                        textAlign = TextAlign.Center,
                        lineHeight = 8.sp,
                        maxLines = 2
                    )
                }
                val displayName = if (isAiAdded) "✨ ${course.name}" else course.name
                Text(
                    displayName,
                    color = Color.White,
                    fontSize = if (totalSlots > 1) 8.5.sp else 10.sp,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center,
                    maxLines = 3,
                    overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                )
                if (course.room.isNotEmpty() && height > rowH * 1.5f) {
                    Spacer(Modifier.height(1.dp))
                    Text(
                        "@${course.room}",
                        color = Color(0xFFEEEEEE),
                        fontSize = if (totalSlots > 1) 7.5.sp else 9.sp,
                        textAlign = TextAlign.Center,
                        maxLines = 2
                    )
                }
            }
        }
    }
}

@Composable
fun CourseDetailDialog(
    course: Course,
    color: Color,
    onDismiss: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    val weekdayNames = arrayOf("", "周一", "周二", "周三", "周四", "周五", "周六", "周日")
    val weekdayStr = weekdayNames.getOrElse(course.weekday) { "周${course.weekday}" }
    val parityStr = when(course.parity) {
        "odd" -> "仅单周"
        "even" -> "仅双周"
        else -> "全部周"
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = MaterialTheme.colorScheme.surface,
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(modifier = Modifier.size(14.dp).clip(RoundedCornerShape(3.dp)).background(color))
                Spacer(Modifier.width(8.dp))
                Text("课程详情", color = MaterialTheme.colorScheme.onSurface, fontWeight = FontWeight.Bold, fontSize = 18.sp)
            }
        },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                Text(course.name, color = color, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                Spacer(Modifier.height(12.dp))

                if (course.customTime.isNotBlank()) {
                    DetailItem(icon = Icons.Default.Schedule, label = "活动时间", value = "📌 ${course.customTime} (准时提醒)")
                    DetailItem(icon = Icons.Default.AccessTime, label = "吸附节次", value = "$weekdayStr 第 ${course.secStart}-${course.secEnd} 节")
                } else {
                    DetailItem(icon = Icons.Default.AccessTime, label = "时间", value = "$weekdayStr 第 ${course.secStart}-${course.secEnd} 节")
                }
                DetailItem(icon = Icons.Default.DateRange, label = "周次", value = "第 ${course.weekStart}-${course.weekEnd} 周 ($parityStr)")
                if (course.room.isNotEmpty()) {
                    DetailItem(icon = Icons.Default.LocationOn, label = "教室", value = course.room)
                }
                if (course.teacher.isNotEmpty()) {
                    DetailItem(icon = Icons.Default.Person, label = "教师", value = course.teacher)
                }
                if (course.campus.isNotEmpty()) {
                    DetailItem(icon = Icons.Default.School, label = "校区", value = course.campus)
                }
                if (course.note.isNotEmpty()) {
                    DetailItem(
                        icon = if (course.note.contains("AI")) Icons.Default.AutoAwesome else Icons.Default.Notes,
                        label = if (course.note.contains("AI")) "来源" else "备注",
                        value = course.note
                    )
                }
            }
        },
        confirmButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(
                    onClick = onDelete,
                    colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)
                ) {
                    Icon(Icons.Default.Delete, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("删除")
                }
                Button(
                    onClick = onEdit,
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                ) {
                    Icon(Icons.Default.Edit, contentDescription = null, modifier = Modifier.size(16.dp), tint = Color.Black)
                    Spacer(Modifier.width(4.dp))
                    Text("编辑", color = Color.Black, fontWeight = FontWeight.Bold)
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("关闭") }
        }
    )
}

@Composable
private fun DetailItem(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(icon, contentDescription = null, modifier = Modifier.size(16.dp), tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
        Spacer(Modifier.width(8.dp))
        Text("$label: ", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
        Text(value, fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurface, fontWeight = FontWeight.Medium)
    }
}

@Composable
fun DeleteConfirmationDialog(
    courseName: String,
    onDismiss: () -> Unit,
    onConfirm: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Warning, contentDescription = null, tint = MaterialTheme.colorScheme.error)
                Spacer(Modifier.width(8.dp))
                Text("删除课程确认", fontWeight = FontWeight.Bold, fontSize = 18.sp)
            }
        },
        text = {
            Text("确定要删除课程《$courseName》吗？\n删除后无法撤销，如需重新添加需手动录入。", fontSize = 14.sp)
        },
        confirmButton = {
            Button(
                onClick = onConfirm,
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
            ) {
                Text("确认删除", color = Color.White, fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        }
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CourseEditDialog(
    initialCourse: Course? = null,
    defaultWeekday: Int = 1,
    defaultSection: Int = 1,
    onDismiss: () -> Unit,
    onSave: (Course) -> Unit
) {
    var name by remember { mutableStateOf(initialCourse?.name ?: "") }
    var weekday by remember { mutableIntStateOf(initialCourse?.weekday ?: defaultWeekday) }
    var secStart by remember { mutableIntStateOf(initialCourse?.secStart ?: defaultSection) }
    var secEnd by remember { mutableIntStateOf(initialCourse?.secEnd ?: (defaultSection + 1).coerceAtMost(13)) }
    var weekStart by remember { mutableIntStateOf(initialCourse?.weekStart ?: 1) }
    var weekEnd by remember { mutableIntStateOf(initialCourse?.weekEnd ?: 16) }
    var parity by remember { mutableStateOf(initialCourse?.parity ?: "all") }
    var room by remember { mutableStateOf(initialCourse?.room ?: "") }
    var teacher by remember { mutableStateOf(initialCourse?.teacher ?: "") }
    var note by remember { mutableStateOf(initialCourse?.note ?: "") }
    var campus by remember { mutableStateOf(initialCourse?.campus ?: "") }
    var customTime by remember { mutableStateOf(initialCourse?.customTime ?: "") }

    var hasError by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf("") }

    val isEditing = (initialCourse != null)
    val weekdayList = listOf(
        Pair(7, "日"), Pair(1, "一"), Pair(2, "二"), Pair(3, "三"),
        Pair(4, "四"), Pair(5, "五"), Pair(6, "六")
    )
    val parityOptions = listOf(
        Pair("all", "全部周"),
        Pair("odd", "仅单周"),
        Pair("even", "仅双周")
    )

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = MaterialTheme.colorScheme.surface,
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = if (isEditing) Icons.Default.Edit else Icons.Default.AddCircleOutline,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(24.dp)
                )
                Spacer(Modifier.width(8.dp))
                Text(if (isEditing) "编辑课程" else "手动添加课程", fontWeight = FontWeight.Bold, fontSize = 18.sp)
            }
        },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 480.dp)
                    .verticalScroll(rememberScrollState())
            ) {
                // 1. 课程名称
                OutlinedTextField(
                    value = name,
                    onValueChange = {
                        name = it
                        if (hasError && it.isNotBlank()) hasError = false
                    },
                    label = { Text("课程名称 *") },
                    placeholder = { Text("如：高等数学、自习、大学物理") },
                    isError = hasError && name.isBlank(),
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
                if (hasError && name.isBlank()) {
                    Text("课程名称不能为空", color = MaterialTheme.colorScheme.error, fontSize = 11.sp, modifier = Modifier.padding(start = 4.dp, top = 2.dp))
                }

                Spacer(Modifier.height(12.dp))

                // 2. 上课星期
                Text("上课星期", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f))
                Spacer(Modifier.height(6.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    weekdayList.forEach { (wInt, wName) ->
                        val isSelected = (weekday == wInt)
                        Box(
                            modifier = Modifier
                                .weight(1f)
                                .padding(horizontal = 2.dp)
                                .clip(RoundedCornerShape(6.dp))
                                .background(if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f))
                                .clickable { weekday = wInt }
                                .padding(vertical = 6.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = wName,
                                fontSize = 12.sp,
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                color = if (isSelected) Color.Black else MaterialTheme.colorScheme.onSurface
                            )
                        }
                    }
                }

                Spacer(Modifier.height(12.dp))

                // 3. 节次范围 (开始节 - 结束节)
                Text("节次范围", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f))
                Spacer(Modifier.height(6.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    NumberDropdownSelector(
                        label = "第",
                        suffix = "节",
                        currentValue = secStart,
                        range = 1..13,
                        modifier = Modifier.weight(1f),
                        onValueChange = {
                            secStart = it
                            if (secEnd < it) secEnd = it
                        }
                    )
                    Text("至", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))
                    NumberDropdownSelector(
                        label = "第",
                        suffix = "节",
                        currentValue = secEnd,
                        range = secStart..13,
                        modifier = Modifier.weight(1f),
                        onValueChange = { secEnd = it }
                    )
                }

                Spacer(Modifier.height(12.dp))

                // 4. 周次范围 (起始周 - 结束周)
                Text("周次范围", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f))
                Spacer(Modifier.height(6.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    NumberDropdownSelector(
                        label = "第",
                        suffix = "周",
                        currentValue = weekStart,
                        range = 1..30,
                        modifier = Modifier.weight(1f),
                        onValueChange = {
                            weekStart = it
                            if (weekEnd < it) weekEnd = it
                        }
                    )
                    Text("至", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))
                    NumberDropdownSelector(
                        label = "第",
                        suffix = "周",
                        currentValue = weekEnd,
                        range = weekStart..30,
                        modifier = Modifier.weight(1f),
                        onValueChange = { weekEnd = it }
                    )
                }

                Spacer(Modifier.height(10.dp))

                // 5. 单双周
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    parityOptions.forEach { (pKey, pLabel) ->
                        val isSelected = (parity == pKey)
                        Box(
                            modifier = Modifier
                                .weight(1f)
                                .clip(RoundedCornerShape(8.dp))
                                .background(if (isSelected) MaterialTheme.colorScheme.primary.copy(alpha = 0.25f) else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f))
                                .border(
                                    width = if (isSelected) 1.5.dp else 0.dp,
                                    color = if (isSelected) MaterialTheme.colorScheme.primary else Color.Transparent,
                                    shape = RoundedCornerShape(8.dp)
                                )
                                .clickable { parity = pKey }
                                .padding(vertical = 7.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = pLabel,
                                fontSize = 12.sp,
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                color = if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface
                            )
                        }
                    }
                }

                Spacer(Modifier.height(12.dp))

                // 6. 上课教室 (选填)
                OutlinedTextField(
                    value = room,
                    onValueChange = { room = it },
                    label = { Text("上课教室 (选填)") },
                    placeholder = { Text("如：教三 201、实验楼 402") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                Spacer(Modifier.height(8.dp))

                // 7. 任课教师 (选填)
                OutlinedTextField(
                    value = teacher,
                    onValueChange = { teacher = it },
                    label = { Text("任课教师 (选填)") },
                    placeholder = { Text("如：张教授") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                Spacer(Modifier.height(8.dp))

                // 8. 备注说明 (选填)
                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    label = { Text("备注说明 (选填)") },
                    placeholder = { Text("如：大作业、需带电脑、自习") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                Spacer(Modifier.height(8.dp))

                // 9. 真实活动时间 (选填)
                OutlinedTextField(
                    value = customTime,
                    onValueChange = { customTime = it },
                    label = { Text("真实活动时间 (选填)") },
                    placeholder = { Text("如：14:15-15:30（提醒将严格按此时刻推送）") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                if (errorMessage.isNotEmpty()) {
                    Spacer(Modifier.height(6.dp))
                    Text(errorMessage, color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    if (name.isBlank()) {
                        hasError = true
                        errorMessage = "请输入课程名称"
                        return@Button
                    }
                    if (secStart > secEnd) {
                        errorMessage = "开始节次不能大于结束节次"
                        return@Button
                    }
                    if (weekStart > weekEnd) {
                        errorMessage = "起始周次不能大于结束周次"
                        return@Button
                    }

                    val finalCourse = (initialCourse ?: Course(
                        name = name.trim(),
                        weekday = weekday,
                        secStart = secStart,
                        secEnd = secEnd,
                        weekStart = weekStart,
                        weekEnd = weekEnd,
                        parity = parity,
                        room = room.trim(),
                        teacher = teacher.trim(),
                        campus = campus.trim(),
                        note = note.trim(),
                        customTime = customTime.trim()
                    )).copy(
                        name = name.trim(),
                        weekday = weekday,
                        secStart = secStart,
                        secEnd = secEnd,
                        weekStart = weekStart,
                        weekEnd = weekEnd,
                        parity = parity,
                        room = room.trim(),
                        teacher = teacher.trim(),
                        campus = campus.trim(),
                        note = note.trim(),
                        customTime = customTime.trim()
                    )

                    onSave(finalCourse)
                },
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
            ) {
                Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(16.dp), tint = Color.Black)
                Spacer(Modifier.width(4.dp))
                Text("保存", color = Color.Black, fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        }
    )
}

@Composable
fun NumberDropdownSelector(
    label: String,
    suffix: String,
    currentValue: Int,
    range: IntRange,
    modifier: Modifier = Modifier,
    onValueChange: (Int) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }

    Box(modifier = modifier) {
        OutlinedCard(
            modifier = Modifier.fillMaxWidth().clickable { expanded = true },
            shape = RoundedCornerShape(8.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "$label $currentValue $suffix",
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Icon(
                    Icons.Default.ArrowDropDown,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                    tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                )
            }
        }

        DropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
            modifier = Modifier.heightIn(max = 220.dp)
        ) {
            range.forEach { num ->
                DropdownMenuItem(
                    text = {
                        Text(
                            "$label $num $suffix",
                            fontWeight = if (num == currentValue) FontWeight.Bold else FontWeight.Normal,
                            color = if (num == currentValue) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface
                        )
                    },
                    onClick = {
                        onValueChange(num)
                        expanded = false
                    }
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CourseReminderDialog(
    onDismiss: () -> Unit,
    onSave: (Boolean, Boolean, Int) -> Unit
) {
    val context = LocalContext.current
    var remindEnabled by remember { mutableStateOf(ScheduleManager.remindEnabled) }
    var dismissRemindEnabled by remember { mutableStateOf(ScheduleManager.dismissRemindEnabled) }
    var remindMinutes by remember { mutableIntStateOf(ScheduleManager.remindMinutes) }
    val minuteOptions = listOf(10, 20, 30)
    var showCustomReminderDialog by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    Icons.Default.NotificationsActive,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(24.dp)
                )
                Spacer(Modifier.width(8.dp))
                Text("课表提醒与作息关怀", fontSize = 18.sp, fontWeight = FontWeight.Bold)
            }
        },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                Text(
                    text = "阿米娅会在上课前为您推送常驻高优先级通知（带教室、授课教师及准备建议），下课时关怀午餐/晚餐与换教室防遗忘。",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    lineHeight = 16.sp
                )

                HorizontalDivider()

                // 上课提醒开关
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text("上课前智能提醒", fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                        Text("提前推送通知并提醒带好水杯课本", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Switch(
                        checked = remindEnabled,
                        onCheckedChange = { remindEnabled = it }
                    )
                }

                // 提前时间选择（等宽等高，统一规格）
                if (remindEnabled) {
                    Column {
                        Text("提前提醒时间：", fontSize = 12.sp, fontWeight = FontWeight.Medium)
                        Spacer(Modifier.height(6.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(6.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            val isCustomSelected = !minuteOptions.contains(remindMinutes)

                            minuteOptions.forEach { mins ->
                                val isSelected = (remindMinutes == mins)
                                Box(
                                    modifier = Modifier
                                        .weight(1f)
                                        .height(34.dp)
                                        .clip(RoundedCornerShape(10.dp))
                                        .background(
                                            if (isSelected) MaterialTheme.colorScheme.primary.copy(alpha = 0.22f)
                                            else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f)
                                        )
                                        .then(
                                            if (isSelected) Modifier.border(1.dp, MaterialTheme.colorScheme.primary, RoundedCornerShape(10.dp))
                                            else Modifier
                                        )
                                        .clickable { remindMinutes = mins },
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = "${mins}m",
                                        fontSize = 12.sp,
                                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                        color = if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
                                        maxLines = 1
                                    )
                                }
                            }

                            // 自定义提前时长入口（规格与其他按钮完全一致）
                            Box(
                                modifier = Modifier
                                    .weight(1f)
                                    .height(34.dp)
                                    .clip(RoundedCornerShape(10.dp))
                                    .background(
                                        if (isCustomSelected) MaterialTheme.colorScheme.primary.copy(alpha = 0.22f)
                                        else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f)
                                    )
                                    .then(
                                        if (isCustomSelected) Modifier.border(1.dp, MaterialTheme.colorScheme.primary, RoundedCornerShape(10.dp))
                                        else Modifier
                                    )
                                    .clickable { showCustomReminderDialog = true },
                                contentAlignment = Alignment.Center
                            ) {
                                Text(
                                    text = if (isCustomSelected) "${remindMinutes}m" else "自定义",
                                    fontSize = 11.sp,
                                    fontWeight = if (isCustomSelected) FontWeight.Bold else FontWeight.Normal,
                                    color = if (isCustomSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
                                    maxLines = 1
                                )
                            }
                        }
                    }
                }

                HorizontalDivider()

                // 下课/放学关怀开关
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text("下课换教室/就餐关怀", fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                        Text("下课时提示下一节课位置或就餐自习", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Switch(
                        checked = dismissRemindEnabled,
                        onCheckedChange = { dismissRemindEnabled = it }
                    )
                }

                HorizontalDivider()

                // 测试按钮
                Text("通知效果测试：", fontSize = 12.sp, fontWeight = FontWeight.Medium)
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    OutlinedButton(
                        onClick = {
                            AppBackgroundService.sendTestReminder(context, isDismissal = false)
                            Toast.makeText(context, "已发送上课测试通知，请查看通知栏", Toast.LENGTH_SHORT).show()
                        },
                        modifier = Modifier.weight(1f),
                        contentPadding = PaddingValues(vertical = 4.dp, horizontal = 6.dp)
                    ) {
                        Text("测试上课提醒", fontSize = 11.sp)
                    }
                    OutlinedButton(
                        onClick = {
                            AppBackgroundService.sendTestReminder(context, isDismissal = true)
                            Toast.makeText(context, "已发送下课测试通知，请查看通知栏", Toast.LENGTH_SHORT).show()
                        },
                        modifier = Modifier.weight(1f),
                        contentPadding = PaddingValues(vertical = 4.dp, horizontal = 6.dp)
                    ) {
                        Text("测试下课关怀", fontSize = 11.sp)
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = { onSave(remindEnabled, dismissRemindEnabled, remindMinutes) }
            ) {
                Text("保存设置")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("取消")
            }
        }
    )

    if (showCustomReminderDialog) {
        var tempMinutes by remember { mutableIntStateOf(remindMinutes) }
        val minLimit = 5
        val maxLimit = 60

        AlertDialog(
            onDismissRequest = { showCustomReminderDialog = false },
            containerColor = MaterialTheme.colorScheme.surface,
            title = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Default.Tune,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = "自定义提前提醒时间",
                        fontWeight = FontWeight.Bold,
                        fontSize = 17.sp,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
            },
            text = {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = "提前 $tempMinutes 分钟",
                        fontSize = 28.sp,
                        fontWeight = FontWeight.ExtraBold,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Spacer(Modifier.height(14.dp))

                    Slider(
                        value = tempMinutes.toFloat(),
                        onValueChange = { tempMinutes = it.toInt().coerceIn(minLimit, maxLimit) },
                        valueRange = minLimit.toFloat()..maxLimit.toFloat(),
                        colors = SliderDefaults.colors(
                            thumbColor = MaterialTheme.colorScheme.primary,
                            activeTrackColor = MaterialTheme.colorScheme.primary
                        ),
                        modifier = Modifier.fillMaxWidth()
                    )

                    Spacer(Modifier.height(6.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceEvenly
                    ) {
                        OutlinedButton(
                            onClick = { tempMinutes = (tempMinutes - 5).coerceAtLeast(minLimit) },
                            contentPadding = PaddingValues(horizontal = 8.dp, vertical = 2.dp),
                            modifier = Modifier.widthIn(min = 44.dp)
                        ) {
                            Text("-5", fontSize = 12.sp)
                        }
                        OutlinedButton(
                            onClick = { tempMinutes = (tempMinutes - 1).coerceAtLeast(minLimit) },
                            contentPadding = PaddingValues(horizontal = 8.dp, vertical = 2.dp),
                            modifier = Modifier.widthIn(min = 44.dp)
                        ) {
                            Text("-1", fontSize = 12.sp)
                        }
                        OutlinedButton(
                            onClick = { tempMinutes = (tempMinutes + 1).coerceAtMost(maxLimit) },
                            contentPadding = PaddingValues(horizontal = 8.dp, vertical = 2.dp),
                            modifier = Modifier.widthIn(min = 44.dp)
                        ) {
                            Text("+1", fontSize = 12.sp)
                        }
                        OutlinedButton(
                            onClick = { tempMinutes = (tempMinutes + 5).coerceAtMost(maxLimit) },
                            contentPadding = PaddingValues(horizontal = 8.dp, vertical = 2.dp),
                            modifier = Modifier.widthIn(min = 44.dp)
                        ) {
                            Text("+5", fontSize = 12.sp)
                        }
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        remindMinutes = tempMinutes
                        showCustomReminderDialog = false
                    }
                ) {
                    Text("确定", color = Color.Black)
                }
            },
            dismissButton = {
                TextButton(onClick = { showCustomReminderDialog = false }) {
                    Text("取消", color = Color.Gray)
                }
            }
        )
    }
}
