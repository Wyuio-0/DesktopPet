package com.amiya.pet.ui

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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.amiya.pet.core.focus.PomodoroMode
import com.amiya.pet.core.focus.PomodoroState
import com.amiya.pet.core.focus.PomodoroTimer

@Composable
fun PomodoroScreen() {
    val status by PomodoroTimer.status.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        // 顶部标题
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = "阿米娅专注番茄钟",
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "让阿米娅陪伴博士高效工作与沉浸学习",
                fontSize = 12.sp,
                color = Color.Gray
            )
        }

        // 模式切换选择
        Row(
            modifier = Modifier
                .clip(RoundedCornerShape(20.dp))
                .background(MaterialTheme.colorScheme.surface)
                .padding(4.dp),
            horizontalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            FilterChip(
                selected = status.mode == PomodoroMode.WORK,
                onClick = { if (status.state != PomodoroState.RUNNING) PomodoroTimer.startFocus(25) },
                label = { Text("25分钟 专注") },
                colors = FilterChipDefaults.filterChipColors(
                    selectedContainerColor = MaterialTheme.colorScheme.primary,
                    selectedLabelColor = Color.Black
                )
            )
            FilterChip(
                selected = status.mode == PomodoroMode.SHORT_BREAK,
                onClick = { if (status.state != PomodoroState.RUNNING) PomodoroTimer.startBreak(5) },
                label = { Text("5分钟 小憩") },
                colors = FilterChipDefaults.filterChipColors(
                    selectedContainerColor = MaterialTheme.colorScheme.primary,
                    selectedLabelColor = Color.Black
                )
            )
        }

        // 倒计时表盘
        Box(
            contentAlignment = Alignment.Center,
            modifier = Modifier.size(240.dp)
        ) {
            CircularProgressIndicator(
                progress = { status.progress },
                modifier = Modifier.fillMaxSize(),
                strokeWidth = 10.dp,
                color = if (status.mode == PomodoroMode.WORK) MaterialTheme.colorScheme.primary else Color(0xFF4CAF50),
                trackColor = Color(0xFF222834)
            )
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    text = status.formattedTime,
                    fontSize = 44.sp,
                    fontWeight = FontWeight.ExtraBold,
                    color = Color.White
                )
                Text(
                    text = when (status.state) {
                        PomodoroState.RUNNING -> "正在专注中..."
                        PomodoroState.PAUSED -> "已暂停"
                        PomodoroState.COMPLETED -> "本次已完成！"
                        PomodoroState.IDLE -> "准备就绪"
                    },
                    fontSize = 13.sp,
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
                        PomodoroState.RUNNING -> "博士，沉浸于当下，25分钟后我们一起休息！阿米娅会在身侧守护您。"
                        PomodoroState.COMPLETED -> "太棒了博士！本次专注圆满完成，放下手头工作喝杯温水吧！"
                        else -> "开始一段专注旅程吧，博士。罗德岛期待您的高光时刻。"
                    },
                    fontSize = 12.sp,
                    color = Color(0xFFECEFF1)
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
                        onClick = { PomodoroTimer.startFocus(25) },
                        modifier = Modifier
                            .height(52.dp)
                            .widthIn(min = 160.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                    ) {
                        Icon(Icons.Default.PlayArrow, contentDescription = null, tint = Color.Black)
                        Spacer(modifier = Modifier.width(6.dp))
                        Text("开始专注", color = Color.Black, fontWeight = FontWeight.Bold, fontSize = 16.sp)
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
                        onClick = { PomodoroTimer.reset() },
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
                        onClick = { PomodoroTimer.reset() },
                        modifier = Modifier.height(52.dp)
                    ) {
                        Text("重置")
                    }
                }
            }
        }
    }
}
