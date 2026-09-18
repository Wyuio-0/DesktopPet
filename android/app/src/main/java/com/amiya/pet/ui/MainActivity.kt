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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.core.content.ContextCompat
import com.amiya.pet.core.update.DownloadProgress
import com.amiya.pet.core.sync.SyncManager
import com.amiya.pet.core.update.ReleaseInfo
import com.amiya.pet.core.update.UpdateManager
import com.amiya.pet.core.schedule.ScheduleManager
import com.amiya.pet.floating.FloatingPetManager
import com.amiya.pet.service.AppBackgroundService
import com.amiya.pet.widget.ScheduleWidgetProvider
import java.util.Date
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
class MainActivity : ComponentActivity() {
    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* granted or denied */ }

    override fun onResume() {
        super.onResume()
        ScheduleWidgetProvider.sendUpdateBroadcast(this)
        FloatingPetManager.checkAndSync(this)
    }

    override fun onDestroy() {
        super.onDestroy()
        SyncManager.stop()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 启动跨端协同局域网互联服务
        SyncManager.start(this)
        SyncManager.onTacticalDropReceived = { text, title ->
            FloatingPetManager.showTacticalMessage(this@MainActivity, text)
        }

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

        // 预加载课表数据 (确保首屏直接显示课表时无需切页即可立即可用)
        ScheduleManager.load(this)

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
                var selectedTab by remember { mutableStateOf(MainTab.SCHEDULE) }
                var pendingChatPrompt by remember { mutableStateOf<String?>(null) }

                // 课表状态 (由顶栏周次选择器驱动)
                var scheduleWeek by remember { mutableIntStateOf(ScheduleManager.getWeekNo() ?: 1) }
                var showImportDialog by remember { mutableStateOf(false) }
                var showReminderDialog by remember { mutableStateOf(false) }
                var showAddCourseDialog by remember { mutableStateOf(false) }
                var showIcsExportDialog by remember { mutableStateOf(false) }
                var showExamScheduleView by remember { mutableStateOf(false) }
                var showSyncDialog by remember { mutableStateOf(false) }
                var showTermStartDialog by remember { mutableStateOf(false) }

                // 对话界面顶栏状态
                var showChatGuideDialog by remember { mutableStateOf(false) }
                var showChatSettingsDialog by remember { mutableStateOf(false) }
                var chatClearTrigger by remember { mutableIntStateOf(0) }

                fun toggleFloatingPet() {
                    val isCurrentlyEnabled = FloatingPetManager.isFloatingPetEnabled(context)
                    if (isCurrentlyEnabled) {
                        FloatingPetManager.setFloatingPetEnabled(context, false)
                        Toast.makeText(context, "桌面悬浮桌宠已关闭", Toast.LENGTH_SHORT).show()
                    } else {
                        if (!FloatingPetManager.canDrawOverlays(context)) {
                            Toast.makeText(context, "请先授予「显示在其他应用上层」悬浮窗权限", Toast.LENGTH_LONG).show()
                            FloatingPetManager.requestOverlayPermission(context)
                        } else {
                            FloatingPetManager.setFloatingPetEnabled(context, true)
                            Toast.makeText(context, "桌面悬浮桌宠已开启，可全屏自由拖拽", Toast.LENGTH_SHORT).show()
                        }
                    }
                }

                Scaffold(
                    topBar = {
                        if (selectedTab != MainTab.SCHEDULE || !showExamScheduleView) {
                            TopAppBar(
                                title = {
                                    when (selectedTab) {
                                        MainTab.SCHEDULE -> {
                                            // 课表管理：顶栏与周次选择合二为一，左右箭头紧贴周次，极大节省空间
                                            val realWeek = ScheduleManager.getWeekNo() ?: 1
                                            val isThisWeek = (scheduleWeek == realWeek)
                                            Row(verticalAlignment = Alignment.CenterVertically) {
                                                IconButton(
                                                    onClick = { if (scheduleWeek > 1) scheduleWeek-- },
                                                    modifier = Modifier.size(32.dp)
                                                ) {
                                                    Icon(Icons.Default.ChevronLeft, "上一周", tint = MaterialTheme.colorScheme.onSurface, modifier = Modifier.size(20.dp))
                                                }
                                                Spacer(Modifier.width(2.dp))
                                                Text(
                                                    "第 $scheduleWeek 周",
                                                    fontWeight = FontWeight.Bold,
                                                    fontSize = 17.sp,
                                                    color = MaterialTheme.colorScheme.onSurface
                                                )
                                                Spacer(Modifier.width(2.dp))
                                                IconButton(
                                                    onClick = { scheduleWeek++ },
                                                    modifier = Modifier.size(32.dp)
                                                ) {
                                                    Icon(Icons.Default.ChevronRight, "下一周", tint = MaterialTheme.colorScheme.onSurface, modifier = Modifier.size(20.dp))
                                                }
                                                if (isThisWeek) {
                                                    Surface(
                                                        shape = RoundedCornerShape(10.dp),
                                                        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.2f)
                                                    ) {
                                                        Text(
                                                            "本周",
                                                            color = MaterialTheme.colorScheme.primary,
                                                            fontSize = 11.sp,
                                                            fontWeight = FontWeight.Bold,
                                                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                                            maxLines = 1
                                                        )
                                                    }
                                                } else {
                                                    Surface(
                                                        shape = RoundedCornerShape(10.dp),
                                                        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.22f),
                                                        modifier = Modifier.clickable { scheduleWeek = realWeek }
                                                    ) {
                                                        Row(
                                                            verticalAlignment = Alignment.CenterVertically,
                                                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                                        ) {
                                                            Icon(Icons.Default.Today, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(12.dp))
                                                            Spacer(Modifier.width(2.dp))
                                                            Text("回本周", color = MaterialTheme.colorScheme.primary, fontSize = 11.sp, fontWeight = FontWeight.Bold, maxLines = 1)
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                        MainTab.NOTES -> {
                                            Text("灵感便签", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                                        }
                                    MainTab.CHAT -> {
                                        Text("与桌宠互动", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                                    }
                                    MainTab.FOCUS -> {
                                        Text("专注番茄钟", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                                    }
                                }
                            },
                            actions = {
                                when (selectedTab) {
                                    MainTab.SCHEDULE -> {
                                        // 课表管理顶栏操作：期末考倒计时 + AI学情分析 + 更多功能折叠菜单
                                        IconButton(onClick = { showExamScheduleView = true }) {
                                            Icon(
                                                Icons.Default.Timer,
                                                contentDescription = "期末考倒计时",
                                                tint = Color(0xFFFF9100)
                                            )
                                        }
                                        IconButton(onClick = {
                                            pendingChatPrompt = "阿米娅，请结合我导入的课表数据，全面分析我的学习情况与课程负荷，并给出科学的学习与作息规划建议。"
                                            selectedTab = MainTab.CHAT
                                        }) {
                                            Icon(
                                                Icons.Default.AutoAwesome,
                                                contentDescription = "AI 学情分析",
                                                tint = MaterialTheme.colorScheme.primary
                                            )
                                        }

                                        var showScheduleMenu by remember { mutableStateOf(false) }
                                        Box {
                                            IconButton(onClick = { showScheduleMenu = true }) {
                                                Icon(Icons.Default.MoreVert, contentDescription = "更多功能", tint = MaterialTheme.colorScheme.onSurface)
                                            }
                                            DropdownMenu(
                                                expanded = showScheduleMenu,
                                                onDismissRequest = { showScheduleMenu = false }
                                            ) {
                                                DropdownMenuItem(
                                                    text = { Text("手动添加课程") },
                                                    leadingIcon = { Icon(Icons.Default.Add, null) },
                                                    onClick = {
                                                        showScheduleMenu = false
                                                        showAddCourseDialog = true
                                                    }
                                                )
                                                DropdownMenuItem(
                                                    text = { Text("导入课表数据") },
                                                    leadingIcon = { Icon(Icons.Default.Download, null) },
                                                    onClick = {
                                                        showScheduleMenu = false
                                                        showImportDialog = true
                                                    }
                                                )
                                                DropdownMenuItem(
                                                    text = { Text("课表提醒与作息设置") },
                                                    leadingIcon = { Icon(Icons.Default.NotificationsActive, null) },
                                                    onClick = {
                                                        showScheduleMenu = false
                                                        showReminderDialog = true
                                                    }
                                                )
                                                DropdownMenuItem(
                                                    text = { Text("设置学期开学日") },
                                                    leadingIcon = { Icon(Icons.Default.EditCalendar, null) },
                                                    onClick = {
                                                        showScheduleMenu = false
                                                        showTermStartDialog = true
                                                    }
                                                )
                                                DropdownMenuItem(
                                                    text = { Text(if (ScheduleManager.weekStartDay == "monday") "周起始日：周一开始 (点击切换)" else "周起始日：周日开始 (点击切换)") },
                                                    leadingIcon = { Icon(Icons.Default.ViewWeek, null) },
                                                    onClick = {
                                                        showScheduleMenu = false
                                                        val nextDay = if (ScheduleManager.weekStartDay == "monday") "sunday" else "monday"
                                                        ScheduleManager.setWeekStartDay(nextDay, context)
                                                        Toast.makeText(context, if (nextDay == "monday") "课表已切换为周一开始" else "课表已切换为周日开始", Toast.LENGTH_SHORT).show()
                                                    }
                                                )
                                                DropdownMenuItem(
                                                    text = { Text("添加桌面课表小部件") },
                                                    leadingIcon = { Icon(Icons.Default.Widgets, null) },
                                                    onClick = {
                                                        showScheduleMenu = false
                                                        val success = ScheduleWidgetProvider.requestPinWidget(context)
                                                        if (success) {
                                                            Toast.makeText(context, "正在请求添加桌面小部件，请在弹窗中确认~", Toast.LENGTH_SHORT).show()
                                                        } else {
                                                            Toast.makeText(context, "系统暂不支持自动添加，请在桌面空白处长按添加「阿米娅今日课表」小部件", Toast.LENGTH_LONG).show()
                                                        }
                                                    }
                                                )
                                                DropdownMenuItem(
                                                    text = { Text("导出通用日历 (.ics)") },
                                                    leadingIcon = { Icon(Icons.Default.CalendarMonth, null) },
                                                    onClick = {
                                                        showScheduleMenu = false
                                                        showIcsExportDialog = true
                                                    }
                                                )
                                                DropdownMenuItem(
                                                    text = { Text("期末考试日程与倒计时") },
                                                    leadingIcon = { Icon(Icons.Default.School, null) },
                                                    onClick = {
                                                        showScheduleMenu = false
                                                        showExamScheduleView = true
                                                    }
                                                )
                                                DropdownMenuItem(
                                                    text = { Text("罗德岛跨端协同 (PC ↔ 手机)") },
                                                    leadingIcon = { Icon(Icons.Default.Devices, null) },
                                                    onClick = {
                                                        showScheduleMenu = false
                                                        showSyncDialog = true
                                                    }
                                                )
                                                HorizontalDivider()
                                                DropdownMenuItem(
                                                    text = { Text(if (FloatingPetManager.isFloatingPetEnabled(context)) "关闭桌面桌宠" else "开启桌面桌宠") },
                                                    leadingIcon = { Icon(Icons.Default.PictureInPictureAlt, null) },
                                                    onClick = {
                                                        showScheduleMenu = false
                                                        toggleFloatingPet()
                                                    }
                                                )
                                                DropdownMenuItem(
                                                    text = { Text(if (isDark) "切换到浅色模式" else "切换到深色模式") },
                                                    leadingIcon = { Icon(if (isDark) Icons.Default.Brightness7 else Icons.Default.Brightness4, null) },
                                                    onClick = {
                                                        showScheduleMenu = false
                                                        toggleTheme()
                                                    }
                                                )
                                                DropdownMenuItem(
                                                    text = { Text("检查应用更新") },
                                                    leadingIcon = { Icon(Icons.Default.CloudDownload, null) },
                                                    onClick = {
                                                        showScheduleMenu = false
                                                        triggerCheckUpdate()
                                                    }
                                                )
                                            }
                                        }
                                    }
                                    MainTab.CHAT -> {
                                        IconButton(onClick = { showChatGuideDialog = true }) {
                                            Icon(Icons.Default.Campaign, contentDescription = "公告与使用指南", tint = MaterialTheme.colorScheme.primary)
                                        }
                                        IconButton(onClick = { chatClearTrigger++ }) {
                                            Icon(Icons.Default.DeleteOutline, contentDescription = "清空对话", tint = MaterialTheme.colorScheme.onSurface)
                                        }
                                        IconButton(onClick = { showChatSettingsDialog = true }) {
                                            Icon(Icons.Default.Settings, contentDescription = "设置", tint = MaterialTheme.colorScheme.onSurface)
                                        }
                                    }
                                    MainTab.NOTES, MainTab.FOCUS -> {
                                        IconButton(onClick = { toggleFloatingPet() }) {
                                            val isEnabled = FloatingPetManager.isShowing || FloatingPetManager.isFloatingPetEnabled(context)
                                            Icon(
                                                Icons.Default.PictureInPictureAlt,
                                                contentDescription = "桌面悬浮桌宠",
                                                tint = if (isEnabled) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                                            )
                                        }
                                        IconButton(onClick = { toggleTheme() }) {
                                            Icon(if (isDark) Icons.Default.Brightness7 else Icons.Default.Brightness4, contentDescription = "切换模式", tint = MaterialTheme.colorScheme.onSurface)
                                        }
                                        IconButton(onClick = { triggerCheckUpdate() }) {
                                            Icon(Icons.Default.CloudDownload, contentDescription = "检查更新", tint = MaterialTheme.colorScheme.onSurface)
                                        }
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
                                    onClick = {
                                        if (tab == MainTab.SCHEDULE && selectedTab == MainTab.SCHEDULE) {
                                            showExamScheduleView = false
                                        }
                                        selectedTab = tab
                                    },
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
                            MainTab.SCHEDULE -> {
                                if (showExamScheduleView) {
                                    ExamScheduleView(
                                        onBackToSchedule = { showExamScheduleView = false }
                                    )
                                } else {
                                    ScheduleScreen(
                                        currentWeek = scheduleWeek,
                                        onWeekChange = { scheduleWeek = it },
                                        showImportDialog = showImportDialog,
                                        onDismissImportDialog = { showImportDialog = false },
                                        onOpenImportDialog = { showImportDialog = true },
                                        showReminderDialog = showReminderDialog,
                                        onDismissReminderDialog = { showReminderDialog = false },
                                        showAddCourseDialog = showAddCourseDialog,
                                        onDismissAddCourseDialog = { showAddCourseDialog = false },
                                        onOpenAddCourseDialog = { showAddCourseDialog = true },
                                        onConsultAi = { prompt ->
                                            pendingChatPrompt = prompt
                                            selectedTab = MainTab.CHAT
                                        }
                                    )
                                }
                            }
                            MainTab.NOTES -> NotesScreen()
                            MainTab.CHAT -> ChatScreen(
                                showGuideDialog = showChatGuideDialog,
                                onDismissGuideDialog = { showChatGuideDialog = false },
                                showSettingsDialog = showChatSettingsDialog,
                                onDismissSettingsDialog = { showChatSettingsDialog = false },
                                clearHistoryTrigger = chatClearTrigger,
                                onCheckUpdate = { triggerCheckUpdate() },
                                onToggleTheme = { toggleTheme() },
                                isDark = isDark,
                                initialPrompt = pendingChatPrompt,
                                onConsumeInitialPrompt = { pendingChatPrompt = null },
                                onNavigateToSchedule = { targetWeek ->
                                    if (targetWeek != null) {
                                        scheduleWeek = targetWeek
                                    }
                                    showExamScheduleView = false
                                    selectedTab = MainTab.SCHEDULE
                                },
                                onNavigateToFocus = {
                                    selectedTab = MainTab.FOCUS
                                },
                                onNavigateToNotes = {
                                    selectedTab = MainTab.NOTES
                                }
                            )
                            MainTab.FOCUS -> PomodoroScreen()
                        }
                    }
                }

                if (showIcsExportDialog) {
                    IcsExportDialog(
                        courses = ScheduleManager.courses,
                        onDismiss = { showIcsExportDialog = false }
                    )
                }

                if (showSyncDialog) {
                    SyncDialog(
                        onDismiss = { showSyncDialog = false }
                    )
                }

                if (showTermStartDialog) {
                    val currentStartStr = remember {
                        val s = ScheduleManager.termStart ?: Date()
                        java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.getDefault()).format(ScheduleManager.normalizeToSunday(s))
                    }
                    var inputDateStr by remember { mutableStateOf(currentStartStr) }
                    var parseError by remember { mutableStateOf("") }

                    val previewInfo = remember(inputDateStr) {
                        try {
                            val format = java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.getDefault())
                            format.isLenient = false
                            val parsed = format.parse(inputDateStr.trim())
                            if (parsed != null) {
                                val norm = ScheduleManager.normalizeToSunday(parsed)
                                val normStr = format.format(norm)
                                val targetNorm = ScheduleManager.normalizeToSunday(Date())
                                val diffMs = targetNorm.time - norm.time
                                val calcWeek = if (diffMs < 0) 0 else (diffMs / (24L * 3600 * 1000) / 7).toInt() + 1
                                "校准第 1 周起始日 (周日): $normStr\n推算今日归属: 第 $calcWeek 周"
                            } else ""
                        } catch (e: Exception) {
                            "日期格式有误 (需为 YYYY-MM-DD)"
                        }
                    }

                    AlertDialog(
                        onDismissRequest = { showTermStartDialog = false },
                        containerColor = MaterialTheme.colorScheme.surface,
                        title = {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.DateRange, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                                Spacer(Modifier.width(8.dp))
                                Text("设置学期开学日期", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
                            }
                        },
                        text = {
                            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                Text(
                                    text = "请设置本学期第 1 周的公历日期。无论您输入该周的哪一天，系统都会智能校准对齐至该周起始日（周日）。",
                                    fontSize = 13.sp,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                                OutlinedTextField(
                                    value = inputDateStr,
                                    onValueChange = { inputDateStr = it; parseError = "" },
                                    label = { Text("开学第 1 周周日 (YYYY-MM-DD)") },
                                    singleLine = true,
                                    modifier = Modifier.fillMaxWidth()
                                )
                                if (previewInfo.isNotEmpty()) {
                                    Text(
                                        text = previewInfo,
                                        fontSize = 12.sp,
                                        color = if (previewInfo.contains("有误")) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary
                                    )
                                }
                                if (parseError.isNotEmpty()) {
                                    Text(parseError, color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
                                }
                            }
                        },
                        confirmButton = {
                            Button(
                                onClick = {
                                    try {
                                        val format = java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.getDefault())
                                        format.isLenient = false
                                        val parsed = format.parse(inputDateStr.trim())
                                        if (parsed != null) {
                                            ScheduleManager.setTermStartDate(parsed, context)
                                            scheduleWeek = ScheduleManager.getWeekNo() ?: 1
                                            showTermStartDialog = false
                                            Toast.makeText(context, "学期开学日已更新，当前自动切至第 $scheduleWeek 周", Toast.LENGTH_SHORT).show()
                                        } else {
                                            parseError = "日期解析失败，请检查格式"
                                        }
                                    } catch (e: Exception) {
                                        parseError = "请输入正确的日期格式 (如 2026-09-07)"
                                    }
                                }
                            ) {
                                Text("保存生效")
                            }
                        },
                        dismissButton = {
                            TextButton(onClick = { showTermStartDialog = false }) {
                                Text("取消")
                            }
                        }
                    )
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
