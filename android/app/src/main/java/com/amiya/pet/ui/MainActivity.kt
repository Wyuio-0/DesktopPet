package com.amiya.pet.ui

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.amiya.pet.core.parser.CharacterParser
import com.amiya.pet.core.update.ReleaseInfo
import com.amiya.pet.core.update.UpdateManager
import com.amiya.pet.service.PetFloatingService
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* granted or denied */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 请求 Android 13+ 通知权限
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) {
                notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        setContent {
            AmiyaPetTheme {
                MainScreen()
            }
        }
    }
}

@Composable
fun AmiyaPetTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Color(0xFF00B0FF),
            onPrimary = Color.Black,
            secondary = Color(0xFF4FC3F7),
            background = Color(0xFF101216),
            surface = Color(0xFF1A1D24),
            surfaceVariant = Color(0xFF242832),
            onBackground = Color(0xFFE2E8F0),
            onSurface = Color(0xFFE2E8F0),
            error = Color(0xFFFF5252)
        ),
        content = content
    )
}

enum class MainTab(val title: String, val icon: ImageVector) {
    PET("桌宠", Icons.Default.Pets),
    NOTES("便签", Icons.Default.EditNote),
    CHAT("对话", Icons.Default.Chat),
    FOCUS("专注", Icons.Default.Timer)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen() {
    var selectedTab by remember { mutableStateOf(MainTab.PET) }

    Scaffold(
        bottomBar = {
            NavigationBar(
                containerColor = MaterialTheme.colorScheme.surface,
                tonalElevation = 8.dp
            ) {
                MainTab.values().forEach { tab ->
                    NavigationBarItem(
                        icon = { Icon(tab.icon, contentDescription = tab.title) },
                        label = { Text(tab.title, fontSize = 12.sp) },
                        selected = selectedTab == tab,
                        onClick = { selectedTab = tab },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = Color.Black,
                            selectedTextColor = MaterialTheme.colorScheme.primary,
                            indicatorColor = MaterialTheme.colorScheme.primary,
                            unselectedIconColor = Color.Gray,
                            unselectedTextColor = Color.Gray
                        )
                    )
                }
            }
        },
        containerColor = MaterialTheme.colorScheme.background
    ) { padding ->
        Box(modifier = Modifier.padding(padding)) {
            when (selectedTab) {
                MainTab.PET -> PetDashboardTab()
                MainTab.NOTES -> NotesScreen()
                MainTab.CHAT -> ChatScreen()
                MainTab.FOCUS -> PomodoroScreen()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PetDashboardTab() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val prefs = remember { context.getSharedPreferences("amiya_pet_prefs", Context.MODE_PRIVATE) }

    // 观察服务运行状态
    val isRunning by PetFloatingService.isRunning.collectAsState()
    val activeCharKey by PetFloatingService.currentCharKey.collectAsState()
    val activeSpeed by PetFloatingService.currentSpeed.collectAsState()
    val activeVolume by PetFloatingService.voiceVolume.collectAsState()
    val isVoiceMuted by PetFloatingService.isVoiceMuted.collectAsState()

    var selectedChar by remember {
        mutableStateOf(prefs.getString("pref_character", activeCharKey) ?: "amiya")
    }
    var currentSpeed by remember {
        mutableFloatStateOf(prefs.getFloat("pref_speed", activeSpeed))
    }
    var currentVolume by remember {
        mutableFloatStateOf(prefs.getFloat("pref_voice_volume", activeVolume))
    }
    var currentMuted by remember {
        mutableStateOf(prefs.getBoolean("pref_voice_muted", isVoiceMuted))
    }

    var hasOverlayPermission by remember {
        mutableStateOf(Settings.canDrawOverlays(context))
    }

    // 版本检查更新状态
    var isCheckingUpdate by remember { mutableStateOf(false) }
    var updateResult by remember { mutableStateOf<ReleaseInfo?>(null) }
    var updateStatusText by remember { mutableStateOf<String?>(null) }
    var showUpdateDialog by remember { mutableStateOf(false) }

    DisposableEffect(Unit) {
        hasOverlayPermission = Settings.canDrawOverlays(context)
        onDispose { }
    }

    val availableChars = remember {
        val list = CharacterParser.listCharacters(context).map { key ->
            val char = CharacterParser.loadCharacter(context, key)
            key to (char?.displayName ?: when (key) {
                "yuyuananjielina" -> "予愿安洁莉娜"
                "shenglinchuxue" -> "圣聆初雪"
                else -> "阿米娅"
            })
        }
        if (list.isNotEmpty()) list else listOf(
            "amiya" to "阿米娅",
            "yuyuananjielina" to "予愿安洁莉娜",
            "shenglinchuxue" to "圣聆初雪"
        )
    }

    val currentVersionName = remember { UpdateManager.getCurrentVersion(context) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // 顶部标题栏
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "阿米娅桌宠",
                    fontWeight = FontWeight.Bold,
                    fontSize = 22.sp,
                    color = Color.White
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "v$currentVersionName",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.primary
                )
            }
        }

        // 权限提示卡片（未授权时显示）
        if (!hasOverlayPermission) {
            Card(
                colors = CardDefaults.cardColors(containerColor = Color(0xFF332015)),
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Warning,
                            contentDescription = null,
                            tint = Color(0xFFFFB74D)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "需要开启悬浮窗权限",
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFFFFB74D),
                            fontSize = 16.sp
                        )
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = "为了让阿米娅能够在其他应用上层陪伴您，请前往系统设置授予“显示在其他应用上层”权限。",
                        color = Color(0xFFE0E0E0),
                        fontSize = 13.sp
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Button(
                        onClick = {
                            val intent = Intent(
                                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                                Uri.parse("package:${context.packageName}")
                            )
                            context.startActivity(intent)
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFF9800)),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text("前往系统授权", color = Color.Black, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }

        // 桌宠主控开关卡片
        Card(
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = "桌宠状态",
                            fontWeight = FontWeight.Bold,
                            fontSize = 16.sp,
                            color = Color.White
                        )
                        Text(
                            text = if (isRunning) "阿米娅正在桌面上陪伴您" else "桌宠当前处于收回状态",
                            fontSize = 13.sp,
                            color = if (isRunning) Color(0xFF4CAF50) else Color.Gray
                        )
                    }
                    Switch(
                        checked = isRunning,
                        onCheckedChange = { enable ->
                            hasOverlayPermission = Settings.canDrawOverlays(context)
                            if (!hasOverlayPermission) {
                                val intent = Intent(
                                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                                    Uri.parse("package:${context.packageName}")
                                )
                                context.startActivity(intent)
                                return@Switch
                            }

                            val serviceIntent = Intent(context, PetFloatingService::class.java).apply {
                                if (enable) {
                                    action = PetFloatingService.ACTION_START
                                    putExtra(PetFloatingService.EXTRA_CHAR_KEY, selectedChar)
                                    putExtra(PetFloatingService.EXTRA_SPEED, currentSpeed)
                                    putExtra(PetFloatingService.EXTRA_VOLUME, currentVolume)
                                    putExtra(PetFloatingService.EXTRA_MUTE, currentMuted)
                                } else {
                                    action = PetFloatingService.ACTION_STOP
                                }
                            }

                            if (enable) {
                                ContextCompat.startForegroundService(context, serviceIntent)
                            } else {
                                context.stopService(serviceIntent)
                            }
                        }
                    )
                }
            }
        }

        // 角色选择卡片
        Card(
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    text = "干员选择",
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp,
                    color = Color.White
                )
                Spacer(modifier = Modifier.height(12.dp))

                availableChars.forEach { (key, name) ->
                    val isSelected = (key == selectedChar)
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp)
                            .clip(RoundedCornerShape(12.dp))
                            .background(
                                if (isSelected) MaterialTheme.colorScheme.primary.copy(alpha = 0.15f)
                                else MaterialTheme.colorScheme.surfaceVariant
                            )
                            .clickable {
                                selectedChar = key
                                prefs.edit().putString("pref_character", key).apply()
                                if (isRunning) {
                                    val intent = Intent(context, PetFloatingService::class.java).apply {
                                        action = PetFloatingService.ACTION_SWITCH_CHARACTER
                                        putExtra(PetFloatingService.EXTRA_CHAR_KEY, key)
                                    }
                                    context.startService(intent)
                                }
                            }
                            .padding(horizontal = 16.dp, vertical = 14.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = name,
                                fontSize = 15.sp,
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                color = if (isSelected) MaterialTheme.colorScheme.primary else Color.White
                            )
                            if (isSelected) {
                                Icon(
                                    imageVector = Icons.Default.Check,
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.primary
                                )
                            }
                        }
                    }
                }
            }
        }

        // 角色原声音效卡片
        Card(
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = "角色原声音效",
                            fontWeight = FontWeight.Bold,
                            fontSize = 16.sp,
                            color = Color.White
                        )
                        Text(
                            text = if (currentMuted) "已静音" else "点击/双击互动播放专属台词",
                            fontSize = 12.sp,
                            color = Color.Gray
                        )
                    }
                    Switch(
                        checked = !currentMuted,
                        onCheckedChange = { unmuted ->
                            val muted = !unmuted
                            currentMuted = muted
                            prefs.edit().putBoolean("pref_voice_muted", muted).apply()
                            if (isRunning) {
                                val intent = Intent(context, PetFloatingService::class.java).apply {
                                    action = PetFloatingService.ACTION_SET_MUTE
                                    putExtra(PetFloatingService.EXTRA_MUTE, muted)
                                }
                                context.startService(intent)
                            }
                        }
                    )
                }

                if (!currentMuted) {
                    Spacer(modifier = Modifier.height(10.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("音量大小", fontSize = 13.sp, color = Color.LightGray)
                        Text("${(currentVolume * 100).toInt()}%", fontSize = 13.sp, color = MaterialTheme.colorScheme.primary)
                    }
                    Slider(
                        value = currentVolume,
                        onValueChange = { vol ->
                            currentVolume = vol
                            prefs.edit().putFloat("pref_voice_volume", vol).apply()
                            if (isRunning) {
                                val intent = Intent(context, PetFloatingService::class.java).apply {
                                    action = PetFloatingService.ACTION_SET_VOLUME
                                    putExtra(PetFloatingService.EXTRA_VOLUME, vol)
                                }
                                context.startService(intent)
                            }
                        },
                        valueRange = 0.1f..1.0f
                    )
                }
            }
        }

        // 动作速率调节
        Card(
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "动作播放速度",
                        fontWeight = FontWeight.Bold,
                        fontSize = 16.sp,
                        color = Color.White
                    )
                    Text(
                        text = "%.2fx".format(currentSpeed),
                        color = MaterialTheme.colorScheme.primary,
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp
                    )
                }
                Spacer(modifier = Modifier.height(8.dp))

                Slider(
                    value = currentSpeed,
                    onValueChange = { speed ->
                        currentSpeed = speed
                        prefs.edit().putFloat("pref_speed", speed).apply()
                        if (isRunning) {
                            val intent = Intent(context, PetFloatingService::class.java).apply {
                                action = PetFloatingService.ACTION_SET_SPEED
                                putExtra(PetFloatingService.EXTRA_SPEED, speed)
                            }
                            context.startService(intent)
                        }
                    },
                    valueRange = 0.5f..2.0f,
                    steps = 14
                )

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("0.5x (慢速)", fontSize = 11.sp, color = Color.Gray)
                    Text("1.15x (推荐流畅)", fontSize = 11.sp, color = MaterialTheme.colorScheme.primary)
                    Text("2.0x (极速)", fontSize = 11.sp, color = Color.Gray)
                }
            }
        }

        // 检查更新装置模块
        Card(
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = "版本检查与更新",
                            fontWeight = FontWeight.Bold,
                            fontSize = 16.sp,
                            color = Color.White
                        )
                        Text(
                            text = "当前版本：v$currentVersionName",
                            fontSize = 13.sp,
                            color = Color.Gray
                        )
                    }
                    Button(
                        onClick = {
                            if (isCheckingUpdate) return@Button
                            isCheckingUpdate = true
                            updateStatusText = "正在连接 GitHub..."
                            scope.launch {
                                val res = UpdateManager.checkUpdate(context)
                                isCheckingUpdate = false
                                res.fold(
                                    onSuccess = { info ->
                                        updateResult = info
                                        if (info.hasUpdate) {
                                            updateStatusText = "发现新版本：${info.tagName}"
                                            showUpdateDialog = true
                                        } else {
                                            updateStatusText = "已是最新版本 (v${info.versionName})"
                                            Toast.makeText(context, "当前已是最新版本！", Toast.LENGTH_SHORT).show()
                                        }
                                    },
                                    onFailure = { err ->
                                        updateStatusText = "检查更新失败: ${err.localizedMessage}"
                                        Toast.makeText(context, "检查更新失败，请检查网络", Toast.LENGTH_SHORT).show()
                                    }
                                )
                            }
                        },
                        enabled = !isCheckingUpdate,
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                    ) {
                        if (isCheckingUpdate) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(16.dp),
                                color = Color.Black,
                                strokeWidth = 2.dp
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text("检查中...", color = Color.Black, fontSize = 13.sp)
                        } else {
                            Icon(
                                imageVector = Icons.Default.Refresh,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp),
                                tint = Color.Black
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("检查更新", color = Color.Black, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                        }
                    }
                }

                if (updateStatusText != null) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = updateStatusText!!,
                        fontSize = 12.sp,
                        color = if (updateStatusText?.contains("失败") == true) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.secondary
                    )
                }
            }
        }

        // 手机端交互操作指南
        Card(
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    text = "手机交互指南",
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp,
                    color = Color.White
                )
                Spacer(modifier = Modifier.height(8.dp))
                GuideItem(title = "单击角色", desc = "触发互动反应动作并播放专属戳戳语音")
                GuideItem(title = "双击角色", desc = "向博士打招呼、弹出对话气泡并播放问候原声")
                GuideItem(title = "手指拖拽", desc = "在屏幕任意位置拖拽，松手后自动贴附两侧边缘")
                GuideItem(title = "智能休息", desc = "静止一段时间后自动进入坐下与睡眠状态")
                GuideItem(title = "熄屏节能", desc = "手机熄屏/锁屏时自动挂起 GPU 渲染，0 耗电")
            }
        }
    }

    // 新版本弹窗提醒
    if (showUpdateDialog && updateResult != null) {
        val info = updateResult!!
        AlertDialog(
            onDismissRequest = { showUpdateDialog = false },
            containerColor = MaterialTheme.colorScheme.surface,
            title = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.SystemUpdate,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "发现新版本 ${info.tagName}",
                        fontWeight = FontWeight.Bold,
                        fontSize = 18.sp,
                        color = Color.White
                    )
                }
            },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    Text(
                        text = "更新说明：",
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.primary,
                        fontSize = 13.sp
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = info.releaseNotes,
                        fontSize = 13.sp,
                        color = Color.LightGray
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        val targetUrl = info.apkDownloadUrl ?: info.htmlUrl
                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(targetUrl))
                        context.startActivity(intent)
                        showUpdateDialog = false
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                ) {
                    Text(
                        if (info.apkDownloadUrl != null) "立即下载 APK" else "前往 GitHub 查看",
                        color = Color.Black,
                        fontWeight = FontWeight.Bold
                    )
                }
            },
            dismissButton = {
                TextButton(onClick = { showUpdateDialog = false }) {
                    Text("稍后再说", color = Color.Gray)
                }
            }
        )
    }
}

@Composable
fun GuideItem(title: String, desc: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.Top
    ) {
        Text(
            text = "• ",
            color = MaterialTheme.colorScheme.primary,
            fontWeight = FontWeight.Bold
        )
        Column {
            Text(
                text = title,
                fontSize = 13.sp,
                fontWeight = FontWeight.SemiBold,
                color = Color.White
            )
            Text(
                text = desc,
                fontSize = 12.sp,
                color = Color.LightGray
            )
        }
    }
}
