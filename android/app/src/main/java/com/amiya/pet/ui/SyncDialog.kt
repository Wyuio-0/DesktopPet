@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.amiya.pet.ui

import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.amiya.pet.core.notes.NotesManager
import com.amiya.pet.core.schedule.ExamManager
import com.amiya.pet.core.schedule.ScheduleManager
import com.amiya.pet.core.sync.DeviceInfo
import com.amiya.pet.core.sync.PairRequest
import com.amiya.pet.core.sync.SyncManager
import kotlinx.coroutines.launch

/**
 * 罗德岛跨端协同与终端互联管理弹窗
 */
@Composable
fun SyncDialog(
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val scrollState = rememberScrollState()

    // 状态管理
    var localIp by remember { mutableStateOf(SyncManager.getLocalIpAddress()) }
    var isScanning by remember { mutableStateOf(false) }
    var discoveredDevices by remember { mutableStateOf<List<DeviceInfo>>(emptyList()) }
    var manualIp by remember { mutableStateOf("") }
    var syncStatusText by remember { mutableStateOf("就绪。") }
    var isOperating by remember { mutableStateOf(false) }

    // 已配对设备
    var trustedDevices by remember { mutableStateOf(SyncManager.getTrustedDevices(context)) }

    // 本地数据统计
    var courseCount by remember { mutableIntStateOf(ScheduleManager.courses.size) }
    var examCount by remember { mutableIntStateOf(ExamManager.exams.size) }
    var noteCount by remember { mutableIntStateOf(NotesManager.getInstance(context).notes.size) }

    // 快传输入
    var dropText by remember { mutableStateOf("") }

    // 监听收到的配对请求
    fun refreshStats() {
        courseCount = ScheduleManager.courses.size
        examCount = ExamManager.exams.size
        noteCount = NotesManager.getInstance(context).notes.size
        trustedDevices = SyncManager.getTrustedDevices(context)
        localIp = SyncManager.getLocalIpAddress()
    }

    var incomingPairRequest by remember { mutableStateOf<PairRequest?>(null) }
    DisposableEffect(Unit) {
        SyncManager.onPairRequestedListener = { req ->
            incomingPairRequest = req
        }
        SyncManager.onDevicesChangedListener = {
            refreshStats()
        }
        onDispose {
            SyncManager.onPairRequestedListener = null
            SyncManager.onDevicesChangedListener = null
        }
    }

    // ── 1. 收到配对请求时的专属认证弹窗（必须博士亲自核验确认）─────────────
    if (incomingPairRequest != null) {
        val req = incomingPairRequest!!
        AlertDialog(
            onDismissRequest = {
                SyncManager.confirmPairRequest(req.requestId, false)
                incomingPairRequest = null
            },
            icon = {
                Icon(Icons.Default.Security, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(36.dp))
            },
            title = {
                Text("罗德岛终端配对申请", fontWeight = FontWeight.Bold, fontSize = 18.sp, textAlign = TextAlign.Center)
            },
            text = {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        "检测到来自电脑终端的连接请求：",
                        fontSize = 13.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(Modifier.height(8.dp))

                    Surface(
                        shape = RoundedCornerShape(8.dp),
                        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Text("💻 设备名称：${req.clientName}", fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                            Spacer(Modifier.height(4.dp))
                            Text("🌐 设备地址：${req.clientIp}:${req.clientPort}", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }

                    Spacer(Modifier.height(14.dp))
                    Text("战术配对码 (PIN):", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.height(4.dp))

                    // 大字体居中展示配对码，如 "582 914"
                    val formattedPin = if (req.pin.length == 6) "${req.pin.substring(0, 3)} ${req.pin.substring(3)}" else req.pin
                    Text(
                        formattedPin,
                        fontSize = 28.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                        fontFamily = FontFamily.Monospace,
                        letterSpacing = 2.sp
                    )

                    Spacer(Modifier.height(12.dp))
                    Text(
                        "⚠️ 请核对电脑端显示的配对码是否完全一致。确认后将允许双向同步课表、考试、便签及剪贴板。",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.8f),
                        lineHeight = 16.sp
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        SyncManager.confirmPairRequest(req.requestId, true)
                        incomingPairRequest = null
                        refreshStats()
                        Toast.makeText(context, "已确认配对！双端互联已建立。", Toast.LENGTH_SHORT).show()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                ) {
                    Text("确认配对 (Accept)", fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                OutlinedButton(
                    onClick = {
                        SyncManager.confirmPairRequest(req.requestId, false)
                        incomingPairRequest = null
                        Toast.makeText(context, "已拒绝配对申请", Toast.LENGTH_SHORT).show()
                    }
                ) {
                    Text("拒绝 (Reject)")
                }
            }
        )
    }

    // ── 2. 主控制弹窗 ────────────────────────────────────────────────
    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Surface(
            shape = RoundedCornerShape(16.dp),
            color = MaterialTheme.colorScheme.surface,
            modifier = Modifier
                .fillMaxWidth(0.95f)
                .fillMaxHeight(0.9f)
                .padding(vertical = 12.dp)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp)
            ) {
                // 顶栏标题
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Surface(
                            shape = CircleShape,
                            color = MaterialTheme.colorScheme.primaryContainer,
                            modifier = Modifier.size(36.dp)
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(Icons.Default.Devices, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(20.dp))
                            }
                        }
                        Spacer(Modifier.width(10.dp))
                        Column {
                            Text("罗德岛跨端协同", fontSize = 17.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
                            Text("局域网双端互联 · 蓝牙式安全配对", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    IconButton(onClick = onDismiss) {
                        Icon(Icons.Default.Close, contentDescription = "关闭", tint = MaterialSchemeTint())
                    }
                }

                HorizontalDivider(modifier = Modifier.padding(vertical = 10.dp))

                Column(
                    modifier = Modifier
                        .weight(1f)
                        .verticalScroll(scrollState),
                    verticalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    // ── 卡片 1: 本机终端状态 ──
                    Card(
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f)),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Surface(shape = CircleShape, color = Color(0xFF4CAF50), modifier = Modifier.size(8.dp)) {}
                                Spacer(Modifier.width(6.dp))
                                Text("局域网服务运行中", fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = Color(0xFF4CAF50))
                                Spacer(Modifier.weight(1f))
                                Text("端口: ${SyncManager.localHttpPort}", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Spacer(Modifier.height(6.dp))
                            Text("本机 IP: $localIp", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }

                    // ── 卡片 2: 附近设备与搜索 ──
                    Card(
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                        modifier = Modifier
                            .fillMaxWidth()
                            .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(12.dp))
                    ) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.SpaceBetween,
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(Icons.Default.WifiTethering, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(18.dp))
                                    Spacer(Modifier.width(6.dp))
                                    Text("搜索电脑终端", fontSize = 14.sp, fontWeight = FontWeight.Bold)
                                }
                                Button(
                                    onClick = {
                                        if (!isScanning) {
                                            isScanning = true
                                            scope.launch {
                                                discoveredDevices = SyncManager.scanLanDevices()
                                                isScanning = false
                                            }
                                        }
                                    },
                                    enabled = !isScanning,
                                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                                    modifier = Modifier.height(34.dp)
                                ) {
                                    if (isScanning) {
                                        CircularProgressIndicator(modifier = Modifier.size(14.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
                                        Spacer(Modifier.width(6.dp))
                                        Text("雷达扫描中...", fontSize = 12.sp)
                                    } else {
                                        Text("🔍 扫描附近设备", fontSize = 12.sp)
                                    }
                                }
                            }

                            // 扫描结果列表
                            if (discoveredDevices.isNotEmpty()) {
                                Spacer(Modifier.height(10.dp))
                                Text("发现的设备 (点击发起配对):", fontSize = 12.sp, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold)
                                Spacer(Modifier.height(6.dp))
                                discoveredDevices.forEach { dev ->
                                    Surface(
                                        shape = RoundedCornerShape(8.dp),
                                        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f),
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(vertical = 3.dp)
                                            .clickable {
                                                scope.launch {
                                                    isOperating = true
                                                    syncStatusText = "正在向「${dev.deviceName}」发起配对请求，请在电脑屏幕上点击确认..."
                                                    val (ok, msg) = SyncManager.requestPairToRemote(context, dev.ip, dev.httpPort)
                                                    isOperating = false
                                                    syncStatusText = msg
                                                    refreshStats()
                                                    Toast.makeText(context, msg, Toast.LENGTH_SHORT).show()
                                                }
                                            }
                                    ) {
                                        Row(
                                            modifier = Modifier.padding(10.dp),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Icon(Icons.Default.LaptopMac, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(20.dp))
                                            Spacer(Modifier.width(8.dp))
                                            Column(modifier = Modifier.weight(1f)) {
                                                Text(dev.deviceName, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                                                Text("${dev.ip}:${dev.httpPort}", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                            }
                                            Text("请求配对 ➔", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                                        }
                                    }
                                }
                            }

                            Spacer(Modifier.height(10.dp))
                            // 直连 IP（应对 AP 隔离）
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                OutlinedTextField(
                                    value = manualIp,
                                    onValueChange = { manualIp = it },
                                    placeholder = { Text("直连 IP (如: 10.0.2.2 或 电脑IP)", fontSize = 12.sp) },
                                    singleLine = true,
                                    modifier = Modifier
                                        .weight(1f)
                                        .height(50.dp),
                                    textStyle = LocalTextStyle.current.copy(fontSize = 12.sp)
                                )
                                Spacer(Modifier.width(8.dp))
                                OutlinedButton(
                                    onClick = {
                                        if (manualIp.isNotBlank()) {
                                            scope.launch {
                                                isOperating = true
                                                var ip = manualIp.trim()
                                                var port = 23333
                                                if (ip.contains(":")) {
                                                    val parts = ip.split(":")
                                                    ip = parts[0]
                                                    port = parts[1].toIntOrNull() ?: 23333
                                                }
                                                syncStatusText = "正在直连探测 $ip:$port..."
                                                val (ok, msg) = SyncManager.requestPairToRemote(context, ip, port)
                                                isOperating = false
                                                syncStatusText = msg
                                                refreshStats()
                                                Toast.makeText(context, msg, Toast.LENGTH_SHORT).show()
                                            }
                                        } else {
                                            Toast.makeText(context, "请输入电脑 IP 地址", Toast.LENGTH_SHORT).show()
                                        }
                                    },
                                    enabled = !isOperating,
                                    modifier = Modifier.height(48.dp)
                                ) {
                                    Text("配对", fontSize = 12.sp)
                                }
                            }
                        }
                    }

                    // ── 卡片 3: 已配对信任设备 ──
                    Card(
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                        modifier = Modifier
                            .fillMaxWidth()
                            .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(12.dp))
                    ) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.VerifiedUser, contentDescription = null, tint = Color(0xFF4CAF50), modifier = Modifier.size(18.dp))
                                Spacer(Modifier.width(6.dp))
                                Text("已配对信任终端 (${trustedDevices.size})", fontSize = 14.sp, fontWeight = FontWeight.Bold)
                            }
                            Spacer(Modifier.height(8.dp))

                            if (trustedDevices.isEmpty()) {
                                Text("暂无已配对设备。请在上方搜索或输入 IP 进行蓝牙式配对。", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            } else {
                                trustedDevices.forEach { (devId, dev) ->
                                    Surface(
                                        shape = RoundedCornerShape(8.dp),
                                        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f),
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(vertical = 4.dp)
                                    ) {
                                        Row(
                                            modifier = Modifier.padding(10.dp),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Icon(Icons.Default.CheckCircle, contentDescription = null, tint = Color(0xFF4CAF50), modifier = Modifier.size(18.dp))
                                            Spacer(Modifier.width(8.dp))
                                            Column(modifier = Modifier.weight(1f)) {
                                                Text(dev.deviceName, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                                                Text("${dev.ip}:${dev.httpPort}", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                            }
                                            TextButton(
                                                onClick = {
                                                    SyncManager.unpairDevice(context, devId)
                                                    refreshStats()
                                                    Toast.makeText(context, "已解除配对", Toast.LENGTH_SHORT).show()
                                                }
                                            ) {
                                                Text("解除配对", fontSize = 12.sp, color = Color(0xFFFF5252))
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // ── 卡片 4: 一键学业数据同步 ──
                    Card(
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                        modifier = Modifier
                            .fillMaxWidth()
                            .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(12.dp))
                    ) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.Sync, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(18.dp))
                                Spacer(Modifier.width(6.dp))
                                Text("学业数据双向同步", fontSize = 14.sp, fontWeight = FontWeight.Bold)
                            }
                            Spacer(Modifier.height(8.dp))

                            Text(
                                "手机本地：课表 $courseCount 门 | 考试 $examCount 场 | 便签 $noteCount 篇",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = MaterialTheme.colorScheme.primary
                            )
                            Spacer(Modifier.height(10.dp))

                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Button(
                                    onClick = {
                                        if (trustedDevices.isEmpty()) {
                                            Toast.makeText(context, "请先配对电脑终端", Toast.LENGTH_SHORT).show()
                                            return@Button
                                        }
                                        val firstDev = trustedDevices.values.first()
                                        val token = SyncManager.getDeviceToken(context, firstDev.deviceId)
                                        scope.launch {
                                            isOperating = true
                                            syncStatusText = "正在双向合并同步..."
                                            // 1. Pull from PC
                                            val pullReport = SyncManager.syncPull(context, firstDev.ip, firstDev.httpPort, token)
                                            // 2. Push merged to PC
                                            val pushReport = SyncManager.syncPush(context, firstDev.ip, firstDev.httpPort, token, "replace")
                                            isOperating = false
                                            refreshStats()
                                            if (pullReport.success && pushReport.success) {
                                                syncStatusText = "🎉 双向全量同步已完成！"
                                                Toast.makeText(context, "学业数据同步成功！", Toast.LENGTH_SHORT).show()
                                            } else {
                                                syncStatusText = "同步未完全成功: ${pullReport.message}"
                                            }
                                        }
                                    },
                                    enabled = !isOperating && trustedDevices.isNotEmpty(),
                                    modifier = Modifier.weight(1f)
                                ) {
                                    Text("⚡ 一键双向合并", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                                }

                                OutlinedButton(
                                    onClick = {
                                        if (trustedDevices.isEmpty()) {
                                            Toast.makeText(context, "请先配对电脑终端", Toast.LENGTH_SHORT).show()
                                            return@OutlinedButton
                                        }
                                        val firstDev = trustedDevices.values.first()
                                        val token = SyncManager.getDeviceToken(context, firstDev.deviceId)
                                        scope.launch {
                                            isOperating = true
                                            syncStatusText = "正在从电脑拉取..."
                                            val report = SyncManager.syncPull(context, firstDev.ip, firstDev.httpPort, token)
                                            isOperating = false
                                            refreshStats()
                                            syncStatusText = report.message
                                            Toast.makeText(context, report.message, Toast.LENGTH_SHORT).show()
                                        }
                                    },
                                    enabled = !isOperating && trustedDevices.isNotEmpty()
                                ) {
                                    Text("📥 从电脑拉取", fontSize = 12.sp)
                                }

                                OutlinedButton(
                                    onClick = {
                                        if (trustedDevices.isEmpty()) {
                                            Toast.makeText(context, "请先配对电脑终端", Toast.LENGTH_SHORT).show()
                                            return@OutlinedButton
                                        }
                                        val firstDev = trustedDevices.values.first()
                                        val token = SyncManager.getDeviceToken(context, firstDev.deviceId)
                                        scope.launch {
                                            isOperating = true
                                            syncStatusText = "正在推送到电脑..."
                                            val report = SyncManager.syncPush(context, firstDev.ip, firstDev.httpPort, token, "replace")
                                            isOperating = false
                                            refreshStats()
                                            syncStatusText = report.message
                                            Toast.makeText(context, report.message, Toast.LENGTH_SHORT).show()
                                        }
                                    },
                                    enabled = !isOperating && trustedDevices.isNotEmpty()
                                ) {
                                    Text("📤 推送到电脑", fontSize = 12.sp)
                                }
                            }

                            Spacer(Modifier.height(6.dp))
                            Text(syncStatusText, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }

                    // ── 卡片 5: 罗德岛「战术快传」 ──
                    Card(
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                        modifier = Modifier
                            .fillMaxWidth()
                            .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(12.dp))
                    ) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.Send, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(18.dp))
                                Spacer(Modifier.width(6.dp))
                                Text("罗德岛「战术快传」(隔空传送至电脑)", fontSize = 14.sp, fontWeight = FontWeight.Bold)
                            }
                            Spacer(Modifier.height(8.dp))

                            OutlinedTextField(
                                value = dropText,
                                onValueChange = { dropText = it },
                                placeholder = { Text("输入要发送到电脑的文本或网址...", fontSize = 12.sp) },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(52.dp),
                                textStyle = LocalTextStyle.current.copy(fontSize = 12.sp)
                            )
                            Spacer(Modifier.height(8.dp))

                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Button(
                                    onClick = {
                                        if (dropText.isBlank()) {
                                            Toast.makeText(context, "请输入要发送的内容", Toast.LENGTH_SHORT).show()
                                            return@Button
                                        }
                                        if (trustedDevices.isEmpty()) {
                                            Toast.makeText(context, "请先配对电脑终端", Toast.LENGTH_SHORT).show()
                                            return@Button
                                        }
                                        val firstDev = trustedDevices.values.first()
                                        val token = SyncManager.getDeviceToken(context, firstDev.deviceId)
                                        scope.launch {
                                            val ok = SyncManager.sendClipboard(context, firstDev.ip, firstDev.httpPort, token, dropText)
                                            if (ok) {
                                                Toast.makeText(context, "🚀 快传成功！已送达电脑剪贴板", Toast.LENGTH_SHORT).show()
                                                dropText = ""
                                            } else {
                                                Toast.makeText(context, "快传失败，请检查电脑是否在线", Toast.LENGTH_SHORT).show()
                                            }
                                        }
                                    },
                                    enabled = trustedDevices.isNotEmpty(),
                                    modifier = Modifier.weight(1f)
                                ) {
                                    Text("🚀 发送文本到电脑", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                                }

                                OutlinedButton(
                                    onClick = {
                                        val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                                        val clip = cm.primaryClip
                                        if (clip != null && clip.itemCount > 0) {
                                            val text = clip.getItemAt(0).text?.toString() ?: ""
                                            if (text.isNotBlank()) {
                                                if (trustedDevices.isEmpty()) {
                                                    Toast.makeText(context, "请先配对电脑终端", Toast.LENGTH_SHORT).show()
                                                    return@OutlinedButton
                                                }
                                                val firstDev = trustedDevices.values.first()
                                                val token = SyncManager.getDeviceToken(context, firstDev.deviceId)
                                                scope.launch {
                                                    val ok = SyncManager.sendClipboard(context, firstDev.ip, firstDev.httpPort, token, text)
                                                    if (ok) {
                                                        Toast.makeText(context, "📋 已将手机剪贴板快传至电脑！", Toast.LENGTH_SHORT).show()
                                                    } else {
                                                        Toast.makeText(context, "快传失败，请检查电脑是否在线", Toast.LENGTH_SHORT).show()
                                                    }
                                                }
                                            } else {
                                                Toast.makeText(context, "手机剪贴板为空", Toast.LENGTH_SHORT).show()
                                            }
                                        } else {
                                            Toast.makeText(context, "手机剪贴板为空", Toast.LENGTH_SHORT).show()
                                        }
                                    },
                                    enabled = trustedDevices.isNotEmpty()
                                ) {
                                    Text("📋 发送手机剪贴板", fontSize = 12.sp)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun MaterialSchemeTint(): Color {
    return MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
}
