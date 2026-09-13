package com.amiya.pet.ui

import android.widget.Toast
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.amiya.pet.core.schedule.ExamItem
import com.amiya.pet.core.schedule.ExamManager
import kotlinx.coroutines.delay

@Composable
fun ExamScheduleView(
    onBackToSchedule: () -> Unit
) {
    val context = LocalContext.current
    LaunchedEffect(Unit) {
        ExamManager.load(context)
    }

    // 每 10 秒刷新一次倒计时
    var ticker by remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(10_000L)
            ticker = System.currentTimeMillis()
        }
    }

    val exams = ExamManager.exams
    val upcomingExams = remember(exams, ticker) {
        exams.filter { !it.isFinished(ticker) }
    }
    val finishedExams = remember(exams, ticker) {
        exams.filter { it.isFinished(ticker) }
    }
    val nextExam = upcomingExams.firstOrNull()

    var showEditDialog by remember { mutableStateOf(false) }
    var selectedExamToEdit by remember { mutableStateOf<ExamItem?>(null) }
    var showFinishedExpanded by remember { mutableStateOf(false) }

    Scaffold(
        containerColor = Color(0xFF12161A),
        topBar = {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .statusBarsPadding()
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(
                        onClick = onBackToSchedule,
                        modifier = Modifier
                            .size(38.dp)
                            .clip(CircleShape)
                            .background(Color(0xFF212730))
                    ) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "返回课表", tint = Color.White)
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            text = "期末考试日程",
                            color = Color.White,
                            fontSize = 20.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "考前倒计时 · 考场与座号一览",
                            color = Color.LightGray,
                            fontSize = 11.sp
                        )
                    }
                }

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilledTonalButton(
                        onClick = {
                            selectedExamToEdit = null
                            showEditDialog = true
                        },
                        colors = ButtonDefaults.filledTonalButtonColors(
                            containerColor = Color(0xFF00B0FF),
                            contentColor = Color.White
                        ),
                        shape = RoundedCornerShape(12.dp),
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp)
                    ) {
                        Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("录入考试", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // 1. 考前倒计时英雄卡片 (Hero Countdown Card)
            item {
                HeroCountdownCard(
                    nextExam = nextExam,
                    now = ticker,
                    onClickEdit = {
                        selectedExamToEdit = nextExam
                        showEditDialog = true
                    }
                )
            }

            // 2. 待考日程标题与数量
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "即将开考 (${upcomingExams.size})",
                        color = Color.White,
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = "点击卡片可快速编辑考场与座号",
                        color = Color.Gray,
                        fontSize = 11.sp
                    )
                }
            }

            if (upcomingExams.isEmpty()) {
                item {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(16.dp),
                        colors = CardDefaults.cardColors(containerColor = Color(0xFF1E232A))
                    ) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(32.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Icon(
                                    Icons.Default.Celebration,
                                    contentDescription = null,
                                    tint = Color(0xFF00E676),
                                    modifier = Modifier.size(48.dp)
                                )
                                Spacer(modifier = Modifier.height(12.dp))
                                Text("暂无待开考科目", color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.Bold)
                                Spacer(modifier = Modifier.height(4.dp))
                                Text("点击右上角「录入考试」规划您的考试日程吧~", color = Color.Gray, fontSize = 12.sp)
                            }
                        }
                    }
                }
            } else {
                items(upcomingExams, key = { it.id }) { exam ->
                    ExamCard(
                        exam = exam,
                        now = ticker,
                        onClick = {
                            selectedExamToEdit = exam
                            showEditDialog = true
                        }
                    )
                }
            }

            // 3. 已结束考试归档（折叠式呈现）
            if (finishedExams.isNotEmpty()) {
                item {
                    Spacer(modifier = Modifier.height(8.dp))
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { showFinishedExpanded = !showFinishedExpanded },
                        shape = RoundedCornerShape(16.dp),
                        colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1F26))
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    Icons.Default.TaskAlt,
                                    contentDescription = null,
                                    tint = Color(0xFF00E676),
                                    modifier = Modifier.size(20.dp)
                                )
                                Spacer(modifier = Modifier.width(10.dp))
                                Text(
                                    text = "已结束考试 (${finishedExams.size})",
                                    color = Color.LightGray,
                                    fontSize = 14.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                            Icon(
                                if (showFinishedExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                                contentDescription = null,
                                tint = Color.Gray
                            )
                        }
                    }
                }

                if (showFinishedExpanded) {
                    items(finishedExams, key = { it.id }) { exam ->
                        FinishedExamCard(
                            exam = exam,
                            onClick = {
                                selectedExamToEdit = exam
                                showEditDialog = true
                            }
                        )
                    }
                }
            }

            item {
                Spacer(modifier = Modifier.height(40.dp))
            }
        }
    }

    // 编辑/添加考试弹窗
    if (showEditDialog) {
        ExamEditDialog(
            initialExam = selectedExamToEdit,
            onDismiss = {
                showEditDialog = false
                selectedExamToEdit = null
            },
            onSaved = { savedItem ->
                if (selectedExamToEdit == null) {
                    ExamManager.addExam(context, savedItem)
                } else {
                    ExamManager.updateExam(context, savedItem)
                }
                showEditDialog = false
                selectedExamToEdit = null
            },
            onDeleted = { delId ->
                ExamManager.deleteExam(context, delId)
                showEditDialog = false
                selectedExamToEdit = null
            }
        )
    }
}

/**
 * 考前倒计时英雄大卡片
 */
@Composable
private fun HeroCountdownCard(
    nextExam: ExamItem?,
    now: Long,
    onClickEdit: () -> Unit
) {
    if (nextExam == null) {
        // 所有考试均已结束或无考试
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(containerColor = Color(0xFF1E2833))
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = "🎉 本学期期末考试全部完成！",
                    color = Color(0xFF00E676),
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "博士辛苦了！请好好享受罗德岛专属的假期吧~",
                    color = Color.LightGray,
                    fontSize = 13.sp
                )
            }
        }
        return
    }

    val isOngoing = nextExam.isOngoing(now)
    val remainingMillis = nextExam.remainingMillis(now)
    val (days, hours, mins) = ExamManager.getCountdownParts(nextExam.examTimeMillis, now)

    // 紧急程度配色：< 24h 赤红, < 72h 琥珀橙, 平时 青蓝
    val themeColor = when {
        isOngoing -> Color(0xFFFF1744)
        remainingMillis < 24 * 3600 * 1000L -> Color(0xFFFF5252)
        remainingMillis < 72 * 3600 * 1000L -> Color(0xFFFF9100)
        else -> Color(0xFF00B0FF)
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClickEdit() },
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF1D242E)),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = Brush.horizontalGradient(
                listOf(themeColor.copy(alpha = 0.6f), Color.Transparent)
            ),
            width = 1.5.dp
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(20.dp)
        ) {
            // 顶栏标签
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(themeColor)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = if (isOngoing) "🔴 正在进行中" else "🎯 最近一场考试",
                        color = themeColor,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold
                    )
                }

                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = themeColor.copy(alpha = 0.2f)
                ) {
                    Text(
                        text = nextExam.examType,
                        color = themeColor,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            // 科目大标题
            Text(
                text = nextExam.title,
                color = Color.White,
                fontSize = 22.sp,
                fontWeight = FontWeight.Bold
            )

            Spacer(modifier = Modifier.height(14.dp))

            // 倒计时核心展示区
            Card(
                colors = CardDefaults.cardColors(containerColor = Color(0xFF161B22)),
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 12.dp, horizontal = 16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    if (isOngoing) {
                        Column {
                            Text("考试正在进行中", color = Color(0xFFFF1744), fontSize = 16.sp, fontWeight = FontWeight.Bold)
                            Text("预定交卷时间：${nextExam.formattedTimeRangeStr().split("-").lastOrNull()?.trim() ?: ""}", color = Color.LightGray, fontSize = 12.sp)
                        }
                    } else {
                        Column {
                            Text("距开考剩余倒计时", color = Color.Gray, fontSize = 11.sp)
                            Spacer(modifier = Modifier.height(2.dp))
                            Row(verticalAlignment = Alignment.Bottom) {
                                if (days > 0) {
                                    Text(text = "$days", color = themeColor, fontSize = 26.sp, fontWeight = FontWeight.Black)
                                    Text(text = " 天 ", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                                }
                                Text(text = "$hours", color = themeColor, fontSize = 26.sp, fontWeight = FontWeight.Black)
                                Text(text = " 时 ", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                                Text(text = "$mins", color = themeColor, fontSize = 26.sp, fontWeight = FontWeight.Black)
                                Text(text = " 分", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                            }
                        }
                    }

                    // 考试日期徽章
                    Column(horizontalAlignment = Alignment.End) {
                        Text(text = nextExam.formattedDateStr(), color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                        Text(text = nextExam.formattedTimeRangeStr(), color = Color.LightGray, fontSize = 12.sp)
                    }
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            // 考场与座位号（核心防跑错）
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                // 考场地点
                Surface(
                    modifier = Modifier.weight(1.3f),
                    shape = RoundedCornerShape(12.dp),
                    color = Color(0xFF222A36)
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(Icons.Default.Place, contentDescription = null, tint = Color(0xFF00B0FF), modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = nextExam.location.ifEmpty { "考场未录入" },
                            color = Color.White,
                            fontSize = 12.sp,
                            maxLines = 1
                        )
                    }
                }

                // 座位号徽章
                Surface(
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(12.dp),
                    color = Color(0xFF222A36)
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(Icons.Default.AirlineSeatReclineNormal, contentDescription = null, tint = Color(0xFFFFD54F), modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = if (nextExam.seatNumber.isNotEmpty()) "座号: ${nextExam.seatNumber}" else "座号随机",
                            color = Color.White,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            maxLines = 1
                        )
                    }
                }
            }

            // 备考备注
            if (nextExam.note.isNotEmpty()) {
                Spacer(modifier = Modifier.height(10.dp))
                Row(
                    verticalAlignment = Alignment.Top,
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(Color(0xFF1E2833))
                        .padding(horizontal = 10.dp, vertical = 6.dp)
                ) {
                    Icon(Icons.Default.Info, contentDescription = null, tint = Color(0xFF81D4FA), modifier = Modifier.size(14.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(text = nextExam.note, color = Color(0xFFB0BEC5), fontSize = 11.sp, lineHeight = 16.sp)
                }
            }
        }
    }
}

/**
 * 待考考试卡片
 */
@Composable
private fun ExamCard(
    exam: ExamItem,
    now: Long,
    onClick: () -> Unit
) {
    val remainingMillis = exam.remainingMillis(now)
    val (days, hours, mins) = ExamManager.getCountdownParts(exam.examTimeMillis, now)

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF1E242C))
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 左侧日期时间柱状块
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier
                    .clip(RoundedCornerShape(12.dp))
                    .background(Color(0xFF28303B))
                    .padding(horizontal = 10.dp, vertical = 8.dp)
            ) {
                Text(
                    text = exam.formattedDateStr().split(" ").firstOrNull() ?: "",
                    color = Color(0xFF00B0FF),
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = exam.formattedDateStr().split(" ").lastOrNull() ?: "",
                    color = Color.LightGray,
                    fontSize = 11.sp
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = exam.formattedTimeRangeStr().split("-").firstOrNull()?.trim() ?: "",
                    color = Color.White,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold
                )
            }

            Spacer(modifier = Modifier.width(14.dp))

            // 右侧详情信息
            Column(modifier = Modifier.weight(1f)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = exam.title,
                        color = Color.White,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.weight(1f)
                    )
                    Surface(
                        shape = RoundedCornerShape(6.dp),
                        color = Color(0xFF37474F)
                    ) {
                        Text(
                            text = exam.examType,
                            color = Color(0xFFFFB74D),
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(6.dp))

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Place, contentDescription = null, tint = Color.Gray, modifier = Modifier.size(13.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = exam.location.ifEmpty { "考场待定" },
                        color = Color.LightGray,
                        fontSize = 12.sp
                    )
                    if (exam.seatNumber.isNotEmpty()) {
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            text = "座号: ${exam.seatNumber}",
                            color = Color(0xFFFFD54F),
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }

                Spacer(modifier = Modifier.height(6.dp))

                // 距开考倒计时提示
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Timer, contentDescription = null, tint = Color(0xFF00B0FF), modifier = Modifier.size(12.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = if (days > 0) "剩 $days 天 $hours 小时" else "仅剩 $hours 小时 $mins 分",
                        color = if (days == 0L) Color(0xFFFF5252) else Color(0xFF00B0FF),
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

/**
 * 已归档/已结束考试卡片
 */
@Composable
private fun FinishedExamCard(
    exam: ExamItem,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF181C22))
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column {
                Text(
                    text = exam.title,
                    color = Color.Gray,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "${exam.formattedDateStr()} · ${exam.location}",
                    color = Color.DarkGray,
                    fontSize = 11.sp
                )
            }
            Surface(
                shape = RoundedCornerShape(6.dp),
                color = Color(0xFF263238)
            ) {
                Text(
                    text = "已结束",
                    color = Color.Gray,
                    fontSize = 10.sp,
                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                )
            }
        }
    }
}
