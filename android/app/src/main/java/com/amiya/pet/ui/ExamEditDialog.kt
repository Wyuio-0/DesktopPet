package com.amiya.pet.ui

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import com.amiya.pet.core.schedule.ExamItem
import com.amiya.pet.core.schedule.ExamManager
import com.amiya.pet.core.schedule.ScheduleManager
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.UUID

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ExamEditDialog(
    initialExam: ExamItem? = null,
    onDismiss: () -> Unit,
    onSaved: (ExamItem) -> Unit,
    onDeleted: ((String) -> Unit)? = null
) {
    val context = LocalContext.current
    val scrollState = rememberScrollState()

    var title by remember { mutableStateOf(initialExam?.title ?: "") }
    var location by remember { mutableStateOf(initialExam?.location ?: "") }
    var seatNumber by remember { mutableStateOf(initialExam?.seatNumber ?: "") }
    var examType by remember { mutableStateOf(initialExam?.examType ?: "闭卷") }
    var durationMinutes by remember { mutableIntStateOf(initialExam?.durationMinutes ?: 120) }
    var durationInputText by remember { mutableStateOf((initialExam?.durationMinutes ?: 120).toString()) }
    var note by remember { mutableStateOf(initialExam?.note ?: "") }

    // 考试开始时间 Calendar 初始化
    val examCalendar = remember {
        Calendar.getInstance().apply {
            if (initialExam != null) {
                timeInMillis = initialExam.examTimeMillis
            } else {
                // 默认 2 天后的 09:00
                add(Calendar.DAY_OF_YEAR, 2)
                set(Calendar.HOUR_OF_DAY, 9)
                set(Calendar.MINUTE, 0)
                set(Calendar.SECOND, 0)
                set(Calendar.MILLISECOND, 0)
            }
        }
    }

    var selectedYear by remember { mutableIntStateOf(examCalendar.get(Calendar.YEAR)) }
    var selectedMonth by remember { mutableIntStateOf(examCalendar.get(Calendar.MONTH) + 1) }
    var selectedDay by remember { mutableIntStateOf(examCalendar.get(Calendar.DAY_OF_MONTH)) }
    var selectedHour by remember { mutableIntStateOf(examCalendar.get(Calendar.HOUR_OF_DAY)) }
    var selectedMinute by remember { mutableIntStateOf(examCalendar.get(Calendar.MINUTE)) }
    var timeInputText by remember {
        mutableStateOf(String.format(Locale.ROOT, "%02d:%02d", selectedHour, selectedMinute))
    }

    val showDatePicker = {
        android.app.DatePickerDialog(
            context,
            { _, y, m, d ->
                selectedYear = y
                selectedMonth = m + 1
                selectedDay = d
            },
            selectedYear,
            selectedMonth - 1,
            selectedDay
        ).show()
    }

    val showTimePicker = {
        android.app.TimePickerDialog(
            context,
            { _, h, m ->
                selectedHour = h
                selectedMinute = m
                timeInputText = String.format(Locale.ROOT, "%02d:%02d", h, m)
            },
            selectedHour,
            selectedMinute,
            true
        ).show()
    }

    // 从当前课表中提取已有课程名称列表作为快速选填 Chip
    val existingCourseNames = remember {
        ScheduleManager.courses.map { it.name }.distinct().filter { it.isNotBlank() }
    }

    val examTypes = listOf("闭卷", "开卷", "上机", "论文/大作业", "口试")
    val durations = listOf(60, 90, 120, 150, 180)

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Card(
            modifier = Modifier
                .fillMaxWidth(0.92f)
                .fillMaxHeight(0.88f),
            shape = RoundedCornerShape(24.dp),
            colors = CardDefaults.cardColors(containerColor = Color(0xFF1E232A))
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(20.dp)
            ) {
                // 顶部标题栏
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(40.dp)
                                .clip(RoundedCornerShape(10.dp))
                                .background(Color(0xFFFF9100).copy(alpha = 0.2f)),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                Icons.Default.EditCalendar,
                                contentDescription = null,
                                tint = Color(0xFFFF9100),
                                modifier = Modifier.size(24.dp)
                            )
                        }
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text(
                                text = if (initialExam == null) "添加期末考试" else "编辑期末考试",
                                color = Color.White,
                                fontSize = 18.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = "设置考场地点、座位号与考前倒计时",
                                color = Color.LightGray,
                                fontSize = 12.sp
                            )
                        }
                    }

                    if (initialExam != null && onDeleted != null) {
                        IconButton(onClick = {
                            onDeleted(initialExam.id)
                            Toast.makeText(context, "考试已删除", Toast.LENGTH_SHORT).show()
                            onDismiss()
                        }) {
                            Icon(Icons.Default.DeleteOutline, contentDescription = "删除考试", tint = Color(0xFFFF5252))
                        }
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // 可滚动内容区域
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .verticalScroll(scrollState)
                ) {
                    // 1. 考试科目名称
                    Text("考试科目 *", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(
                        value = title,
                        onValueChange = { title = it },
                        modifier = Modifier.fillMaxWidth(),
                        placeholder = { Text("例如：高等量子力学", color = Color.Gray) },
                        singleLine = true,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = Color.White,
                            unfocusedTextColor = Color.White,
                            focusedBorderColor = Color(0xFF00B0FF),
                            unfocusedBorderColor = Color(0xFF455A64)
                        )
                    )

                    // 快速选取已有课程 Chip
                    if (existingCourseNames.isNotEmpty()) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Text("从现有排课中快捷填入：", color = Color.LightGray, fontSize = 11.sp)
                        Spacer(modifier = Modifier.height(4.dp))
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            existingCourseNames.take(8).forEach { name ->
                                Surface(
                                    modifier = Modifier.clickable { title = name },
                                    shape = RoundedCornerShape(12.dp),
                                    color = if (title == name) Color(0xFF00B0FF).copy(alpha = 0.3f) else Color(0xFF2A313C)
                                ) {
                                    Text(
                                        text = name,
                                        color = if (title == name) Color(0xFF00B0FF) else Color.White,
                                        fontSize = 11.sp,
                                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp)
                                    )
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    // 2. 考试日期与时间
                    Text("开考日期与时间 *", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(6.dp))

                    // 快捷日期切换
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        listOf("今天" to 0, "明天" to 1, "后天" to 2, "3天后" to 3, "1周后" to 7).forEach { (label, offset) ->
                            Surface(
                                modifier = Modifier.clickable {
                                    val c = Calendar.getInstance().apply { add(Calendar.DAY_OF_YEAR, offset) }
                                    selectedYear = c.get(Calendar.YEAR)
                                    selectedMonth = c.get(Calendar.MONTH) + 1
                                    selectedDay = c.get(Calendar.DAY_OF_MONTH)
                                },
                                shape = RoundedCornerShape(12.dp),
                                color = Color(0xFF2A313C)
                            ) {
                                Text(
                                    text = label,
                                    color = Color.LightGray,
                                    fontSize = 11.sp,
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    // 日期选择卡片：年-月-日
                    Card(
                        colors = CardDefaults.cardColors(containerColor = Color(0xFF2A313C)),
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(12.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier
                                    .clip(RoundedCornerShape(8.dp))
                                    .clickable { showDatePicker() }
                                    .padding(vertical = 4.dp, horizontal = 4.dp)
                            ) {
                                Icon(
                                    Icons.Default.CalendarMonth,
                                    contentDescription = null,
                                    tint = Color(0xFF00B0FF),
                                    modifier = Modifier.size(18.dp)
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("日期：$selectedYear 年 $selectedMonth 月 $selectedDay 日", color = Color.White, fontSize = 14.sp)
                            }
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                IconButton(
                                    onClick = {
                                        val c = Calendar.getInstance().apply {
                                            set(selectedYear, selectedMonth - 1, selectedDay)
                                            add(Calendar.DAY_OF_YEAR, -1)
                                        }
                                        selectedYear = c.get(Calendar.YEAR)
                                        selectedMonth = c.get(Calendar.MONTH) + 1
                                        selectedDay = c.get(Calendar.DAY_OF_MONTH)
                                    },
                                    modifier = Modifier.size(32.dp)
                                ) {
                                    Icon(Icons.Default.ChevronLeft, null, tint = Color.LightGray)
                                }
                                IconButton(
                                    onClick = {
                                        val c = Calendar.getInstance().apply {
                                            set(selectedYear, selectedMonth - 1, selectedDay)
                                            add(Calendar.DAY_OF_YEAR, 1)
                                        }
                                        selectedYear = c.get(Calendar.YEAR)
                                        selectedMonth = c.get(Calendar.MONTH) + 1
                                        selectedDay = c.get(Calendar.DAY_OF_MONTH)
                                    },
                                    modifier = Modifier.size(32.dp)
                                ) {
                                    Icon(Icons.Default.ChevronRight, null, tint = Color.LightGray)
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    // 时间选择卡片：开考时间 (时:分)
                    Card(
                        colors = CardDefaults.cardColors(containerColor = Color(0xFF2A313C)),
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(12.dp)
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(8.dp))
                                        .clickable { showTimePicker() }
                                        .padding(vertical = 4.dp, horizontal = 4.dp)
                                ) {
                                    Icon(
                                        Icons.Default.AccessTime,
                                        contentDescription = null,
                                        tint = Color(0xFF00B0FF),
                                        modifier = Modifier.size(18.dp)
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        "开考时间：",
                                        color = Color.White,
                                        fontSize = 14.sp
                                    )
                                    Text(
                                        text = String.format(Locale.ROOT, "%02d:%02d", selectedHour, selectedMinute),
                                        color = Color(0xFF00B0FF),
                                        fontSize = 16.sp,
                                        fontWeight = FontWeight.Bold
                                    )
                                }

                                Button(
                                    onClick = { showTimePicker() },
                                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF00B0FF).copy(alpha = 0.2f)),
                                    shape = RoundedCornerShape(8.dp),
                                    contentPadding = PaddingValues(horizontal = 10.dp, vertical = 6.dp),
                                    modifier = Modifier.height(32.dp)
                                ) {
                                    Icon(
                                        Icons.Default.Schedule,
                                        contentDescription = null,
                                        tint = Color(0xFF00B0FF),
                                        modifier = Modifier.size(14.dp)
                                    )
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text("时钟选取…", color = Color(0xFF00B0FF), fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
                                }
                            }

                            Spacer(modifier = Modifier.height(10.dp))

                            // 常用时间快捷 Chips
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .horizontalScroll(rememberScrollState()),
                                horizontalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                listOf("08:00", "08:30", "09:00", "14:00", "14:30", "16:00", "19:00").forEach { timeStr ->
                                    val parts = timeStr.split(":")
                                    val h = parts[0].toInt()
                                    val m = parts[1].toInt()
                                    val isSelected = selectedHour == h && selectedMinute == m
                                    Surface(
                                        modifier = Modifier.clickable {
                                            selectedHour = h
                                            selectedMinute = m
                                            timeInputText = timeStr
                                        },
                                        shape = RoundedCornerShape(8.dp),
                                        color = if (isSelected) Color(0xFF00B0FF) else Color(0xFF37474F)
                                    ) {
                                        Text(
                                            text = timeStr,
                                            color = Color.White,
                                            fontSize = 11.sp,
                                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                                        )
                                    }
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    // 自定义开考时间输入框 (支持直接手动输入，如 08:30 或 10:15)
                    OutlinedTextField(
                        value = timeInputText,
                        onValueChange = { newVal ->
                            timeInputText = newVal
                            val match = Regex("""^([0-1]?[0-9]|2[0-3])[:：]([0-5]?[0-9])$""").matchEntire(newVal.trim())
                            if (match != null) {
                                val h = match.groupValues[1].toIntOrNull()
                                val m = match.groupValues[2].toIntOrNull()
                                if (h != null && m != null && h in 0..23 && m in 0..59) {
                                    selectedHour = h
                                    selectedMinute = m
                                }
                            }
                        },
                        placeholder = { Text("自定义开考时间 (如 08:30、15:00)", color = Color.Gray, fontSize = 12.sp) },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text),
                        leadingIcon = {
                            Icon(Icons.Default.AccessTime, contentDescription = null, tint = Color(0xFF00B0FF), modifier = Modifier.size(18.dp))
                        },
                        trailingIcon = {
                            IconButton(onClick = { showTimePicker() }) {
                                Icon(Icons.Default.Schedule, contentDescription = "时钟选取", tint = Color.LightGray, modifier = Modifier.size(18.dp))
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = Color.White,
                            unfocusedTextColor = Color.White,
                            focusedBorderColor = Color(0xFF00B0FF),
                            unfocusedBorderColor = Color(0xFF455A64),
                            focusedContainerColor = Color(0xFF222A36),
                            unfocusedContainerColor = Color(0xFF222A36)
                        )
                    )

                    Spacer(modifier = Modifier.height(16.dp))

                    // 3. 考试时长 (常用预设 + 自定义分钟数)
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("考试时长 (分钟)", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                        val endCal = Calendar.getInstance().apply {
                            set(selectedYear, selectedMonth - 1, selectedDay, selectedHour, selectedMinute, 0)
                            add(Calendar.MINUTE, durationMinutes)
                        }
                        val endTimeStr = String.format(Locale.ROOT, "%02d:%02d", endCal.get(Calendar.HOUR_OF_DAY), endCal.get(Calendar.MINUTE))
                        Text(
                            "预计交卷 $endTimeStr (${durationMinutes}分钟)",
                            color = Color(0xFF00B0FF),
                            fontSize = 12.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                    Spacer(modifier = Modifier.height(6.dp))

                    // 常用时长快速选择
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        durations.forEach { dur ->
                            val isSelected = durationMinutes == dur
                            Surface(
                                modifier = Modifier
                                    .weight(1f)
                                    .clickable {
                                        durationMinutes = dur
                                        durationInputText = dur.toString()
                                    },
                                shape = RoundedCornerShape(10.dp),
                                color = if (isSelected) Color(0xFF00B0FF) else Color(0xFF2A313C)
                            ) {
                                Box(modifier = Modifier.padding(vertical = 8.dp), contentAlignment = Alignment.Center) {
                                    Text(
                                        text = "${dur}m",
                                        color = Color.White,
                                        fontSize = 12.sp,
                                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                                    )
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    // 自定义时长输入框
                    OutlinedTextField(
                        value = durationInputText,
                        onValueChange = { newVal ->
                            val digits = newVal.filter { it.isDigit() }.take(4)
                            durationInputText = digits
                            val parsed = digits.toIntOrNull()
                            if (parsed != null && parsed > 0) {
                                durationMinutes = parsed
                            }
                        },
                        placeholder = { Text("输入自定义考试时长 (如 100)", color = Color.Gray, fontSize = 12.sp) },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        leadingIcon = {
                            Icon(Icons.Default.Timer, contentDescription = null, tint = Color(0xFF00B0FF), modifier = Modifier.size(18.dp))
                        },
                        trailingIcon = {
                            Text("分钟", color = Color.LightGray, fontSize = 12.sp, modifier = Modifier.padding(end = 12.dp))
                        },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = Color.White,
                            unfocusedTextColor = Color.White,
                            focusedBorderColor = Color(0xFF00B0FF),
                            unfocusedBorderColor = Color(0xFF455A64),
                            focusedContainerColor = Color(0xFF222A36),
                            unfocusedContainerColor = Color(0xFF222A36)
                        )
                    )

                    Spacer(modifier = Modifier.height(16.dp))

                    // 4. 考场与座位号（关键信息并排）
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Column(modifier = Modifier.weight(1.3f)) {
                            Text("考场地点", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                            Spacer(modifier = Modifier.height(6.dp))
                            OutlinedTextField(
                                value = location,
                                onValueChange = { location = it },
                                placeholder = { Text("如: 理学楼 301", color = Color.Gray, fontSize = 12.sp) },
                                singleLine = true,
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedTextColor = Color.White,
                                    unfocusedTextColor = Color.White,
                                    focusedBorderColor = Color(0xFF00B0FF),
                                    unfocusedBorderColor = Color(0xFF455A64)
                                )
                            )
                        }

                        Column(modifier = Modifier.weight(1f)) {
                            Text("座位号 / 座号", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                            Spacer(modifier = Modifier.height(6.dp))
                            OutlinedTextField(
                                value = seatNumber,
                                onValueChange = { seatNumber = it },
                                placeholder = { Text("如: 38 号", color = Color.Gray, fontSize = 12.sp) },
                                singleLine = true,
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedTextColor = Color.White,
                                    unfocusedTextColor = Color.White,
                                    focusedBorderColor = Color(0xFF00B0FF),
                                    unfocusedBorderColor = Color(0xFF455A64)
                                )
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    // 5. 考试形式
                    Text("考试类型", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(6.dp))
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        examTypes.forEach { type ->
                            Surface(
                                modifier = Modifier.clickable { examType = type },
                                shape = RoundedCornerShape(10.dp),
                                color = if (examType == type) Color(0xFFFF9100) else Color(0xFF2A313C)
                            ) {
                                Text(
                                    text = type,
                                    color = Color.White,
                                    fontSize = 12.sp,
                                    fontWeight = if (examType == type) FontWeight.Bold else FontWeight.Normal,
                                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    // 6. 备考注意事项 / 携带工具
                    Text("备考提醒与携带物品 (选填)", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(
                        value = note,
                        onValueChange = { note = it },
                        modifier = Modifier.fillMaxWidth(),
                        placeholder = { Text("如: 自备科学计算器、黑色水笔、学生证", color = Color.Gray, fontSize = 12.sp) },
                        maxLines = 2,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = Color.White,
                            unfocusedTextColor = Color.White,
                            focusedBorderColor = Color(0xFF00B0FF),
                            unfocusedBorderColor = Color(0xFF455A64)
                        )
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                // 底部操作按钮
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    OutlinedButton(
                        onClick = onDismiss,
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Text("取消", color = Color.LightGray)
                    }

                    Button(
                        onClick = {
                            if (title.isBlank()) {
                                Toast.makeText(context, "请输入考试科目名称", Toast.LENGTH_SHORT).show()
                                return@Button
                            }

                            val finalDuration = durationInputText.toIntOrNull() ?: durationMinutes
                            if (finalDuration <= 0) {
                                Toast.makeText(context, "考试时长必须大于 0 分钟", Toast.LENGTH_SHORT).show()
                                return@Button
                            }

                            val timeMatch = Regex("""^([0-1]?[0-9]|2[0-3])[:：]([0-5]?[0-9])$""").matchEntire(timeInputText.trim())
                            val finalHour = timeMatch?.groupValues?.get(1)?.toIntOrNull() ?: selectedHour
                            val finalMinute = timeMatch?.groupValues?.get(2)?.toIntOrNull() ?: selectedMinute

                            val cal = Calendar.getInstance().apply {
                                set(selectedYear, selectedMonth - 1, selectedDay, finalHour, finalMinute, 0)
                                set(Calendar.MILLISECOND, 0)
                            }

                            val item = ExamItem(
                                id = initialExam?.id ?: UUID.randomUUID().toString(),
                                title = title.trim(),
                                examTimeMillis = cal.timeInMillis,
                                durationMinutes = finalDuration,
                                location = location.trim(),
                                seatNumber = seatNumber.trim(),
                                examType = examType,
                                note = note.trim(),
                                relatedCourseId = initialExam?.relatedCourseId
                            )
                            onSaved(item)
                            Toast.makeText(context, "考试日程已保存", Toast.LENGTH_SHORT).show()
                            onDismiss()
                        },
                        modifier = Modifier.weight(1.5f),
                        shape = RoundedCornerShape(12.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF00B0FF))
                    ) {
                        Icon(Icons.Default.Check, null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(6.dp))
                        Text("保存考试", color = Color.White, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}
