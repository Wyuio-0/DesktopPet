package com.amiya.pet.ui

import android.content.Context
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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
import com.amiya.pet.core.focus.PomodoroMode
import com.amiya.pet.core.focus.PomodoroState
import com.amiya.pet.core.focus.PomodoroTimer

@Composable
fun PomodoroScreen() {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("amiya_pet_prefs", Context.MODE_PRIVATE) }
    var workMinutes by remember { mutableIntStateOf(prefs.getInt("pref_pomodoro_work_mins", 25)) }
    var breakMinutes by remember { mutableIntStateOf(prefs.getInt("pref_pomodoro_break_mins", 5)) }
    var showCustomDialog by remember { mutableStateOf(false) }

    val status by PomodoroTimer.status.collectAsState()
    val isWork = status.mode == PomodoroMode.WORK
    val currentMinutes = if (isWork) workMinutes else breakMinutes

    // 初始进入页面若处于空闲状态，同步用户保存的偏好时长
    LaunchedEffect(Unit) {
        if (status.state == PomodoroState.IDLE) {
            PomodoroTimer.setDuration(status.mode, currentMinutes)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(horizontal = 20.dp, vertical = 16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        // 顶部标题
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = "阿米娅专注番茄钟",
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onBackground
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "让阿米娅陪伴博士高效工作与沉浸学习",
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.6f)
            )
        }

        // 模式切换与时长设置区域
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            // 模式选择（专注 vs 小憩）
            Row(
                modifier = Modifier
                    .clip(RoundedCornerShape(20.dp))
                    .background(MaterialTheme.colorScheme.surface)
                    .padding(4.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                FilterChip(
                    selected = isWork,
                    onClick = {
                        if (status.state != PomodoroState.RUNNING) {
                            PomodoroTimer.setDuration(PomodoroMode.WORK, workMinutes)
                        }
                    },
                    label = { Text("专注 (${workMinutes}m)") },
                    leadingIcon = {
                        Icon(
                            Icons.Default.Timer,
                            contentDescription = null,
                            modifier = Modifier.size(16.dp),
                            tint = if (isWork) Color.Black else MaterialTheme.colorScheme.onSurface
                        )
                    },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = MaterialTheme.colorScheme.primary,
                        selectedLabelColor = Color.Black,
                        containerColor = MaterialTheme.colorScheme.surfaceVariant,
                        labelColor = MaterialTheme.colorScheme.onSurface
                    )
                )
                FilterChip(
                    selected = !isWork,
                    onClick = {
                        if (status.state != PomodoroState.RUNNING) {
                            PomodoroTimer.setDuration(PomodoroMode.SHORT_BREAK, breakMinutes)
                        }
                    },
                    label = { Text("小憩 (${breakMinutes}m)") },
                    leadingIcon = {
                        Icon(
                            Icons.Default.Coffee,
                            contentDescription = null,
                            modifier = Modifier.size(16.dp),
                            tint = if (!isWork) Color.Black else MaterialTheme.colorScheme.onSurface
                        )
                    },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = MaterialTheme.colorScheme.primary,
                        selectedLabelColor = Color.Black,
                        containerColor = MaterialTheme.colorScheme.surfaceVariant,
                        labelColor = MaterialTheme.colorScheme.onSurface
                    )
                )
            }

            // 快捷时长预设气泡与自定义时长按钮
            Row(
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                val presets = if (isWork) listOf(15, 25, 45, 60) else listOf(3, 5, 10, 15)
                presets.forEach { mins ->
                    val isSelected = currentMinutes == mins
                    AssistChip(
                        onClick = {
                            if (status.state != PomodoroState.RUNNING) {
                                if (isWork) {
                                    workMinutes = mins
                                    prefs.edit().putInt("pref_pomodoro_work_mins", mins).apply()
                                } else {
                                    breakMinutes = mins
                                    prefs.edit().putInt("pref_pomodoro_break_mins", mins).apply()
                                }
                                PomodoroTimer.setDuration(status.mode, mins)
                            }
                        },
                        label = {
                            Text(
                                "${mins}m",
                                fontSize = 11.sp,
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                            )
                        },
                        colors = AssistChipDefaults.assistChipColors(
                            containerColor = if (isSelected) MaterialTheme.colorScheme.primary.copy(alpha = 0.22f) else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f),
                            labelColor = if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface
                        ),
                        border = if (isSelected) BorderStroke(1.dp, MaterialTheme.colorScheme.primary) else null,
                        shape = RoundedCornerShape(12.dp)
                    )
                }

                // 自定义时长弹窗入口
                AssistChip(
                    onClick = {
                        if (status.state != PomodoroState.RUNNING) {
                            showCustomDialog = true
                        }
                    },
                    label = {
                        Text(
                            text = if (!presets.contains(currentMinutes)) "${currentMinutes}m ⚙️" else "自定义",
                            fontSize = 11.sp,
                            fontWeight = if (!presets.contains(currentMinutes)) FontWeight.Bold else FontWeight.Normal
                        )
                    },
                    leadingIcon = {
                        Icon(Icons.Default.Tune, contentDescription = "自定义时长", modifier = Modifier.size(13.dp))
                    },
                    colors = AssistChipDefaults.assistChipColors(
                        containerColor = if (!presets.contains(currentMinutes)) MaterialTheme.colorScheme.primary.copy(alpha = 0.22f) else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f),
                        labelColor = if (!presets.contains(currentMinutes)) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface
                    ),
                    border = if (!presets.contains(currentMinutes)) BorderStroke(1.dp, MaterialTheme.colorScheme.primary) else null,
                    shape = RoundedCornerShape(12.dp)
                )
            }
        }

        // 倒计时环形表盘
        Box(
            contentAlignment = Alignment.Center,
            modifier = Modifier.size(230.dp)
        ) {
            CircularProgressIndicator(
                progress = { status.progress },
                modifier = Modifier.fillMaxSize(),
                strokeWidth = 10.dp,
                color = if (isWork) MaterialTheme.colorScheme.primary else Color(0xFF4CAF50),
                trackColor = MaterialTheme.colorScheme.surfaceVariant
            )
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    text = status.formattedTime,
                    fontSize = 44.sp,
                    fontWeight = FontWeight.ExtraBold,
                    color = MaterialTheme.colorScheme.onBackground
                )
                Text(
                    text = when (status.state) {
                        PomodoroState.RUNNING -> if (isWork) "正在专注中..." else "正在小憩中..."
                        PomodoroState.PAUSED -> "已暂停"
                        PomodoroState.COMPLETED -> "本次已完成！"
                        PomodoroState.IDLE -> "准备就绪 · 目标 ${currentMinutes}分钟"
                    },
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium,
                    color = MaterialTheme.colorScheme.primary
                )
            }
        }

        // 陪伴加油语录卡片
        Card(
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Row(
                modifier = Modifier.padding(14.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = Icons.Default.Favorite,
                    contentDescription = null,
                    tint = Color(0xFFFF4081),
                    modifier = Modifier.size(24.dp)
                )
                Spacer(modifier = Modifier.width(10.dp))
                Text(
                    text = when (status.state) {
                        PomodoroState.RUNNING -> if (isWork) {
                            "博士，沉浸于当下，${workMinutes}分钟后我们一起休息！阿米娅会在身侧守护您。"
                        } else {
                            "短暂小憩${breakMinutes}分钟，闭目放松，深呼吸吧，博士！"
                        }
                        PomodoroState.COMPLETED -> if (isWork) {
                            "太棒了博士！${workMinutes}分钟专注圆满完成，放下手头工作喝杯温水吧！"
                        } else {
                            "休息结束，精力已充满！准备好迎接下一个高光挑战了吗？"
                        }
                        else -> "设定心仪的时长，开始一段专注旅程吧，博士。罗德岛期待您的高光时刻。"
                    },
                    fontSize = 12.sp,
                    lineHeight = 17.sp,
                    color = MaterialTheme.colorScheme.onSurface
                )
            }
        }

        // 底部控制按钮组
        Row(
            horizontalArrangement = Arrangement.spacedBy(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            when (status.state) {
                PomodoroState.IDLE, PomodoroState.COMPLETED -> {
                    Button(
                        onClick = {
                            if (isWork) {
                                PomodoroTimer.startFocus(workMinutes)
                            } else {
                                PomodoroTimer.startBreak(breakMinutes)
                            }
                        },
                        modifier = Modifier
                            .height(52.dp)
                            .widthIn(min = 170.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                    ) {
                        Icon(Icons.Default.PlayArrow, contentDescription = null, tint = Color.Black)
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = if (isWork) "开始专注 (${workMinutes}m)" else "开始小憩 (${breakMinutes}m)",
                            color = Color.Black,
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp
                        )
                    }
                }
                PomodoroState.RUNNING -> {
                    Button(
                        onClick = { PomodoroTimer.pause() },
                        modifier = Modifier
                            .height(52.dp)
                            .widthIn(min = 120.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFB74D))
                    ) {
                        Icon(Icons.Default.Pause, contentDescription = null, tint = Color.Black)
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("暂停", color = Color.Black, fontWeight = FontWeight.Bold)
                    }
                    OutlinedButton(
                        onClick = { PomodoroTimer.reset(currentMinutes) },
                        modifier = Modifier.height(52.dp)
                    ) {
                        Text("放弃")
                    }
                }
                PomodoroState.PAUSED -> {
                    Button(
                        onClick = { PomodoroTimer.resume() },
                        modifier = Modifier
                            .height(52.dp)
                            .widthIn(min = 120.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                    ) {
                        Icon(Icons.Default.PlayArrow, contentDescription = null, tint = Color.Black)
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("继续", color = Color.Black, fontWeight = FontWeight.Bold)
                    }
                    OutlinedButton(
                        onClick = { PomodoroTimer.reset(currentMinutes) },
                        modifier = Modifier.height(52.dp)
                    ) {
                        Text("重置")
                    }
                }
            }
        }
    }

    // 自定义时长弹窗
    if (showCustomDialog) {
        val minLimit = 1
        val maxLimit = if (isWork) 180 else 60
        var tempMinutes by remember { mutableIntStateOf(if (isWork) workMinutes else breakMinutes) }

        AlertDialog(
            onDismissRequest = { showCustomDialog = false },
            containerColor = MaterialTheme.colorScheme.surface,
            title = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Default.Tune,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = if (isWork) "自定义专注时长" else "自定义小憩时长",
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
                        text = "$tempMinutes 分钟",
                        fontSize = 32.sp,
                        fontWeight = FontWeight.ExtraBold,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Spacer(modifier = Modifier.height(14.dp))

                    // 连续滑动调节
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

                    Spacer(modifier = Modifier.height(6.dp))

                    // 快速微调步进按钮
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
                        if (isWork) {
                            workMinutes = tempMinutes
                            prefs.edit().putInt("pref_pomodoro_work_mins", tempMinutes).apply()
                        } else {
                            breakMinutes = tempMinutes
                            prefs.edit().putInt("pref_pomodoro_break_mins", tempMinutes).apply()
                        }
                        PomodoroTimer.setDuration(status.mode, tempMinutes)
                        showCustomDialog = false
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                ) {
                    Text("保存设定", color = Color.Black, fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = { showCustomDialog = false }) {
                    Text("取消", color = Color.Gray)
                }
            }
        )
    }
}
