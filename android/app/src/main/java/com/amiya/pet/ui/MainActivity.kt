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
import com.amiya.pet.core.update.DownloadProgress
import com.amiya.pet.core.update.ReleaseInfo
import com.amiya.pet.core.update.UpdateManager
import com.amiya.pet.service.AppBackgroundService
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import java.io.File

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

        val serviceIntent = Intent(this, AppBackgroundService::class.java)
        ContextCompat.startForegroundService(this, serviceIntent)

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
        SCHEDULE("课表", Icons.Default.DateRange),
    NOTES("便签", Icons.Default.EditNote),
    CHAT("对话", Icons.Default.Chat),
    FOCUS("专注", Icons.Default.Timer)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen() {
    var selectedTab by remember { mutableStateOf(MainTab.CHAT) }

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
                
                MainTab.SCHEDULE -> ScheduleScreen()
                MainTab.NOTES -> NotesScreen()
                MainTab.CHAT -> ChatScreen()
                MainTab.FOCUS -> PomodoroScreen()
            }
        }
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
