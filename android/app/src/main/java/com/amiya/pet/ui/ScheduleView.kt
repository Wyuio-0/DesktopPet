package com.amiya.pet.ui

import androidx.compose.foundation.background
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
    onConsultAi: (String) -> Unit = {}
) {
    val context = LocalContext.current
    var currentWeek by remember { mutableIntStateOf(ScheduleManager.getWeekNo() ?: 1) }
    var showImportDialog by remember { mutableStateOf(false) }
    var refreshTrigger by remember { mutableStateOf(0) }
    
    LaunchedEffect(refreshTrigger) {
        ScheduleManager.load(context)
        currentWeek = ScheduleManager.getWeekNo() ?: 1
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { if (currentWeek > 1) currentWeek-- }) {
                    Icon(Icons.Default.ChevronLeft, "上一周", tint = MaterialTheme.colorScheme.onBackground)
                }
                Text("第 $currentWeek 周", color = MaterialTheme.colorScheme.onBackground, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                IconButton(onClick = { currentWeek++ }) {
                    Icon(Icons.Default.ChevronRight, "下一周", tint = MaterialTheme.colorScheme.onBackground)
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (ScheduleManager.courses.isNotEmpty()) {
                    OutlinedButton(
                        onClick = {
                            onConsultAi("阿米娅，请结合我导入的课表数据，全面分析我的学习情况与课程负荷，并给出科学的学习与作息规划建议。")
                        },
                        contentPadding = PaddingValues(horizontal = 10.dp, vertical = 6.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.AutoAwesome,
                            contentDescription = null,
                            modifier = Modifier.size(15.dp),
                            tint = MaterialTheme.colorScheme.primary
                        )
                        Spacer(Modifier.width(4.dp))
                        Text(
                            text = "AI 学情分析",
                            fontSize = 13.sp,
                            color = MaterialTheme.colorScheme.primary,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Spacer(Modifier.width(8.dp))
                }
                Button(
                    onClick = { showImportDialog = true },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                ) {
                    Icon(Icons.Default.Download, contentDescription = null, modifier = Modifier.size(16.dp), tint = Color.Black)
                    Spacer(Modifier.width(4.dp))
                    Text("导入课表", color = Color.Black, fontWeight = FontWeight.Bold)
                }
            }
        }

        if (ScheduleManager.courses.isEmpty()) {
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
                        text = "暂无课表数据，请点击右上角「导入课表」",
                        color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.7f),
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Medium
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        text = "💡 导入后课表将自动同步给阿米娅，可一键获取全套学情负荷分析与自习作息建议",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.85f),
                        textAlign = TextAlign.Center
                    )
                }
            }
        } else {
            TimetableGrid(currentWeek, refreshTrigger, { if (currentWeek > 1) currentWeek-- }, { currentWeek++ })
        }
    }
    
    if (showImportDialog) {
        var jsonInput by remember { mutableStateOf("") }
        var dateInput by remember { mutableStateOf(SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())) }
        var resultMsg by remember { mutableStateOf("") }
        
        AlertDialog(
            onDismissRequest = { showImportDialog = false },
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
                                    showImportDialog = false
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
                TextButton(onClick = { showImportDialog = false }) { Text("关闭") }
            }
        )
    }
}

@Composable
fun TimetableGrid(weekNo: Int, refreshTrigger: Int, onPrevWeek: () -> Unit, onNextWeek: () -> Unit) {
    val weekDays = listOf("日", "一", "二", "三", "四", "五", "六")
    val courses = ScheduleManager.courses
    val colorMap = remember(refreshTrigger) {
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


    var showTime by remember { mutableStateOf(false) }

    val realWeekNo = ScheduleManager.getWeekNo() ?: 1
    val cal = Calendar.getInstance()
    val todayIdx = cal.get(Calendar.DAY_OF_WEEK)
    val currentIsoWeekday = if (todayIdx == Calendar.SUNDAY) 7 else todayIdx - 1
    val isCurrentWeek = (weekNo == realWeekNo)
    val currentMins = cal.get(Calendar.HOUR_OF_DAY) * 60 + cal.get(Calendar.MINUTE)
    val dayOrder = listOf(7, 1, 2, 3, 4, 5, 6)

    val dates = remember(weekNo, refreshTrigger) {
        val start = ScheduleManager.termStart
        if (start != null) {
            val cal = Calendar.getInstance()
            cal.time = start
            cal.add(Calendar.DAY_OF_YEAR, (weekNo - 1) * 7)
            val dayOfWeek = cal.get(Calendar.DAY_OF_WEEK)
            cal.add(Calendar.DAY_OF_YEAR, Calendar.SUNDAY - dayOfWeek)
            
            val result = mutableListOf<String>()
            for (i in 0..6) {
                result.add(java.text.SimpleDateFormat("M.d", java.util.Locale.getDefault()).format(cal.time))
                cal.add(Calendar.DAY_OF_YEAR, 1)
            }
            result
        } else {
            List(7) { "" }
        }
    }

    // Gesture state
    var dragAccumulator by remember { mutableFloatStateOf(0f) }


    Column(modifier = Modifier.fillMaxSize()) {
        Row(modifier = Modifier.fillMaxWidth().padding(start = 38.dp, end = 8.dp)) {
            weekDays.forEachIndexed { idx, it ->
                val isToday = isCurrentWeek && currentIsoWeekday == dayOrder[idx]
                Column(
                    modifier = Modifier.weight(1f)
                        .clip(RoundedCornerShape(4.dp))
                        .background(if (isToday) MaterialTheme.colorScheme.primary.copy(alpha=0.3f) else Color.Transparent)
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
            val rowH = maxHeight / 13
            // Background grid lines and row numbers
            Column(modifier = Modifier.fillMaxSize()) {
                for (i in 1..13) {
                    val rawTimeInfo = ScheduleManager.sections[i.toString()] ?: ""
                    var isCurrentSlot = false
                    if (isCurrentWeek && rawTimeInfo.contains(":")) {
                        try {
                            val timePart = rawTimeInfo.split("\n").first().split("-").first().trim()
                            val parts = timePart.split(":")
                            val startMins = parts[0].toInt() * 60 + parts[1].toInt()
                            if (currentMins in startMins..(startMins + 45)) {
                                isCurrentSlot = true
                            }
                        } catch(e: Exception){}
                    }

                    Box(modifier = Modifier.fillMaxWidth().height(rowH).background(if (isCurrentSlot) MaterialTheme.colorScheme.primary.copy(alpha=0.15f) else Color.Transparent)) {
                        Box(
                            modifier = Modifier
                                .width(38.dp)
                                .fillMaxHeight()
                                .clickable { showTime = !showTime }
                                .background(if (isCurrentSlot) MaterialTheme.colorScheme.primary.copy(alpha=0.3f) else Color.Transparent)
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
                                color = if (isCurrentSlot) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onBackground.copy(alpha = 0.65f),
                                fontSize = if (showTime) 9.sp else 11.sp,
                                lineHeight = 11.sp,
                                fontWeight = if (isCurrentSlot) FontWeight.Bold else FontWeight.Normal,
                                textAlign = TextAlign.Center
                            )
                        }
                        Box(modifier = Modifier.fillMaxSize().padding(start = 38.dp)) {
                            Spacer(modifier = Modifier.fillMaxWidth().height(1.dp).background(MaterialTheme.colorScheme.onSurface.copy(alpha = 0.12f)).align(Alignment.TopCenter))
                        }
                    }
                }
            }
            // Courses overlay
            Row(modifier = Modifier.matchParentSize().padding(start = 38.dp)) {
                for (wd in listOf(7, 1, 2, 3, 4, 5, 6)) {
                    Box(modifier = Modifier.weight(1f).fillMaxHeight()) {
                        val dayCourses = ScheduleManager.getCoursesOn(wd, weekNo)
                        for (c in dayCourses) {
                            CourseBlock(c, colorMap[c.name] ?: Color.Gray, rowH)
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun CourseBlock(course: Course, color: Color, rowH: androidx.compose.ui.unit.Dp) {
    var showDetail by remember { mutableStateOf(false) }
    val topOff = rowH * (course.secStart - 1)
    val height = rowH * (course.secEnd - course.secStart + 1)

    Box(
        modifier = Modifier
            .padding(1.dp)
            .offset(y = topOff)
            .height(height)
            .fillMaxWidth()
            .clip(RoundedCornerShape(6.dp))
            .background(color)
            .clickable { showDetail = true }
            .padding(2.dp)
    ) {
        Column(modifier = Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(course.name, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center, maxLines = 3, overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis)
            if (course.room.isNotEmpty() && height > rowH * 1.5f) {
                Spacer(Modifier.height(2.dp))
                Text("@${course.room}", color = Color(0xFFEEEEEE), fontSize = 9.sp, textAlign = TextAlign.Center, maxLines = 2)
            }
        }
    }

    if (showDetail) {
        AlertDialog(
            onDismissRequest = { showDetail = false },
            containerColor = MaterialTheme.colorScheme.surface,
            title = { Text("课程详情", color = MaterialTheme.colorScheme.onSurface) },
            text = {
                Column {
                    Text(course.name, color = color, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                    Spacer(Modifier.height(8.dp))
                    Text("节次: ${course.secStart} - ${course.secEnd}节", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f), fontSize = 14.sp)
                    Text("周次: ${course.weekStart} - ${course.weekEnd}周 (${course.parity})", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f), fontSize = 14.sp)
                    if (course.teacher.isNotEmpty()) Text("教师: ${course.teacher}", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f), fontSize = 14.sp)
                    if (course.room.isNotEmpty()) Text("教室: ${course.room}", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f), fontSize = 14.sp)
                    if (course.note.isNotEmpty()) Text("备注: ${course.note}", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f), fontSize = 14.sp)
                }
            },
            confirmButton = {
                TextButton(onClick = { showDetail = false }) { Text("关闭") }
            }
        )
    }
}

