package com.amiya.pet.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.amiya.pet.core.notes.Note
import com.amiya.pet.core.notes.NotesManager
import kotlinx.coroutines.delay

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NotesScreen() {
    val context = LocalContext.current
    val notesManager = remember { NotesManager.getInstance(context) }
    var notesList by remember { mutableStateOf(notesManager.notes) }
    var currentEditingNote by remember { mutableStateOf<Note?>(null) }

    fun refresh() {
        notesList = notesManager.notes
    }

    if (currentEditingNote != null) {
        NoteEditorView(
            note = currentEditingNote!!,
            onBack = {
                currentEditingNote = null
                refresh()
            },
            onSave = { updatedContent ->
                notesManager.updateNote(currentEditingNote!!.id, updatedContent)
                refresh()
            },
            onDelete = {
                notesManager.deleteNote(currentEditingNote!!.id)
                currentEditingNote = null
                refresh()
            }
        )
    } else {
        Scaffold(
            floatingActionButton = {
                FloatingActionButton(
                    onClick = {
                        val newNote = notesManager.createNote(title = "灵感随记", content = "")
                        currentEditingNote = newNote
                        refresh()
                    },
                    containerColor = MaterialTheme.colorScheme.primary,
                    contentColor = Color.Black
                ) {
                    Icon(Icons.Default.Add, contentDescription = "新建便签")
                }
            },
            containerColor = MaterialTheme.colorScheme.background
        ) { padding ->
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(16.dp)
            ) {
                Text(
                    text = "灵感便签本",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color.White
                )
                Text(
                    text = "共 ${notesList.size} 篇随记 · 输入实时自动防抖存盘",
                    fontSize = 12.sp,
                    color = Color.Gray
                )
                Spacer(modifier = Modifier.height(12.dp))

                if (notesList.isEmpty()) {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Text("点击右下角 ➕ 创建第一条灵感随记", color = Color.Gray, fontSize = 14.sp)
                    }
                } else {
                    LazyColumn(
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                        modifier = Modifier.fillMaxSize()
                    ) {
                        items(notesList, key = { it.id }) { note ->
                            NoteCard(
                                note = note,
                                onClick = { currentEditingNote = note },
                                onTogglePin = {
                                    notesManager.togglePin(note.id)
                                    refresh()
                                }
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun NoteCard(
    note: Note,
    onClick: () -> Unit,
    onTogglePin: () -> Unit
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = RoundedCornerShape(14.dp),
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (note.pinned) {
                        Icon(
                            imageVector = Icons.Default.PushPin,
                            contentDescription = "置顶",
                            tint = Color(0xFFFFD54F),
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                    }
                    Text(
                        text = note.title,
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp,
                        color = Color.White
                    )
                }

                IconButton(
                    onClick = onTogglePin,
                    modifier = Modifier.size(24.dp)
                ) {
                    Icon(
                        imageVector = if (note.pinned) Icons.Default.PushPin else Icons.Default.PushPin,
                        contentDescription = null,
                        tint = if (note.pinned) Color(0xFFFFD54F) else Color.Gray,
                        modifier = Modifier.size(16.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(6.dp))
            val previewText = note.content.ifEmpty { "(空白便签内容)" }
            Text(
                text = previewText,
                fontSize = 13.sp,
                color = Color.LightGray,
                maxLines = 2
            )

            Spacer(modifier = Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "${note.content.length} 字",
                    fontSize = 11.sp,
                    color = Color.Gray
                )
                Text(
                    text = "更新于 ${note.updatedAt}",
                    fontSize = 11.sp,
                    color = Color.Gray
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NoteEditorView(
    note: Note,
    onBack: () -> Unit,
    onSave: (String) -> Unit,
    onDelete: () -> Unit
) {
    var textContent by remember { mutableStateOf(note.content) }
    var saveStatus by remember { mutableStateOf("已保存") }
    var showDeleteConfirm by remember { mutableStateOf(false) }

    // 400ms 防抖自动存盘
    LaunchedEffect(textContent) {
        if (textContent != note.content) {
            saveStatus = "保存中..."
            delay(400L)
            onSave(textContent)
            saveStatus = "已保存"
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = note.autoDeriveTitle(),
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "$saveStatus · ${textContent.length} 字",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    IconButton(onClick = { showDeleteConfirm = true }) {
                        Icon(Icons.Default.Delete, contentDescription = "删除", tint = Color(0xFFFF5252))
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        },
        containerColor = MaterialTheme.colorScheme.background
    ) { padding ->
        TextField(
            value = textContent,
            onValueChange = { textContent = it },
            placeholder = { Text("在此输入便签内容，支持输入即存...", color = Color.Gray) },
            colors = TextFieldDefaults.colors(
                focusedContainerColor = MaterialTheme.colorScheme.background,
                unfocusedContainerColor = MaterialTheme.colorScheme.background,
                focusedIndicatorColor = Color.Transparent,
                unfocusedIndicatorColor = Color.Transparent
            ),
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp, vertical = 8.dp)
        )
    }

    if (showDeleteConfirm) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirm = false },
            title = { Text("删除便签") },
            text = { Text("确定要删除此条灵感随记吗？此操作无法撤回。") },
            confirmButton = {
                TextButton(
                    onClick = {
                        showDeleteConfirm = false
                        onDelete()
                    }
                ) {
                    Text("删除", color = Color(0xFFFF5252))
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteConfirm = false }) {
                    Text("取消")
                }
            }
        )
    }
}
