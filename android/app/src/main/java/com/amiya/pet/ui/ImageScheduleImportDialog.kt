@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.amiya.pet.ui

import android.graphics.BitmapFactory
import android.net.Uri
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
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
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.amiya.pet.core.ai.AmiyaBrain
import com.amiya.pet.core.schedule.Course
import com.amiya.pet.core.schedule.ScheduleManager
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private val WEEKDAY_NAMES = arrayOf("", "周一", "周二", "周三", "周四", "周五", "周六", "周日")

private val SCANNING_HINTS = listOf(
    "PRTS 视觉多模态核心正在读取图像...",
    "正在分析课表表格结构与坐标网格...",
    "正在智能校对星期列与节次行映射...",
    "正在高精度提取各门课程、教室与周次信息...",
    "即将完成结构化构建..."
)

@Composable
fun ImageScheduleImportDialog(
    onDismiss: () -> Unit,
    onImportSuccess: (count: Int) -> Unit = {},
    onConsultAi: (prompt: String) -> Unit = {}
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val brain = remember { AmiyaBrain.getInstance(context) }

    var selectedUri by remember { mutableStateOf<Uri?>(null) }
    var selectedImageBytes by remember { mutableStateOf<ByteArray?>(null) }
    var isScanning by remember { mutableStateOf(false) }
    var scanHintIndex by remember { mutableIntStateOf(0) }
    var parsedCourses by remember { mutableStateOf<List<Course>>(emptyList()) }
    var selectedIndices by remember { mutableStateOf<Set<Int>>(emptySet()) }
    var isOverwrite by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var scanJob by remember { mutableStateOf<Job?>(null) }

    // 缩略图生成（直接基于内存字节解码，零 IO 阻塞与权限失效）
    val previewBitmap = remember(selectedImageBytes) {
        selectedImageBytes?.let { bytes ->
            try {
                val opts = BitmapFactory.Options().apply { inSampleSize = 2 }
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size, opts)
            } catch (e: Exception) {
                null
            }
        }
    }

    val pickImageLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) {
            selectedUri = uri
            errorMessage = null
            parsedCourses = emptyList()
            selectedIndices = emptySet()
            try {
                selectedImageBytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
            } catch (e: Exception) {
                errorMessage = "无法读取所选图片: ${e.message}"
            }
        }
    }

    // 扫描提示文案轮播
    LaunchedEffect(isScanning) {
        if (isScanning) {
            scanHintIndex = 0
            while (isScanning) {
                delay(2200)
                scanHintIndex = (scanHintIndex + 1) % SCANNING_HINTS.size
            }
        }
    }

    Dialog(
        onDismissRequest = {
            if (!isScanning) {
                scanJob?.cancel()
                onDismiss()
            }
        },
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Surface(
            modifier = Modifier
                .fillMaxWidth(0.94f)
                .wrapContentHeight()
                .padding(vertical = 20.dp),
            shape = RoundedCornerShape(20.dp),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 6.dp
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(20.dp)
            ) {
                // 顶部标题栏
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Surface(
                            shape = CircleShape,
                            color = MaterialTheme.colorScheme.primaryContainer,
                            modifier = Modifier.size(38.dp)
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(
                                    imageVector = Icons.Default.DocumentScanner,
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.primary,
                                    modifier = Modifier.size(20.dp)
                                )
                            }
                        }
                        Spacer(Modifier.width(10.dp))
                        Column {
                            Text(
                                text = "课表截图 / 拍照 AI 导入",
                                fontSize = 17.sp,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Text(
                                text = "PRTS 多模态视觉智能解析 · 一键导入整学期课表",
                                fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                    IconButton(
                        onClick = {
                            scanJob?.cancel()
                            onDismiss()
                        },
                        enabled = !isScanning,
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "关闭",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                Spacer(Modifier.height(16.dp))

                // 错误提示
                if (errorMessage != null) {
                    Surface(
                        shape = RoundedCornerShape(10.dp),
                        color = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.8f),
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(bottom = 12.dp)
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                Icons.Default.ErrorOutline,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.error,
                                modifier = Modifier.size(20.dp)
                            )
                            Spacer(Modifier.width(8.dp))
                            Text(
                                text = errorMessage ?: "",
                                fontSize = 12.sp,
                                color = MaterialTheme.colorScheme.onErrorContainer,
                                modifier = Modifier.weight(1f)
                            )
                        }
                    }
                }

                // 核心状态切换：未选图 / 已选图等待扫描 / 扫描中 / 识别结果核对
                when {
                    // 1. 扫描中
                    isScanning -> {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 32.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(52.dp),
                                color = MaterialTheme.colorScheme.primary,
                                strokeWidth = 4.dp
                            )
                            Spacer(Modifier.height(20.dp))
                            Text(
                                text = SCANNING_HINTS[scanHintIndex],
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Medium,
                                color = MaterialTheme.colorScheme.primary,
                                textAlign = TextAlign.Center
                            )
                            Spacer(Modifier.height(8.dp))
                            Text(
                                text = "多模态大模型正在逐行分析节次与星期，请稍候...",
                                fontSize = 12.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Spacer(Modifier.height(24.dp))
                            OutlinedButton(
                                onClick = {
                                    scanJob?.cancel()
                                    isScanning = false
                                },
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Text("取消分析", fontSize = 12.sp)
                            }
                        }
                    }

                    // 2. 识别结果预览核对状态
                    parsedCourses.isNotEmpty() -> {
                        Column(modifier = Modifier.fillMaxWidth()) {
                            // 统计与全选
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        Icons.Default.CheckCircle,
                                        contentDescription = null,
                                        tint = Color(0xFF4CAF50),
                                        modifier = Modifier.size(18.dp)
                                    )
                                    Spacer(Modifier.width(6.dp))
                                    Text(
                                        text = "已识别出 ${parsedCourses.size} 个课程时段",
                                        fontSize = 14.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = MaterialTheme.colorScheme.onSurface
                                    )
                                }
                                TextButton(
                                    onClick = {
                                        selectedIndices = if (selectedIndices.size == parsedCourses.size) {
                                            emptySet()
                                        } else {
                                            parsedCourses.indices.toSet()
                                        }
                                    }
                                ) {
                                    Text(
                                        text = if (selectedIndices.size == parsedCourses.size) "取消全选" else "全选全部",
                                        fontSize = 12.sp
                                    )
                                }
                            }

                            Spacer(Modifier.height(8.dp))

                            // 课程列表卡片
                            LazyColumn(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .heightIn(max = 280.dp),
                                verticalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                itemsIndexed(parsedCourses) { index, course ->
                                    val isSelected = selectedIndices.contains(index)
                                    CoursePreviewItem(
                                        course = course,
                                        isSelected = isSelected,
                                        onToggle = {
                                            selectedIndices = if (isSelected) {
                                                selectedIndices - index
                                            } else {
                                                selectedIndices + index
                                            }
                                        }
                                    )
                                }
                            }

                            Spacer(Modifier.height(14.dp))

                            // 导入模式选择
                            Text(
                                text = "导入模式设置：",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Spacer(Modifier.height(4.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    modifier = Modifier
                                        .clickable { isOverwrite = true }
                                        .padding(vertical = 4.dp)
                                ) {
                                    RadioButton(
                                        selected = isOverwrite,
                                        onClick = { isOverwrite = true }
                                    )
                                    Spacer(Modifier.width(4.dp))
                                    Text("覆盖现有课表 (清空重置)", fontSize = 12.sp)
                                }
                                Spacer(Modifier.width(12.dp))
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    modifier = Modifier
                                        .clickable { isOverwrite = false }
                                        .padding(vertical = 4.dp)
                                ) {
                                    RadioButton(
                                        selected = !isOverwrite,
                                        onClick = { isOverwrite = false }
                                    )
                                    Spacer(Modifier.width(4.dp))
                                    Text("增量追加合并", fontSize = 12.sp)
                                }
                            }

                            Spacer(Modifier.height(16.dp))

                            // 操作按钮行
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(10.dp)
                            ) {
                                OutlinedButton(
                                    onClick = {
                                        parsedCourses = emptyList()
                                        selectedIndices = emptySet()
                                    },
                                    modifier = Modifier.weight(1f),
                                    shape = RoundedCornerShape(10.dp)
                                ) {
                                    Text("重新选图", fontSize = 13.sp)
                                }
                                Button(
                                    onClick = {
                                        val toImport = parsedCourses.filterIndexed { idx, _ -> selectedIndices.contains(idx) }
                                        if (toImport.isEmpty()) {
                                            Toast.makeText(context, "请至少勾选一门要导入的课程", Toast.LENGTH_SHORT).show()
                                            return@Button
                                        }
                                        ScheduleManager.importCourses(toImport, isOverwrite, context)
                                        Toast.makeText(context, "成功导入 ${toImport.size} 门课程！", Toast.LENGTH_SHORT).show()
                                        onImportSuccess(toImport.size)
                                        onDismiss()
                                    },
                                    enabled = selectedIndices.isNotEmpty(),
                                    modifier = Modifier.weight(1.5f),
                                    shape = RoundedCornerShape(10.dp),
                                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                                ) {
                                    Icon(
                                        Icons.Default.DownloadDone,
                                        contentDescription = null,
                                        tint = Color.Black,
                                        modifier = Modifier.size(16.dp)
                                    )
                                    Spacer(Modifier.width(6.dp))
                                    Text(
                                        text = "确认导入 (${selectedIndices.size})",
                                        color = Color.Black,
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 13.sp
                                    )
                                }
                            }
                        }
                    }

                    // 3. 初始/已选图待识别状态
                    else -> {
                        Column(modifier = Modifier.fillMaxWidth()) {
                            if (previewBitmap != null) {
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .height(180.dp)
                                        .clip(RoundedCornerShape(12.dp))
                                        .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(12.dp))
                                ) {
                                    Image(
                                        bitmap = previewBitmap.asImageBitmap(),
                                        contentDescription = "所选课表预览",
                                        modifier = Modifier.fillMaxSize(),
                                        contentScale = ContentScale.Fit
                                    )
                                    Surface(
                                        color = Color.Black.copy(alpha = 0.65f),
                                        shape = RoundedCornerShape(bottomStart = 8.dp),
                                        modifier = Modifier.align(Alignment.TopEnd)
                                    ) {
                                        Row(
                                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Icon(
                                                Icons.Default.Check,
                                                contentDescription = null,
                                                tint = Color(0xFF4CAF50),
                                                modifier = Modifier.size(14.dp)
                                            )
                                            Spacer(Modifier.width(4.dp))
                                            Text("已就绪", color = Color.White, fontSize = 11.sp)
                                        }
                                    }
                                }
                                Spacer(Modifier.height(14.dp))
                            } else {
                                Surface(
                                    shape = RoundedCornerShape(12.dp),
                                    color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clickable { pickImageLauncher.launch("image/*") }
                                        .border(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.3f), RoundedCornerShape(12.dp))
                                ) {
                                    Column(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(vertical = 32.dp, horizontal = 16.dp),
                                        horizontalAlignment = Alignment.CenterHorizontally
                                    ) {
                                        Icon(
                                            imageVector = Icons.Default.AddPhotoAlternate,
                                            contentDescription = null,
                                            tint = MaterialTheme.colorScheme.primary,
                                            modifier = Modifier.size(44.dp)
                                        )
                                        Spacer(Modifier.height(10.dp))
                                        Text(
                                            text = "点击从相册/相册截图选择课表",
                                            fontSize = 14.sp,
                                            fontWeight = FontWeight.SemiBold,
                                            color = MaterialTheme.colorScheme.onSurface
                                        )
                                        Spacer(Modifier.height(4.dp))
                                        Text(
                                            text = "支持教务系统课表截图、手机相册照片或导出图片",
                                            fontSize = 11.sp,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                    }
                                }
                                Spacer(Modifier.height(14.dp))
                            }

                            // 提示说明卡片
                            Surface(
                                shape = RoundedCornerShape(10.dp),
                                color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f),
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Column(modifier = Modifier.padding(12.dp)) {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Icon(
                                            Icons.Default.AutoAwesome,
                                            contentDescription = null,
                                            tint = MaterialTheme.colorScheme.primary,
                                            modifier = Modifier.size(16.dp)
                                        )
                                        Spacer(Modifier.width(6.dp))
                                        Text(
                                            text = "PRTS 视觉识别技术说明",
                                            fontSize = 12.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = MaterialTheme.colorScheme.primary
                                        )
                                    }
                                    Spacer(Modifier.height(4.dp))
                                    Text(
                                        text = "• 支持强智、正方、青果等各类高校教务课表网格识别；\n" +
                                               "• 建议截取包含星期列与节次行的完整课表，字迹越清晰准确率越高；\n" +
                                               "• 默认使用智谱 GLM-4V 多模态免费免翻视觉引擎，无需翻墙秒级分析。",
                                        fontSize = 11.sp,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        lineHeight = 16.sp
                                    )
                                }
                            }

                            Spacer(Modifier.height(18.dp))

                            // 底部操作栏
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(10.dp)
                            ) {
                                OutlinedButton(
                                    onClick = { pickImageLauncher.launch("image/*") },
                                    modifier = Modifier.weight(1f),
                                    shape = RoundedCornerShape(10.dp)
                                ) {
                                    Icon(
                                        imageVector = if (selectedUri != null) Icons.Default.Refresh else Icons.Default.PhotoLibrary,
                                        contentDescription = null,
                                        modifier = Modifier.size(16.dp)
                                    )
                                    Spacer(Modifier.width(4.dp))
                                    Text(if (selectedUri != null) "更换图片" else "选取图片", fontSize = 13.sp)
                                }

                                 Button(
                                    onClick = {
                                        val bytes = selectedImageBytes ?: return@Button
                                        isScanning = true
                                        errorMessage = null
                                        scanJob = scope.launch {
                                            val result = brain.parseScheduleFromImage(context, bytes)
                                            isScanning = false
                                            result.fold(
                                                onSuccess = { courses ->
                                                    parsedCourses = courses
                                                    selectedIndices = courses.indices.toSet()
                                                },
                                                onFailure = { err ->
                                                    errorMessage = err.message ?: "识别失败，请检查网络或图片清晰度"
                                                }
                                            )
                                        }
                                    },
                                    enabled = selectedImageBytes != null,
                                    modifier = Modifier.weight(1.3f),
                                    shape = RoundedCornerShape(10.dp),
                                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                                ) {
                                    Icon(
                                        Icons.Default.AutoAwesome,
                                        contentDescription = null,
                                        tint = Color.Black,
                                        modifier = Modifier.size(16.dp)
                                    )
                                    Spacer(Modifier.width(6.dp))
                                    Text("开始智能解析", color = Color.Black, fontWeight = FontWeight.Bold, fontSize = 13.sp)
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
private fun CoursePreviewItem(
    course: Course,
    isSelected: Boolean,
    onToggle: () -> Unit
) {
    val weekdayStr = WEEKDAY_NAMES.getOrElse(course.weekday) { "周${course.weekday}" }
    val parityStr = when (course.parity) {
        "odd" -> "单周"
        "even" -> "双周"
        else -> "全周"
    }

    Surface(
        shape = RoundedCornerShape(10.dp),
        color = if (isSelected) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f),
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onToggle)
            .border(
                1.dp,
                if (isSelected) MaterialTheme.colorScheme.primary.copy(alpha = 0.6f) else MaterialTheme.colorScheme.outline.copy(alpha = 0.15f),
                RoundedCornerShape(10.dp)
            )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 10.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Checkbox(
                checked = isSelected,
                onCheckedChange = { onToggle() },
                modifier = Modifier.size(28.dp)
            )
            Spacer(Modifier.width(8.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = course.name,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Spacer(Modifier.height(4.dp))
                Row(
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    BadgeTag(text = weekdayStr, color = MaterialTheme.colorScheme.primary)
                    BadgeTag(text = "第${course.secStart}-${course.secEnd}节", color = MaterialTheme.colorScheme.secondary)
                    BadgeTag(text = "${course.weekStart}-${course.weekEnd}周 ($parityStr)", color = MaterialTheme.colorScheme.tertiary)
                }
                if (course.room.isNotEmpty() || course.teacher.isNotEmpty()) {
                    Spacer(Modifier.height(2.dp))
                    Text(
                        text = listOfNotNull(
                            if (course.room.isNotEmpty()) "📍 ${course.room}" else null,
                            if (course.teacher.isNotEmpty()) "👤 ${course.teacher}" else null
                        ).joinToString(" · "),
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

@Composable
private fun BadgeTag(text: String, color: Color) {
    Surface(
        shape = RoundedCornerShape(4.dp),
        color = color.copy(alpha = 0.15f)
    ) {
        Text(
            text = text,
            fontSize = 10.sp,
            fontWeight = FontWeight.Medium,
            color = color,
            modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp)
        )
    }
}
