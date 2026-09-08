package com.amiya.pet.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChevronLeft
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Download
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
fun ScheduleScreen() {
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
                    Icon(Icons.Default.ChevronLeft, "上一周", tint = Color.White)
                }
                Text("第 $currentWeek 周", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                IconButton(onClick = { currentWeek++ }) {
                    Icon(Icons.Default.ChevronRight, "下一周", tint = Color.White)
                }
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

        if (ScheduleManager.courses.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("暂无课表数据，请点击右上角导入", color = Color.Gray)
            }
        } else {
            TimetableGrid(currentWeek, refreshTrigger)
        }
    }
    
    if (showImportDialog) {
        var jsonInput by remember { mutableStateOf("") }
        var dateInput by remember { mutableStateOf(SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())) }
        var resultMsg by remember { mutableStateOf("") }
        
        AlertDialog(
            onDismissRequest = { showImportDialog = false },
            containerColor = MaterialTheme.colorScheme.surface,
            title = { Text("导入强智教务课表", color = Color.White) },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    Text("请在下方粘贴抓包得到的课表 JSON 数据：", fontSize = 13.sp, color = Color.LightGray)
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = jsonInput,
                        onValueChange = { jsonInput = it },
                        modifier = Modifier.fillMaxWidth().height(150.dp),
                        textStyle = LocalTextStyle.current.copy(color = Color.White)
                    )
                    Spacer(Modifier.height(12.dp))
                    Text("开学日期 (第一周周一，格式 YYYY-MM-DD)：", fontSize = 13.sp, color = Color.LightGray)
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = dateInput,
                        onValueChange = { dateInput = it },
                        modifier = Modifier.fillMaxWidth(),
                        textStyle = LocalTextStyle.current.copy(color = Color.White)
                    )
                    if (resultMsg.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Text(resultMsg, color = if(resultMsg.contains("成功")) Color(0xFF4CAF50) else MaterialTheme.colorScheme.error, fontSize = 13.sp)
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
fun TimetableGrid(weekNo: Int, refreshTrigger: Int) {
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

    Column(modifier = Modifier.fillMaxSize()) {
        Row(modifier = Modifier.fillMaxWidth().padding(start = 38.dp, end = 8.dp)) {
            weekDays.forEach {
                Text(it, modifier = Modifier.weight(1f), color = Color.LightGray, fontSize = 12.sp, textAlign = TextAlign.Center)
            }
        }
        Spacer(Modifier.height(4.dp))
        BoxWithConstraints(modifier = Modifier.weight(1f).fillMaxWidth().padding(end = 8.dp, bottom = 16.dp)) {
            val rowH = maxHeight / 13
            // Background grid lines and row numbers
            Column(modifier = Modifier.fillMaxSize()) {
                for (i in 1..13) {
                    Box(modifier = Modifier.fillMaxWidth().height(rowH)) {
                        Box(
                            modifier = Modifier
                                .width(38.dp)
                                .fillMaxHeight()
                                .clickable { showTime = !showTime }
                                .align(Alignment.CenterStart),
                            contentAlignment = Alignment.Center
                        ) {
                            val rawTime = ScheduleManager.sections[i.toString()] ?: "$i"
                            val displayTime = if (!showTime) i.toString() else {
                                if (rawTime.contains("-") || rawTime.contains("\n")) {
                                    rawTime.replace("-", "\n")
                                } else if (rawTime.contains(":")) {
                                    try {
                                        val parts = rawTime.split(":")
                                        val h = parts[0].toInt()
                                        val m = parts[1].toInt()
                                        val endM = h * 60 + m + 45
                                        val eH = endM / 60
                                        val eM = endM % 60
                                        "$rawTime\n${String.format(Locale.getDefault(), "%02d:%02d", eH, eM)}"
                                    } catch(e: Exception) { rawTime }
                                } else rawTime
                            }
                            Text(
                                text = displayTime,
                                color = Color.Gray,
                                fontSize = if (showTime) 9.sp else 11.sp,
                                lineHeight = 11.sp,
                                textAlign = TextAlign.Center
                            )
                        }
                        Box(modifier = Modifier.fillMaxSize().padding(start = 38.dp)) {
                            Spacer(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color(0xFF333333)).align(Alignment.TopCenter))
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
            title = { Text("课程详情", color = Color.White) },
            text = {
                Column {
                    Text(course.name, color = color, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                    Spacer(Modifier.height(8.dp))
                    Text("节次: ${course.secStart} - ${course.secEnd}节", color = Color.LightGray, fontSize = 14.sp)
                    Text("周次: ${course.weekStart} - ${course.weekEnd}周 (${course.parity})", color = Color.LightGray, fontSize = 14.sp)
                    if (course.teacher.isNotEmpty()) Text("教师: ${course.teacher}", color = Color.LightGray, fontSize = 14.sp)
                    if (course.room.isNotEmpty()) Text("教室: ${course.room}", color = Color.LightGray, fontSize = 14.sp)
                    if (course.note.isNotEmpty()) Text("备注: ${course.note}", color = Color.LightGray, fontSize = 14.sp)
                }
            },
            confirmButton = {
                TextButton(onClick = { showDetail = false }) { Text("关闭") }
            }
        )
    }
}

