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

            AmiyaPetTheme(forceDark = themeOverride.value) {
                var selectedTab by remember { mutableStateOf(MainTab.CHAT) }

                Scaffold(
                    topBar = {
                        TopAppBar(
                            title = {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text("与桌宠互动", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                                }
                            },
                            actions = {
                                TextButton(onClick = {
                                    scope.launch {
                                        val res = UpdateManager.checkUpdate(context)
                                        if (res.isSuccess && res.getOrNull()?.hasUpdate == true) {
                                            releaseInfo = res.getOrNull()
                                            showUpdateDialog = true
                                        } else {
                                            Toast.makeText(context, "当前已是最新版本", Toast.LENGTH_SHORT).show()
                                        }
                                    }
                                }) {
                                    Text("检查更新", color = MaterialTheme.colorScheme.onSurface, fontSize = 14.sp)
                                }
                                IconButton(onClick = {
                                    // 循环切换主题状态
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
                                }) {
                                    if (themeOverride.value ?: isSystemInDarkTheme()) {
                                        Icon(Icons.Default.Brightness7, contentDescription = "切换到浅色模式", tint = MaterialTheme.colorScheme.onSurface)
                                    } else {
                                        Icon(Icons.Default.Brightness4, contentDescription = "切换到深色模式", tint = MaterialTheme.colorScheme.onSurface)
                                    }
                                }
                            },
                            colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.surface)
                        )
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
                            MainTab.SCHEDULE -> ScheduleScreen()
                            MainTab.NOTES -> NotesScreen()
                            MainTab.CHAT -> ChatScreen()
                            MainTab.FOCUS -> PomodoroScreen()
                        }
                    }
                }

                // Update dialog
                if (showUpdateDialog && releaseInfo != null) {
                    AlertDialog(
                        onDismissRequest = { if (!isDownloading) showUpdateDialog = false },
                        title = { Text("发现新版本: ${releaseInfo!!.versionName}", color = MaterialTheme.colorScheme.onSurface) },
                        text = {
                            Column {
                                Text(releaseInfo!!.releaseNotes, fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurface)
                                Spacer(Modifier.height(16.dp))
                                if (isDownloading && downloadProgress != null) {
                                    LinearProgressIndicator(progress = { downloadProgress!!.progress }, modifier = Modifier.fillMaxWidth())
                                    Spacer(Modifier.height(8.dp))
                                    Text(
                                        "${downloadProgress!!.downloadedBytes / 1024 / 1024}MB / ${downloadProgress!!.totalBytes / 1024 / 1024}MB",
                                        fontSize = 12.sp,
                                        color = Color.Gray
                                    )
                                }
                            }
                        },
                        confirmButton = {
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
                        },
                        dismissButton = {
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
            surfaceVariant = Color(0xFFF5F5F5),
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
            Text(title, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = Color.White)
            Text(desc, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurface)
        }
    }
}
