package com.amiya.pet.ui

import android.content.Context
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Outline
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.amiya.pet.R
import com.amiya.pet.core.ai.AmiyaBrain
import com.amiya.pet.core.ai.ChatMessage
import com.amiya.pet.core.schedule.ScheduleManager
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    onCheckUpdate: () -> Unit = {},
    onToggleTheme: () -> Unit = {},
    isDark: Boolean = true,
    initialPrompt: String? = null,
    onConsumeInitialPrompt: () -> Unit = {}
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val brain = remember { AmiyaBrain.getInstance(context) }
    val prefs = remember { context.getSharedPreferences("amiya_pet_prefs", Context.MODE_PRIVATE) }
    var showGuideDialog by remember { mutableStateOf(!prefs.getBoolean("has_seen_guide_v1", false)) }
    var chatList by remember { mutableStateOf(brain.chatHistory) }
    var inputText by remember { mutableStateOf("") }
    var isSending by remember { mutableStateOf(false) }
    var showSettingsDialog by remember { mutableStateOf(false) }

    val listState = rememberLazyListState()

    LaunchedEffect(Unit) {
        if (ScheduleManager.courses.isEmpty()) {
            ScheduleManager.load(context)
        }
    }

    val courseCount = remember(ScheduleManager.courses) {
        ScheduleManager.courses.map { it.name }.distinct().size
    }

    fun sendMessage(msg: String) {
        val trimmed = msg.trim()
        if (trimmed.isEmpty() || isSending) return
        inputText = ""
        isSending = true

        val userMsg = ChatMessage("user", trimmed)
        val assistantPlaceholder = ChatMessage(
            role = "assistant",
            content = "",
            reasoningContent = "",
            isThinking = false,
            isStreaming = true
        )
        chatList = chatList + userMsg + assistantPlaceholder

        scope.launch {
            if (chatList.isNotEmpty()) {
                listState.animateScrollToItem(chatList.size - 1)
            }
            brain.sendMessageStream(trimmed) { reasoning, content, isThinking ->
                val current = chatList
                if (current.isNotEmpty() && current.last().role == "assistant") {
                    val updated = current.last().copy(
                        reasoningContent = reasoning,
                        content = content,
                        isThinking = isThinking,
                        isStreaming = true
                    )
                    chatList = current.dropLast(1) + updated
                }
            }
            // 流式结束，更新状态
            val current = chatList
            if (current.isNotEmpty() && current.last().role == "assistant") {
                val updated = current.last().copy(
                    isThinking = false,
                    isStreaming = false
                )
                chatList = current.dropLast(1) + updated
            }
            isSending = false
            if (chatList.isNotEmpty()) {
                listState.animateScrollToItem(chatList.size - 1)
            }
        }
    }

    LaunchedEffect(initialPrompt) {
        if (!initialPrompt.isNullOrBlank()) {
            sendMessage(initialPrompt)
            onConsumeInitialPrompt()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("与桌宠互动", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                    }
                },
                actions = {
                    IconButton(onClick = { showGuideDialog = true }) {
                        Icon(
                            imageVector = Icons.Default.Campaign,
                            contentDescription = "公告与使用指南",
                            tint = MaterialTheme.colorScheme.primary
                        )
                    }
                    IconButton(onClick = {
                        brain.clearHistory()
                        chatList = emptyList()
                    }) {
                        Icon(Icons.Default.DeleteOutline, contentDescription = "清空对话", tint = MaterialTheme.colorScheme.onSurface)
                    }
                    IconButton(onClick = onCheckUpdate) {
                        Icon(Icons.Default.CloudDownload, contentDescription = "检查更新", tint = MaterialTheme.colorScheme.onSurface)
                    }
                    IconButton(onClick = onToggleTheme) {
                        if (isDark) {
                            Icon(Icons.Default.Brightness7, contentDescription = "切换到浅色模式", tint = MaterialTheme.colorScheme.onSurface)
                        } else {
                            Icon(Icons.Default.Brightness4, contentDescription = "切换到深色模式", tint = MaterialTheme.colorScheme.onSurface)
                        }
                    }
                    IconButton(onClick = { showSettingsDialog = true }) {
                        Icon(Icons.Default.Settings, contentDescription = "设置", tint = MaterialTheme.colorScheme.onSurface)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.surface)
            )
        },
        containerColor = MaterialTheme.colorScheme.background
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // Chat messages
            Box(modifier = Modifier.weight(1f)) {
                if (chatList.isEmpty()) {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        Icon(Icons.Default.ChatBubbleOutline, null, tint = Color.Gray, modifier = Modifier.size(48.dp))
                        Spacer(modifier = Modifier.height(12.dp))
                        Text("随时准备听您诉说。", color = MaterialTheme.colorScheme.onSurface, fontSize = 15.sp, fontWeight = FontWeight.Medium)
                        if (courseCount > 0) {
                            Spacer(modifier = Modifier.height(12.dp))
                            Surface(
                                shape = RoundedCornerShape(12.dp),
                                color = MaterialTheme.colorScheme.primary.copy(alpha = 0.12f),
                                modifier = Modifier.clickable {
                                    sendMessage("阿米娅，请结合我导入的课表数据，全面分析我的学习情况与课程负荷，并给出科学的学习与作息规划建议。")
                                }
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 8.dp)
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.AutoAwesome,
                                        contentDescription = null,
                                        tint = MaterialTheme.colorScheme.primary,
                                        modifier = Modifier.size(16.dp)
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        text = "已同步博士课表（共 $courseCount 门）· 点击让阿米娅分析学情",
                                        fontSize = 12.sp,
                                        color = MaterialTheme.colorScheme.primary,
                                        fontWeight = FontWeight.Medium
                                    )
                                }
                            }
                        }
                    }
                } else {
                    LazyColumn(
                        state = listState,
                        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                        modifier = Modifier.fillMaxSize()
                    ) {
                        items(chatList) { message ->
                            ChatBubbleItem(message = message, isDark = isDark)
                        }
                    }
                }
            }

            // Quick prompts
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState())
                    .padding(horizontal = 12.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                if (courseCount > 0) {
                    QuickPromptChip("📊 课表学情分析", {
                        sendMessage("阿米娅，请结合我导入的课表数据，全面分析我的学习负荷与课程节奏，并给出科学的自习与作息规划建议。")
                    })
                    QuickPromptChip("📅 今天有什么课", {
                        sendMessage("阿米娅，我今天有什么课程安排？下一节课是什么？")
                    })
                    QuickPromptChip("💡 学习作息建议", {
                        sendMessage("根据我这周的课程密度与空闲时段，建议我在什么时候安排自习和备考比较好？")
                    })
                }
                QuickPromptChip("☕ 辛苦了", { sendMessage("辛苦了，阿米娅。") })
                QuickPromptChip("有什么安排？", { sendMessage("阿米娅，今天有什么需要注意的安排吗？") })
            }

            // Input
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.surface)
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedTextField(
                    value = inputText,
                    onValueChange = { inputText = it },
                    placeholder = { Text("对桌宠说点什么...", color = Color.Gray, fontSize = 14.sp) },
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(24.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = MaterialTheme.colorScheme.onSurface,
                        unfocusedTextColor = MaterialTheme.colorScheme.onSurface,
                        focusedBorderColor = MaterialTheme.colorScheme.primary,
                        unfocusedBorderColor = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.2f)
                    ),
                    maxLines = 3
                )
                Spacer(modifier = Modifier.width(8.dp))
                IconButton(
                    onClick = { sendMessage(inputText) },
                    enabled = inputText.isNotBlank() && !isSending,
                    modifier = Modifier
                        .size(48.dp)
                        .clip(RoundedCornerShape(24.dp))
                        .background(if (inputText.isNotBlank()) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    if (isSending) {
                        CircularProgressIndicator(modifier = Modifier.size(20.dp), color = Color.Black, strokeWidth = 2.dp)
                    } else {
                        Icon(Icons.Default.Send, "发送", tint = if (inputText.isNotBlank()) Color.Black else Color.Gray)
                    }
                }
            }
        }
    }

    if (showSettingsDialog) {
        var baseUrl by remember { mutableStateOf(brain.baseUrl) }
        var apiKey by remember { mutableStateOf(brain.apiKey) }
        var model by remember { mutableStateOf(brain.model) }
        var publicRelayUrl by remember { mutableStateOf(brain.publicRelayUrl) }
        var showAdvancedRelay by remember { mutableStateOf(false) }

        AlertDialog(
            onDismissRequest = { showSettingsDialog = false },
            containerColor = MaterialTheme.colorScheme.surface,
            title = { Text("综合设置", fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface) },
            text = {
                Column(
                    modifier = Modifier.verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Text("AI 模型配置", color = MaterialTheme.colorScheme.primary, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                    OutlinedTextField(
                        value = baseUrl, 
                        onValueChange = { baseUrl = it }, 
                        label = { Text("API Base URL") }, 
                        singleLine = true, 
                        modifier = Modifier.fillMaxWidth(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = MaterialTheme.colorScheme.onSurface,
                            unfocusedTextColor = MaterialTheme.colorScheme.onSurface
                        )
                    )
                    OutlinedTextField(
                        value = apiKey, 
                        onValueChange = { apiKey = it }, 
                        label = { Text("API Key") }, 
                        placeholder = { Text("不填则默认使用公共免费 AI 线路", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f)) },
                        singleLine = true, 
                        modifier = Modifier.fillMaxWidth(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = MaterialTheme.colorScheme.onSurface,
                            unfocusedTextColor = MaterialTheme.colorScheme.onSurface
                        )
                    )
                    OutlinedTextField(
                        value = model, 
                        onValueChange = { model = it }, 
                        label = { Text("Model") }, 
                        singleLine = true, 
                        modifier = Modifier.fillMaxWidth(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = MaterialTheme.colorScheme.onSurface,
                            unfocusedTextColor = MaterialTheme.colorScheme.onSurface
                        )
                    )

                    // 可折叠高级公共中转配置（用于 Laf 或国内免翻墙自建网关）
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { showAdvancedRelay = !showAdvancedRelay }
                            .padding(vertical = 4.dp)
                    ) {
                        Icon(
                            imageVector = if (showAdvancedRelay) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = "公共免 Key 中转网关设置 (Laf / 国内直连)",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.primary,
                            fontWeight = FontWeight.Medium
                        )
                    }

                    if (showAdvancedRelay) {
                        OutlinedTextField(
                            value = publicRelayUrl,
                            onValueChange = { publicRelayUrl = it },
                            label = { Text("免 Key 公共网关 URL") },
                            placeholder = { Text("如 https://xxx.laf.run/v1/chat/completions", fontSize = 11.sp) },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth(),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = MaterialTheme.colorScheme.onSurface,
                                unfocusedTextColor = MaterialTheme.colorScheme.onSurface
                            )
                        )
                    }

                    Text(
                        text = "💡 提示：无需配置 Key 即可直接与阿米娅 AI 对话（默认使用公共免费线路）；支持自定义接入 DeepSeek-R1 / OpenAI 等推理模型，流式展现深度思考过程；离线状态将自动切换为原声陪伴台词。",
                        fontSize = 11.sp,
                        lineHeight = 15.sp,
                        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.85f)
                    )
                    
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedButton(
                        onClick = {
                            showSettingsDialog = false
                            onCheckUpdate()
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Default.CloudDownload, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(6.dp))
                        Text("检查应用更新", fontSize = 13.sp)
                    }

                    Spacer(modifier = Modifier.height(8.dp))
                }
            },
            confirmButton = {
                Button(onClick = {
                    brain.baseUrl = baseUrl
                    brain.apiKey = apiKey
                    brain.model = model
                    brain.publicRelayUrl = publicRelayUrl.trim().ifBlank { AmiyaBrain.DEFAULT_PUBLIC_RELAY_URL }
                    showSettingsDialog = false
                }) {
                    Text("保存", color = Color.Black)
                }
            },
            dismissButton = { TextButton(onClick = { showSettingsDialog = false }) { Text("取消", color = Color.Gray) } }
        )
    }

    if (showGuideDialog) {
        UserGuideDialog(
            onDismiss = {
                prefs.edit().putBoolean("has_seen_guide_v1", true).apply()
                showGuideDialog = false
            }
        )
    }
}

@Composable
fun QuickPromptChip(text: String, onClick: () -> Unit) {
    Box(modifier = Modifier.clip(RoundedCornerShape(12.dp)).background(MaterialTheme.colorScheme.surfaceVariant).clickable(onClick = onClick).padding(horizontal = 10.dp, vertical = 5.dp)) {
        Text(text = text, fontSize = 11.sp, color = MaterialTheme.colorScheme.primary)
    }
}

/**
 * 45° 几何双向战术切角形状 (Rhodes PRTS Tactical Chamfer Shape)
 * 阿米娅气泡：左上、右下切角
 * 博士气泡：右上、左下切角
 */
class TacticalBubbleShape(
    private val chamferDp: Float = 10f,
    private val isUser: Boolean = false
) : Shape {
    override fun createOutline(
        size: Size,
        layoutDirection: LayoutDirection,
        density: Density
    ): Outline {
        val c = chamferDp * density.density
        val w = size.width
        val h = size.height
        val path = Path().apply {
            if (!isUser) {
                // 阿米娅气泡：左上、右下 45° 战术切角
                moveTo(c, 0f)
                lineTo(w, 0f)
                lineTo(w, h - c)
                lineTo(w - c, h)
                lineTo(0f, h)
                lineTo(0f, c)
                close()
            } else {
                // 博士气泡：右上、左下 45° 战术切角
                moveTo(0f, 0f)
                lineTo(w - c, 0f)
                lineTo(w, c)
                lineTo(w, h)
                lineTo(c, h)
                lineTo(0f, h - c)
                close()
            }
        }
        return Outline.Generic(path)
    }
}

/**
 * 微信式左右对称排版 + 方案A【罗德岛战术终端】气泡 + 纯透明底浮动头像
 */
@Composable
fun ChatBubbleItem(message: ChatMessage, isDark: Boolean = true) {
    val isUser = message.role == "user"

    // 方案A 配色自适应系统：
    // 深色模式：阿米娅深炭灰(#161B22) + 荧光青引线(#00E5FF) + 柔白字(#F1F5F9)；博士夜海蓝(#0A2540) + 明青字(#E0F2FE)
    // 浅色模式：阿米娅纯白卡片(#FFFFFF) + 墨青引线(#0284C7) + 深石板炭黑字(#0F172A)；博士清爽冰青蓝(#E0F2FE) + 深海蓝黑字(#082F49)
    val amiyaBg = if (isDark) Color(0xFF161B22) else Color(0xFFFFFFFF)
    val amiyaAccent = if (isDark) Color(0xFF00E5FF) else Color(0xFF0284C7)
    val amiyaText = if (isDark) Color(0xFFF1F5F9) else Color(0xFF0F172A)
    val amiyaBadge = if (isDark) Color(0xFF00E5FF) else Color(0xFF0369A1)

    val doctorBg = if (isDark) Color(0xFF0A2540) else Color(0xFFE0F2FE)
    val doctorAccent = if (isDark) Color(0xFF38BDF8) else Color(0xFF0284C7)
    val doctorText = if (isDark) Color(0xFFE0F2FE) else Color(0xFF082F49)
    val doctorBadge = if (isDark) Color(0xFF38BDF8) else Color(0xFF0369A1)

    val bubbleBg = if (isUser) doctorBg else amiyaBg
    val bubbleAccent = if (isUser) doctorAccent else amiyaAccent
    val bubbleText = if (isUser) doctorText else amiyaText
    val badgeColor = if (isUser) doctorBadge else amiyaBadge

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 3.dp),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
        verticalAlignment = Alignment.Top
    ) {
        // 1. 左侧阿米娅头像：原画捧花笑颜 · 纯透明底自然浮动
        if (!isUser) {
            Image(
                painter = painterResource(id = R.drawable.avatar_amiya),
                contentDescription = "阿米娅",
                modifier = Modifier.size(40.dp)
            )
            Spacer(modifier = Modifier.width(8.dp))
        }

        // 2. 对话气泡内容区域 (PRTS 战术终端标头 + 45° 几何 Chamfer 切角)
        Column(
            horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
        ) {
            // PRTS 战术标头小工牌
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(
                    start = if (isUser) 0.dp else 4.dp,
                    end = if (isUser) 4.dp else 0.dp,
                    bottom = 2.dp
                )
            ) {
                if (!isUser) {
                    Text(
                        text = "◆ ",
                        fontSize = 9.sp,
                        color = badgeColor,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = "AMIYA // PRTS LINK",
                        fontSize = 9.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        color = badgeColor
                    )
                } else {
                    Text(
                        text = "DOCTOR // ACCESS",
                        fontSize = 9.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        color = badgeColor
                    )
                    Text(
                        text = " ◆",
                        fontSize = 9.sp,
                        color = badgeColor,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            // 45° 切角战术气泡实体
            Box(
                modifier = Modifier
                    .widthIn(max = 280.dp)
                    .clip(TacticalBubbleShape(chamferDp = 10f, isUser = isUser))
                    .background(bubbleBg)
                    .drawBehind {
                        // 绘制 2.5dp 战术引线：阿米娅在左侧，博士在右侧
                        val strokeWidth = 2.5.dp.toPx()
                        if (!isUser) {
                            drawLine(
                                color = bubbleAccent,
                                start = Offset(strokeWidth / 2, 0f),
                                end = Offset(strokeWidth / 2, size.height),
                                strokeWidth = strokeWidth
                            )
                        } else {
                            drawLine(
                                color = bubbleAccent,
                                start = Offset(size.width - strokeWidth / 2, 0f),
                                end = Offset(size.width - strokeWidth / 2, size.height),
                                strokeWidth = strokeWidth
                            )
                        }
                    }
                    .padding(
                        start = if (!isUser) 14.dp else 12.dp,
                        end = if (isUser) 14.dp else 12.dp,
                        top = 9.dp,
                        bottom = 9.dp
                    )
            ) {
                Column {
                    if (!isUser) {
                        val hasReasoning = message.reasoningContent.isNotEmpty()
                        val isCurrentlyThinking = message.isStreaming && message.isThinking

                        // 深度思考 (Reasoning / CoT) 折叠卡片
                        if (hasReasoning || isCurrentlyThinking) {
                            var isExpanded by remember { mutableStateOf(message.isStreaming) }
                            val thinkingBg = if (isDark) Color(0xFF0F141C) else Color(0xFFF1F5F9)
                            val thinkingBorder = if (isDark) Color(0xFF1E293B) else Color(0xFFE2E8F0)
                            val thinkingTextColor = if (isDark) Color(0xFF94A3B8) else Color(0xFF475569)

                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(6.dp))
                                    .background(thinkingBg)
                                    .clickable { isExpanded = !isExpanded }
                                    .padding(horizontal = 8.dp, vertical = 6.dp)
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.AutoAwesome,
                                        contentDescription = null,
                                        tint = bubbleAccent,
                                        modifier = Modifier.size(13.dp)
                                    )
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text(
                                        text = if (isCurrentlyThinking) "阿米娅正在深度思考..." else "思考过程",
                                        fontSize = 11.sp,
                                        fontWeight = FontWeight.SemiBold,
                                        fontFamily = FontFamily.Monospace,
                                        color = bubbleAccent
                                    )
                                    Spacer(modifier = Modifier.weight(1f))
                                    if (isCurrentlyThinking) {
                                        CircularProgressIndicator(
                                            modifier = Modifier.size(10.dp),
                                            strokeWidth = 1.5.dp,
                                            color = bubbleAccent
                                        )
                                        Spacer(modifier = Modifier.width(6.dp))
                                    }
                                    Icon(
                                        imageVector = if (isExpanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                                        contentDescription = if (isExpanded) "折叠" else "展开",
                                        tint = thinkingTextColor,
                                        modifier = Modifier.size(14.dp)
                                    )
                                }

                                if (isExpanded) {
                                    Spacer(modifier = Modifier.height(4.dp))
                                    HorizontalDivider(
                                        color = thinkingBorder,
                                        thickness = 0.5.dp
                                    )
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(
                                        text = if (message.reasoningContent.isNotEmpty()) {
                                            message.reasoningContent + if (isCurrentlyThinking) " ▌" else ""
                                        } else {
                                            "正在梳理战术逻辑与数据链路..."
                                        },
                                        fontSize = 11.sp,
                                        lineHeight = 16.sp,
                                        fontFamily = FontFamily.Monospace,
                                        color = thinkingTextColor
                                    )
                                }
                            }

                            if (message.content.isNotEmpty() || (!isCurrentlyThinking && message.isStreaming)) {
                                Spacer(modifier = Modifier.height(8.dp))
                            }
                        }

                        // 回复正文（支持流式光标 ▌）
                        if (message.content.isNotEmpty()) {
                            Text(
                                text = message.content + if (message.isStreaming && !message.isThinking) " ▌" else "",
                                fontSize = 14.sp,
                                lineHeight = 20.sp,
                                color = bubbleText
                            )
                        } else if (message.isStreaming && !message.isThinking) {
                            Text(
                                text = "阿米娅正在组织语言 ▌",
                                fontSize = 13.sp,
                                lineHeight = 18.sp,
                                color = bubbleText.copy(alpha = 0.7f),
                                fontFamily = FontFamily.Monospace
                            )
                        }
                    } else {
                        Text(
                            text = message.content,
                            fontSize = 14.sp,
                            lineHeight = 20.sp,
                            color = bubbleText
                        )
                    }
                }
            }
        }

        // 3. 右侧博士头像：罗德岛战术兜帽 · 纯透明底自然浮动
        if (isUser) {
            Spacer(modifier = Modifier.width(8.dp))
            Image(
                painter = painterResource(id = R.drawable.avatar_doctor),
                contentDescription = "博士",
                modifier = Modifier.size(40.dp)
            )
        }
    }
}
