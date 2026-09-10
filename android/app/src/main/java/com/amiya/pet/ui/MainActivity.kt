@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.amiya.pet.ui

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.core.content.ContextCompat
import com.amiya.pet.core.update.DownloadProgress
import com.amiya.pet.core.update.ReleaseInfo
import com.amiya.pet.core.update.UpdateManager
import com.amiya.pet.service.AppBackgroundService
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
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

        // 启动前台服务
        val serviceIntent = Intent(this, AppBackgroundService::class.java)
        ContextCompat.startForegroundService(this, serviceIntent)

        // 初始化主题偏好（-1: 跟随系统, 0: 浅色, 1: 深色）
        val prefs = getSharedPreferences("amiya_pet_prefs", Context.MODE_PRIVATE)
        val storedTheme = prefs.getInt("pref_theme", -1)
        val initialForce: Boolean? = when (storedTheme) {
            1 -> true
            0 -> false
            else -> null
        }
        val themeOverride = mutableStateOf(initialForce)

        setContent {
            val context = LocalContext.current
            val scope = rememberCoroutineScope()
            var showUpdateDialog by remember { mutableStateOf(false) }
            var releaseInfo by remember { mutableStateOf<ReleaseInfo?>(null) }
            var isDownloading by remember { mutableStateOf(false) }
            var downloadProgress by remember { mutableStateOf<DownloadProgress?>(null) }
            var downloadJob by remember { mutableStateOf<Job?>(null) }

            // 自动检查更新
            LaunchedEffect(Unit) {
                val result = UpdateManager.checkUpdate(context)
                if (result.isSuccess) {
                    val info = result.getOrNull()
                    if (info != null && info.hasUpdate) {
                        releaseInfo = info
                        showUpdateDialog = true
                    }
                }
            }

            val isDark = themeOverride.value ?: isSystemInDarkTheme()

            fun triggerCheckUpdate() {
                scope.launch {
                    Toast.makeText(context, "正在检查更新...", Toast.LENGTH_SHORT).show()
                    val res = UpdateManager.checkUpdate(context)
                    val currentVer = UpdateManager.getCurrentVersion(context)
                    if (res.isSuccess) {
                        val info = res.getOrNull()
                        if (info != null) {
                            releaseInfo = info
                            showUpdateDialog = true
                        } else {
                            Toast.makeText(context, "当前已是最新版本 (v$currentVer)", Toast.LENGTH_SHORT).show()
                        }
                    } else {
                        val err = res.exceptionOrNull()?.localizedMessage ?: "网络异常"
                        Toast.makeText(context, "检查更新失败: $err", Toast.LENGTH_SHORT).show()
                    }
                }
            }

            fun toggleTheme() {
                val newVal = when (themeOverride.value) {
                    null -> true
                    true -> false
                    false -> null
                }
                themeOverride.value = newVal
                val intVal = when (newVal) {
                    true -> 1
                    false -> 0
                    null -> -1
                }
                prefs.edit().putInt("pref_theme", intVal).apply()
            }

            AmiyaPetTheme(forceDark = themeOverride.value) {
                var selectedTab by remember { mutableStateOf(MainTab.CHAT) }
                var pendingChatPrompt by remember { mutableStateOf<String?>(null) }

                Scaffold(
                    topBar = {
                        if (selectedTab != MainTab.CHAT) {
                            TopAppBar(
                                title = {
                                    Text(
                                        when (selectedTab) {
                                            MainTab.SCHEDULE -> "课表管理"
                                            MainTab.NOTES -> "灵感便签"
                                            MainTab.FOCUS -> "专注番茄钟"
                                            else -> ""
                                        },
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 18.sp
                                    )
                                },
                                actions = {
                                    IconButton(onClick = { triggerCheckUpdate() }) {
                                        Icon(Icons.Default.CloudDownload, contentDescription = "检查更新", tint = MaterialTheme.colorScheme.onSurface)
                                    }
                                    IconButton(onClick = { toggleTheme() }) {
                                        if (isDark) {
                                            Icon(Icons.Default.Brightness7, contentDescription = "切换到浅色模式", tint = MaterialTheme.colorScheme.onSurface)
                                        } else {
                                            Icon(Icons.Default.Brightness4, contentDescription = "切换到深色模式", tint = MaterialTheme.colorScheme.onSurface)
                                        }
                                    }
                                },
                                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.surface)
                            )
                        }
                    },
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
                            MainTab.SCHEDULE -> ScheduleScreen(
                                onConsultAi = { prompt ->
                                    pendingChatPrompt = prompt
                                    selectedTab = MainTab.CHAT
                                }
                            )
                            MainTab.NOTES -> NotesScreen()
                            MainTab.CHAT -> ChatScreen(
                                onCheckUpdate = { triggerCheckUpdate() },
                                onToggleTheme = { toggleTheme() },
                                isDark = isDark,
                                initialPrompt = pendingChatPrompt,
                                onConsumeInitialPrompt = { pendingChatPrompt = null }
                            )
                            MainTab.FOCUS -> PomodoroScreen()
                        }
                    }
                }

                // Update dialog
                if (showUpdateDialog && releaseInfo != null) {
                    val currentVer = UpdateManager.getCurrentVersion(context)
                    val isNewer = releaseInfo!!.hasUpdate
                    AlertDialog(
                        onDismissRequest = { if (!isDownloading) showUpdateDialog = false },
                        containerColor = MaterialTheme.colorScheme.surface,
                        title = {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    imageVector = if (isNewer) Icons.Default.CloudDownload else Icons.Default.CheckCircle,
                                    contentDescription = null,
                                    tint = if (isNewer) MaterialTheme.colorScheme.primary else Color(0xFF4CAF50),
                                    modifier = Modifier.size(24.dp)
                                )
                                Spacer(Modifier.width(8.dp))
                                Column {
                                    Text(
                                        text = if (isNewer) "发现新版本 v${releaseInfo!!.versionName}" else "已是最新版本 (v$currentVer)",
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 17.sp,
                                        color = MaterialTheme.colorScheme.onSurface
                                    )
                                    if (isNewer) {
                                        Text(
                                            text = "当前安装版本: v$currentVer",
                                            fontSize = 12.sp,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                    }
                                }
                            }
                        },
                        text = {
                            Column(modifier = Modifier.fillMaxWidth()) {
                                Text(
                                    text = if (isNewer) "✨ 新版本更新内容：" else "✨ 本版更新日志：",
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 13.sp,
                                    color = MaterialTheme.colorScheme.primary
                                )
                                Spacer(Modifier.height(8.dp))
                                Surface(
                                    shape = RoundedCornerShape(8.dp),
                                    color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .heightIn(max = 240.dp)
                                ) {
                                    Column(
                                        modifier = Modifier
                                            .padding(12.dp)
                                            .verticalScroll(rememberScrollState())
                                    ) {
                                        Text(
                                            text = releaseInfo!!.releaseNotes.ifBlank { "包含多项性能优化与细节改进。" },
                                            fontSize = 13.sp,
                                            lineHeight = 20.sp,
                                            color = MaterialTheme.colorScheme.onSurface
                                        )
                                    }
                                }
                                if (isDownloading && downloadProgress != null) {
                                    Spacer(Modifier.height(14.dp))
                                    LinearProgressIndicator(progress = { downloadProgress!!.progress }, modifier = Modifier.fillMaxWidth())
                                    Spacer(Modifier.height(6.dp))
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween
                                    ) {
                                        Text(
                                            text = "${downloadProgress!!.downloadedBytes / 1024 / 1024}MB / ${downloadProgress!!.totalBytes / 1024 / 1024}MB",
                                            fontSize = 12.sp,
                                            color = Color.Gray
                                        )
                                        Text(
                                            text = downloadProgress!!.formattedSpeed(),
                                            fontSize = 12.sp,
                                            color = MaterialTheme.colorScheme.primary
                                        )
                                    }
                                }
                            }
                        },
                        confirmButton = {
                            if (isNewer) {
                                if (!isDownloading) {
                                    Button(onClick = {
                                        isDownloading = true
                                        downloadJob = scope.launch {
                                            val apkUrl = releaseInfo!!.apkDownloadUrl
                                            if (!apkUrl.isNullOrEmpty()) {
                                                val res = UpdateManager.downloadApk(context, apkUrl) { prog ->
                                                    downloadProgress = prog
                                                }
                                                if (res.isSuccess) {
                                                    isDownloading = false
                                                    showUpdateDialog = false
                                                    UpdateManager.installApk(context, res.getOrThrow())
                                                } else {
                                                    isDownloading = false
                                                }
                                            } else {
                                                isDownloading = false
                                            }
                                        }
                                    }) {
                                        Text("立即更新")
                                    }
                                }
                            } else {
                                Button(onClick = { showUpdateDialog = false }) {
                                    Text("好的")
                                }
                            }
                        },
                        dismissButton = {
                            if (isNewer) {
                                if (!isDownloading) {
                                    TextButton(onClick = { showUpdateDialog = false }) {
                                        Text("稍后再说", color = Color.Gray)
                                    }
                                } else {
                                    TextButton(onClick = {
                                        downloadJob?.cancel()
                                        isDownloading = false
                                    }) {
                                        Text("取消下载", color = Color.Red)
                                    }
                                }
                            }
                        }
                    )
                }
            }
        }
    }
}

@Composable
fun AmiyaPetTheme(forceDark: Boolean? = null, content: @Composable () -> Unit) {
    val dark = forceDark ?: isSystemInDarkTheme()
    val colors = if (dark) {
        darkColorScheme(
            primary = Color(0xFF00B0FF),
            onPrimary = Color.Black,
            secondary = Color(0xFF4FC3F7),
            background = Color(0xFF101216),
            surface = Color(0xFF1A1D24),
            surfaceVariant = Color(0xFF242832),
            onBackground = Color(0xFFE2E8F0),
            onSurface = Color(0xFFE2E8F0),
            error = Color(0xFFFF5252)
        )
    } else {
        lightColorScheme(
            primary = Color(0xFF00B0FF),
            onPrimary = Color.Black,
            secondary = Color(0xFF4FC3F7),
            background = Color(0xFFF0F0F0),
            surface = Color(0xFFFFFFFF),
            surfaceVariant = Color(0xFFE2E8F0),
            onBackground = Color(0xFF101216),
            onSurface = Color(0xFF101216),
            error = Color(0xFFFF5252)
        )
    }
    MaterialTheme(colorScheme = colors, content = content)
}

enum class MainTab(val title: String, val icon: ImageVector) {
    SCHEDULE("课表", Icons.Default.DateRange),
    NOTES("便签", Icons.Default.EditNote),
    CHAT("对话", Icons.Default.Chat),
    FOCUS("专注", Icons.Default.Timer)
}

@Composable
fun GuideItem(title: String, desc: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.Top
    ) {
        Text("• ", color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
        Column {
            Text(title, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
            Text(desc, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))
        }
    }
}
