package com.amiya.pet.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties

@Composable
fun UserGuideDialog(onDismiss: () -> Unit) {
    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Card(
            modifier = Modifier
                .fillMaxWidth(0.92f)
                .fillMaxHeight(0.85f),
            shape = RoundedCornerShape(24.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            elevation = CardDefaults.cardElevation(defaultElevation = 10.dp)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(20.dp)
            ) {
                // Header
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Box(
                        modifier = Modifier
                            .size(40.dp)
                            .clip(RoundedCornerShape(12.dp))
                            .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.18f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Campaign,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(24.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "欢迎使用阿米娅助理",
                            fontWeight = FontWeight.Bold,
                            fontSize = 17.sp,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        Text(
                            text = "快速上手指南 & 核心功能公告",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.primary,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                    IconButton(
                        onClick = onDismiss,
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "关闭",
                            tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))
                HorizontalDivider(color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.08f))
                Spacer(modifier = Modifier.height(12.dp))

                // Scrollable Content
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    // Section 1: API Key 接入教程
                    GuideSectionCard(
                        icon = Icons.Default.Key,
                        iconColor = Color(0xFFF59E0B),
                        title = "1. AI 对话与 API Key 配置教程",
                        tag = "核心配置"
                    ) {
                        Text(
                            text = "本应用采用兼容 OpenAI 标准的大模型通讯接口，您可以接入自己喜爱的大模型让阿米娅具备强大的日常闲聊、日程规划与答疑能力。",
                            fontSize = 12.sp,
                            lineHeight = 18.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Spacer(modifier = Modifier.height(8.dp))

                        GuideStepItem(
                            step = "A",
                            title = "获取 API Key（推荐 DeepSeek）",
                            desc = "前往大模型开放平台（如 platform.deepseek.com）注册并创建 API Key（支持 DeepSeek、Kimi、通义千问等兼容平台，性价比极高）。"
                        )
                        GuideStepItem(
                            step = "B",
                            title = "在应用中填写配置",
                            desc = "在对话界面右上角点击齿轮 ⚙️「设置」按钮，分别填入：\n• API Base URL：https://api.deepseek.com\n• API Key：sk-xxxxxxxxxxxx\n• Model：deepseek-chat（或 deepseek-reasoner）"
                        )
                        GuideStepItem(
                            step = "C",
                            title = "保存并测试",
                            desc = "点击「保存」后即可在对话框中给阿米娅发送任意消息测试回复。若未配置 API Key，阿米娅将使用内置语音台词给您温馨陪伴回复。"
                        )
                    }

                    // Section 2: 课表自行导入教程
                    GuideSectionCard(
                        icon = Icons.Default.CalendarMonth,
                        iconColor = Color(0xFF0284C7),
                        title = "2. 智能课表管理与自行导入教程",
                        tag = "教务导入"
                    ) {
                        Text(
                            text = "课表系统能够自动根据当前开学周次计算今日课程，并在上课前通过前台服务发送提醒通知，支持左右滑动切换周次。",
                            fontSize = 12.sp,
                            lineHeight = 18.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Spacer(modifier = Modifier.height(8.dp))

                        GuideStepItem(
                            step = "A",
                            title = "进入课表导入面板",
                            desc = "点击底部导航栏第二个标签「课表」，点击右上角带有下载图标的「导入课表」按钮。"
                        )
                        GuideStepItem(
                            step = "B",
                            title = "粘贴教务 JSON 数据与开学日期",
                            desc = "在上方文本框粘贴强智等教务系统抓包所得的课表 JSON 数据，并在下方输入「开学第一周周一」日期（格式为 YYYY-MM-DD，如 2026-09-01）。"
                        )
                        GuideStepItem(
                            step = "C",
                            title = "解析与日常查看",
                            desc = "点击「开始导入」，应用会自动解析课程名、教室、周次与节次。点击课表左侧节次数字可切换上下课具体作息时间显示。"
                        )
                    }

                    // Section 3: 其他核心功能介绍
                    GuideSectionCard(
                        icon = Icons.Default.Widgets,
                        iconColor = Color(0xFF10B981),
                        title = "3. 更多实用功能速览",
                        tag = "罗德岛工坊"
                    ) {
                        FeatureBulletItem(
                            icon = Icons.Default.ChatBubbleOutline,
                            title = "PRTS 战术切角对话",
                            desc = "45° 机能 Chamfer 切角气泡，阿米娅捧花笑颜纯透明底原画头像，提供底部快捷预设提问（辛苦了/提个建议等）。"
                        )
                        FeatureBulletItem(
                            icon = Icons.Default.LightMode,
                            title = "浅色 / 深色模式一键切换",
                            desc = "点击顶部太阳/月亮按键即可自由切换日间战术纸质卡片与深夜静谧护眼机能终端，完全自适应跟随系统。"
                        )
                        FeatureBulletItem(
                            icon = Icons.Default.EditNote,
                            title = "灵感便签 (底部导航)",
                            desc = "随时随手记录工作日志与待办备忘，实时自动保存，支持彩色标签与分类查找。"
                        )
                        FeatureBulletItem(
                            icon = Icons.Default.Timer,
                            title = "专注番茄钟 (底部导航)",
                            desc = "罗德岛定制专注训练计时器，支持前台服务保活运行、震动提醒与自定义专注时段。"
                        )
                        FeatureBulletItem(
                            icon = Icons.Default.CloudDownload,
                            title = "一键检查应用更新",
                            desc = "点击顶部云朵图标或在设置内随时检测 GitHub 官方 Release 最新安装包，直连高速下载。"
                        )
                    }

                    // Bottom Tips Card
                    Surface(
                        shape = RoundedCornerShape(14.dp),
                        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.08f),
                        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.25f))
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "💡",
                                fontSize = 16.sp
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = "小提示：随时点击对话界面顶部的喇叭图标，即可重新唤起这份使用说明与公告！",
                                fontSize = 11.sp,
                                lineHeight = 16.sp,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                // Confirm / Dismiss Button
                Button(
                    onClick = onDismiss,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp),
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.primary,
                        contentColor = Color.Black
                    )
                ) {
                    Text(
                        text = "我知道了 · 开始使用",
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp
                    )
                }
            }
        }
    }
}

@Composable
private fun GuideSectionCard(
    icon: ImageVector,
    iconColor: Color,
    title: String,
    tag: String,
    content: @Composable ColumnScope.() -> Unit
) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outline.copy(alpha = 0.15f)
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = iconColor,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = title,
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp,
                    color = MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.weight(1f)
                )
                Surface(
                    shape = RoundedCornerShape(6.dp),
                    color = iconColor.copy(alpha = 0.15f)
                ) {
                    Text(
                        text = tag,
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Bold,
                        color = iconColor,
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(10.dp))
            content()
        }
    }
}

@Composable
private fun GuideStepItem(step: String, title: String, desc: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.Top
    ) {
        Box(
            modifier = Modifier
                .size(20.dp)
                .clip(RoundedCornerShape(6.dp))
                .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.2f)),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = step,
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary
            )
        }
        Spacer(modifier = Modifier.width(8.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = desc,
                fontSize = 11.sp,
                lineHeight = 16.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun FeatureBulletItem(icon: ImageVector, title: String, desc: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.Top
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier
                .size(16.dp)
                .padding(top = 2.dp)
        )
        Spacer(modifier = Modifier.width(8.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = desc,
                fontSize = 11.sp,
                lineHeight = 16.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
