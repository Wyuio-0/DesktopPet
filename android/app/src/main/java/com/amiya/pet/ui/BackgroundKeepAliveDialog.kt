@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.amiya.pet.ui

import android.content.Intent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.amiya.pet.core.system.BatteryOptimizationHelper
import com.amiya.pet.service.AppBackgroundService

/**
 * Material 3 风格的后台保活与时间准点守护引导弹窗
 * 引导用户授予「忽略电池优化（无限制后台）」、「精准闹钟」并展示品牌防杀后台指引。
 */
@Composable
fun BackgroundKeepAliveDialog(
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    var checkTrigger by remember { mutableIntStateOf(0) }
    var isIgnoringBattery by remember { mutableStateOf(BatteryOptimizationHelper.isIgnoringBatteryOptimizations(context)) }
    var canScheduleAlarm by remember { mutableStateOf(BatteryOptimizationHelper.canScheduleExactAlarms(context)) }
    val isServiceRunning by AppBackgroundService.isRunning.collectAsState()

    // 页面从系统设置切回时，自动刷新权限与优化状态
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                isIgnoringBattery = BatteryOptimizationHelper.isIgnoringBatteryOptimizations(context)
                canScheduleAlarm = BatteryOptimizationHelper.canScheduleExactAlarms(context)
                checkTrigger++
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
        }
    }

    val brandGuide = remember { BatteryOptimizationHelper.getBrandGuide() }
    var isGuideExpanded by remember { mutableStateOf(true) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(36.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.15f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        Icons.Default.Security,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(20.dp)
                    )
                }
                Spacer(Modifier.width(10.dp))
                Column {
                    Text("后台保活与准点守护", fontSize = 17.sp, fontWeight = FontWeight.Bold)
                    Text("解决休眠冻结，确保提醒与番茄钟准时", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    text = "Android 系统的智能省电策略在锁屏后会冻结后台应用，导致课表提醒延迟、番茄钟倒计时变慢或小组件不刷新。建议完成以下配置：",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    lineHeight = 17.sp
                )

                // 卡片 1: 忽略电池优化 (后台无限制运行)
                KeepAliveItemCard(
                    icon = Icons.Default.BatteryChargingFull,
                    title = "忽略电池优化 (后台无限制)",
                    desc = "允许阿米娅在锁屏休眠时不受 Android Doze 深度休眠限制。",
                    isOk = isIgnoringBattery,
                    okText = "已开启 (无限制)",
                    actionText = "去开启无限制",
                    onAction = {
                        BatteryOptimizationHelper.requestIgnoreBatteryOptimizations(context)
                    }
                )

                // 卡片 2: 精准闹钟调度权限
                KeepAliveItemCard(
                    icon = Icons.Default.Alarm,
                    title = "精准闹钟调度权限",
                    desc = "保障上课提醒、下课关怀及番茄钟倒计时分秒不差准时唤醒响铃。",
                    isOk = canScheduleAlarm,
                    okText = "已允许调度",
                    actionText = "去开启权限",
                    onAction = {
                        BatteryOptimizationHelper.requestExactAlarmPermission(context)
                    }
                )

                // 卡片 3: 后台常驻前台服务
                KeepAliveItemCard(
                    icon = Icons.Default.NotificationsActive,
                    title = "后台守护常驻服务",
                    desc = "在通知栏保持低内存防杀保活，持续更新桌面小组件与桌宠。",
                    isOk = isServiceRunning,
                    okText = "服务运行中",
                    actionText = "启动守护服务",
                    onAction = {
                        val sIntent = Intent(context, AppBackgroundService::class.java)
                        ContextCompat.startForegroundService(context, sIntent)
                    }
                )

                // 卡片 4: 品牌专属防杀后台指南
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { isGuideExpanded = !isGuideExpanded },
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    Icons.Default.PhoneAndroid,
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.primary,
                                    modifier = Modifier.size(18.dp)
                                )
                                Spacer(Modifier.width(6.dp))
                                Text(
                                    brandGuide.brandName,
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }
                            Icon(
                                if (isGuideExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.size(18.dp)
                            )
                        }

                        AnimatedVisibility(visible = isGuideExpanded) {
                            Column(modifier = Modifier.padding(top = 8.dp)) {
                                Text(
                                    "各大厂商系统省电策略较严，建议一并配置：",
                                    fontSize = 11.sp,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                                Spacer(Modifier.height(6.dp))
                                brandGuide.steps.forEach { step ->
                                    Text(
                                        step,
                                        fontSize = 11.sp,
                                        color = MaterialTheme.colorScheme.onSurface,
                                        lineHeight = 16.sp,
                                        modifier = Modifier.padding(vertical = 2.dp)
                                    )
                                }
                                Spacer(Modifier.height(8.dp))
                                OutlinedButton(
                                    onClick = { BatteryOptimizationHelper.openVendorPowerSettings(context) },
                                    modifier = Modifier.fillMaxWidth(),
                                    shape = RoundedCornerShape(8.dp),
                                    contentPadding = PaddingValues(vertical = 6.dp)
                                ) {
                                    Icon(Icons.Default.OpenInNew, contentDescription = null, modifier = Modifier.size(14.dp))
                                    Spacer(Modifier.width(6.dp))
                                    Text("打开系统应用/省电设置页", fontSize = 12.sp)
                                }
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = onDismiss,
                shape = RoundedCornerShape(10.dp)
            ) {
                Text("我已知晓 / 完成")
            }
        }
    )
}

@Composable
private fun KeepAliveItemCard(
    icon: ImageVector,
    title: String,
    desc: String,
    isOk: Boolean,
    okText: String,
    actionText: String,
    onAction: () -> Unit
) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f)) {
                    Icon(
                        icon,
                        contentDescription = null,
                        tint = if (isOk) Color(0xFF10B981) else Color(0xFFF59E0B),
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(Modifier.width(6.dp))
                    Text(title, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                }

                Surface(
                    shape = RoundedCornerShape(6.dp),
                    color = if (isOk) Color(0xFF10B981).copy(alpha = 0.15f) else Color(0xFFF59E0B).copy(alpha = 0.15f)
                ) {
                    Text(
                        if (isOk) okText else "待配置",
                        color = if (isOk) Color(0xFF059669) else Color(0xFFD97706),
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                    )
                }
            }

            Spacer(Modifier.height(4.dp))
            Text(desc, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, lineHeight = 15.sp)

            if (!isOk) {
                Spacer(Modifier.height(8.dp))
                Button(
                    onClick = onAction,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(8.dp),
                    contentPadding = PaddingValues(vertical = 4.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                ) {
                    Text(actionText, fontSize = 12.sp)
                }
            }
        }
    }
}
