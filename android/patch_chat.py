
import re
with open("app/src/main/java/com/amiya/pet/ui/ChatView.kt", "r", encoding="utf-8") as f:
    text = f.read()

# We need to completely rewrite the file content.
new_content = """package com.amiya.pet.ui

import android.content.Context
import android.content.Intent
import android.view.ViewGroup
import android.widget.FrameLayout
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.amiya.pet.core.ai.AmiyaBrain
import com.amiya.pet.core.ai.ChatMessage
import com.amiya.pet.core.parser.CharacterParser
import com.amiya.pet.core.state.PetStateListener
import com.amiya.pet.core.state.PetStateMachine
import com.amiya.pet.core.model.Action
import com.amiya.pet.core.voice.VoicePlayer
import com.amiya.pet.render.PetGlSurfaceView
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val prefs = remember { context.getSharedPreferences("amiya_pet_prefs", Context.MODE_PRIVATE) }
    val brain = remember { AmiyaBrain.getInstance(context) }
    var chatList by remember { mutableStateOf(brain.chatHistory) }
    var inputText by remember { mutableStateOf("") }
    var isSending by remember { mutableStateOf(false) }
    var showSettingsDialog by remember { mutableStateOf(false) }
    var showCharDialog by remember { mutableStateOf(false) }

    var selectedChar by remember { mutableStateOf(prefs.getString("pref_character", "amiya") ?: "amiya") }
    var currentSpeed by remember { mutableFloatStateOf(prefs.getFloat("pref_speed", 1.15f)) }
    var currentVolume by remember { mutableFloatStateOf(prefs.getFloat("pref_voice_volume", 0.8f)) }
    var isVoiceMuted by remember { mutableStateOf(prefs.getBoolean("pref_voice_muted", false)) }

    val listState = rememberLazyListState()

    // Setup Pet
    val voicePlayer = remember { VoicePlayer(context) }
    var stateMachine by remember { mutableStateOf<PetStateMachine?>(null) }
    var petView by remember { mutableStateOf<PetGlSurfaceView?>(null) }

    DisposableEffect(selectedChar, currentSpeed, isVoiceMuted, currentVolume) {
        voicePlayer.isMuted = isVoiceMuted
        voicePlayer.volume = currentVolume
        voicePlayer.loadCharacterVoices(selectedChar)
        
        onDispose { }
    }

    DisposableEffect(selectedChar) {
        val character = CharacterParser.loadCharacter(context, selectedChar) ?: CharacterParser.loadCharacter(context, "amiya")!!
        val listener = object : PetStateListener {
            override fun onActionStarted(action: Action, clipPath: String) {
                petView?.playAsset(clipPath, action.loop, currentSpeed)
            }
            override fun onBubbleMessage(text: String) {}
            override fun onUserInteraction(type: String) {}
        }
        stateMachine?.destroy()
        val machine = PetStateMachine(character, listener)
        stateMachine = machine
        machine.start()
        
        onDispose {
            machine.destroy()
        }
    }
    
    DisposableEffect(currentSpeed) {
        petView?.setSpeed(currentSpeed)
        onDispose {}
    }

    fun sendMessage(msg: String) {
        val trimmed = msg.trim()
        if (trimmed.isEmpty() || isSending) return
        inputText = ""
        isSending = true
        scope.launch {
            val reply = brain.sendMessage(trimmed)
            chatList = brain.chatHistory
            isSending = false
            if (chatList.isNotEmpty()) {
                listState.animateScrollToItem(chatList.size - 1)
            }
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
                    IconButton(onClick = { showCharDialog = true }) {
                        Icon(Icons.Default.Person, contentDescription = "切换角色", tint = Color.LightGray)
                    }
                    IconButton(onClick = { showSettingsDialog = true }) {
                        Icon(Icons.Default.Settings, contentDescription = "设置", tint = Color.LightGray)
                    }
                    IconButton(onClick = {
                        brain.clearHistory()
                        chatList = emptyList()
                    }) {
                        Icon(Icons.Default.DeleteOutline, contentDescription = "清空对话", tint = Color.LightGray)
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
            // Pet rendering area
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(200.dp)
                    .background(Color(0xFF161920))
                    .pointerInput(Unit) {
                        detectTapGestures(
                            onTap = { 
                                stateMachine?.onUserInteraction("click")
                                voicePlayer.playClickVoice()
                            },
                            onDoubleTap = { 
                                stateMachine?.onUserInteraction("double_click")
                                voicePlayer.playGreetVoice()
                            }
                        )
                    },
                contentAlignment = Alignment.Center
            ) {
                AndroidView(
                    factory = { ctx ->
                        PetGlSurfaceView(ctx).apply {
                            layoutParams = FrameLayout.LayoutParams(
                                ViewGroup.LayoutParams.MATCH_PARENT,
                                ViewGroup.LayoutParams.MATCH_PARENT
                            )
                            onPlaybackEnded = {
                                stateMachine?.onClipPlaybackEnded()
                            }
                            petView = this
                        }
                    },
                    modifier = Modifier.fillMaxSize()
                )
            }
            
            Spacer(modifier = Modifier.height(1.dp).fillMaxWidth().background(Color(0xFF2A2E38)))

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
                        Text("随时准备听您诉说。", color = Color.LightGray, fontSize = 15.sp, fontWeight = FontWeight.Medium)
                    }
                } else {
                    LazyColumn(
                        state = listState,
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                        modifier = Modifier.fillMaxSize()
                    ) {
                        items(chatList) { message ->
                            ChatBubbleItem(message = message)
                        }
                    }
                }
            }

            // Quick prompts
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                QuickPromptChip("辛苦了", { sendMessage("辛苦了") })
                QuickPromptChip("帮我提个建议", { sendMessage("帮我提个建议") })
                QuickPromptChip("有什么安排？", { sendMessage("有什么安排？") })
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
                        focusedBorderColor = MaterialTheme.colorScheme.primary,
                        unfocusedBorderColor = Color(0xFF3A4050)
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
                        .background(if (inputText.isNotBlank()) MaterialTheme.colorScheme.primary else Color(0xFF2A2E38))
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

    if (showCharDialog) {
        val availableChars = remember {
            val list = CharacterParser.listCharacters(context).map { key ->
                val char = CharacterParser.loadCharacter(context, key)
                key to (char?.displayName ?: key)
            }
            if (list.isNotEmpty()) list else listOf("amiya" to "阿米娅")
        }
        
        AlertDialog(
            onDismissRequest = { showCharDialog = false },
            containerColor = MaterialTheme.colorScheme.surface,
            title = { Text("切换角色", color = Color.White) },
            text = {
                Column {
                    availableChars.forEach { (key, name) ->
                        val isSelected = (key == selectedChar)
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 4.dp)
                                .clip(RoundedCornerShape(8.dp))
                                .background(if (isSelected) MaterialTheme.colorScheme.primary.copy(alpha = 0.2f) else Color.Transparent)
                                .clickable {
                                    selectedChar = key
                                    prefs.edit().putString("pref_character", key).apply()
                                    showCharDialog = false
                                }
                                .padding(12.dp)
                        ) {
                            Text(name, color = if (isSelected) MaterialTheme.colorScheme.primary else Color.White)
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { showCharDialog = false }) { Text("关闭") } }
        )
    }

    if (showSettingsDialog) {
        var baseUrl by remember { mutableStateOf(brain.baseUrl) }
        var apiKey by remember { mutableStateOf(brain.apiKey) }
        var model by remember { mutableStateOf(brain.model) }

        AlertDialog(
            onDismissRequest = { showSettingsDialog = false },
            containerColor = MaterialTheme.colorScheme.surface,
            title = { Text("桌宠综合设置", fontWeight = FontWeight.Bold, color = Color.White) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("AI 模型配置", color = MaterialTheme.colorScheme.primary, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                    OutlinedTextField(value = baseUrl, onValueChange = { baseUrl = it }, label = { Text("API Base URL") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = apiKey, onValueChange = { apiKey = it }, label = { Text("API Key") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = model, onValueChange = { model = it }, label = { Text("Model") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("桌宠声音与速度", color = MaterialTheme.colorScheme.primary, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                    
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                        Text("静音台词语音", color = Color.White, fontSize = 14.sp)
                        Switch(checked = isVoiceMuted, onCheckedChange = { 
                            isVoiceMuted = it
                            prefs.edit().putBoolean("pref_voice_muted", it).apply()
                        })
                    }
                    if (!isVoiceMuted) {
                        Text("音量", color = Color.Gray, fontSize = 12.sp)
                        Slider(value = currentVolume, onValueChange = { 
                            currentVolume = it
                            prefs.edit().putFloat("pref_voice_volume", it).apply()
                        }, valueRange = 0f..1f)
                    }
                    
                    Text("动作速度 (%.2fx)".format(currentSpeed), color = Color.Gray, fontSize = 12.sp)
                    Slider(value = currentSpeed, onValueChange = { 
                        currentSpeed = it
                        prefs.edit().putFloat("pref_speed", it).apply()
                    }, valueRange = 0.5f..2f, steps = 14)
                }
            },
            confirmButton = {
                Button(onClick = {
                    brain.baseUrl = baseUrl
                    brain.apiKey = apiKey
                    brain.model = model
                    showSettingsDialog = false
                }) {
                    Text("保存", color = Color.Black)
                }
            },
            dismissButton = { TextButton(onClick = { showSettingsDialog = false }) { Text("取消", color = Color.Gray) } }
        )
    }
}

@Composable
fun QuickPromptChip(text: String, onClick: () -> Unit) {
    Box(modifier = Modifier.clip(RoundedCornerShape(12.dp)).background(Color(0xFF252A36)).clickable(onClick = onClick).padding(horizontal = 10.dp, vertical = 5.dp)) {
        Text(text = text, fontSize = 11.sp, color = Color(0xFF80D8FF))
    }
}

@Composable
fun ChatBubbleItem(message: ChatMessage) {
    val isUser = message.role == "user"
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start) {
        Box(
            modifier = Modifier.widthIn(max = 280.dp)
                .clip(RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomStart = if (isUser) 16.dp else 2.dp, bottomEnd = if (isUser) 2.dp else 16.dp))
                .background(if (isUser) MaterialTheme.colorScheme.primary else Color(0xFF222632))
                .padding(horizontal = 14.dp, vertical = 10.dp)
        ) {
            Text(text = message.content, fontSize = 14.sp, color = if (isUser) Color.Black else Color(0xFFECEFF1))
        }
    }
}
"""

with open("app/src/main/java/com/amiya/pet/ui/ChatView.kt", "w", encoding="utf-8") as f:
    f.write(new_content)

