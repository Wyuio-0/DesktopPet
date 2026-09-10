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
                        tag = "开箱即用"
                    ) {
                        Text(
                            text = "阿米娅已内置公共免费 AI 线路，您无需配置任何 API Key 即可直接与阿米娅进行自然流畅的 AI 智能对话！同时支持接入您的专属大模型以满足个性化需求。",
                            fontSize = 12.sp,
                            lineHeight = 18.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Spacer(modifier = Modifier.height(8.dp))

                        GuideStepItem(
                            step = "A",
                            title = "免配置直接开聊（默认推荐）",
                            desc = "初次安装无需任何繁琐设置，直接在下方输入框发送消息，阿米娅将通过公共免费 AI 线路即刻与您交流；离线时将自动无缝切换为原声陪伴台词。"
                        )
                        GuideStepItem(
                            step = "B",
                            title = "接入专属自定义大模型（进阶可选）",
                            desc = "若您拥有 DeepSeek、Kimi、通义千问等平台专属 API Key，可在右上角 ⚙️「设置」中填入 Base URL、API Key 与 Model，保存后优先使用您自己的大模型。"
                        )
                        GuideStepItem(
                            step = "C",
                            title = "随时自由切换",
                            desc = "若想换回公共免费 AI 线路，只需在设置中将 API Key 清空并保存即可。"
                        )
                    }

                    // Section 2: 课表抓包与自行导入保姆级教程
                    GuideSectionCard(
                        icon = Icons.Default.CalendarMonth,
                        iconColor = Color(0xFF0284C7),
                        title = "2. 课表抓包导入保姆级教程（F12抓包）",
                        tag = "强智/高校教务"
                    ) {
                        Text(
                            text = "阿米娅课表支持自动计算当前周次课程与课前 10 分钟自动提醒。只需按以下 5 步从电脑教务系统抓取一次数据导入即可永久使用：",
                            fontSize = 12.sp,
                            lineHeight = 18.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Spacer(modifier = Modifier.height(8.dp))

                        GuideStepItem(
                            step = "1",
                            title = "电脑登录教务系统进入课表",
                            desc = "在电脑浏览器（推荐 Edge/Chrome）登录学校教务系统，点击进入「个人课表查询」或「学生课表」页面，选好当前学年与学期（如 2026-2027-1），此时先不要点查询。"
                        )
                        GuideStepItem(
                            step = "2",
                            title = "按 F12 打开开发者工具",
                            desc = "在课表页面按键盘 F12 键（部分笔记本按 Fn+F12，或鼠标右键网页空白处选择「检查」）。在弹出的控制台顶部，切换到「Network / 网络」标签栏。"
                        )
                        GuideStepItem(
                            step = "3",
                            title = "点击查询，筛选特殊请求与特征值",
                            desc = "保持 F12 网络面板开启，在网页上点击「查询」按钮触发加载。在 Network 顶部的搜索筛选框（Filter）中输入关键字：xskbcx 或 kbList。请求列表中会出现名为 xskbcx_cxXsksxxlist（或包含 kbcx）的网络请求。"
                        )
                        GuideStepItem(
                            step = "4",
                            title = "核对特殊值并完整复制 Response",
                            desc = "点击该请求，在右侧面板切到「Response / 响应」（或 Preview / 预览）。核对内容必须包含 \"kbList\"、\"kcmc\"（课程名）、\"cdmc\"（教室）、\"zcd\"（周次）等特殊特征值。在响应内容区域右键点击「Copy response（复制响应内容）」或全选复制完整 JSON 数据（以 { 开头、以 } 结尾），通过微信传输助手/QQ发到手机。"
                        )
                        GuideStepItem(
                            step = "5",
                            title = "手机 App 一键导入与周次绑定",
                            desc = "打开本 App 底部「课表」➔ 点击右上角「导入课表」➔ 将复制的 JSON 文本完整粘贴至上方输入框 ➔ 在下方准确输入「开学第 1 周周一」日期（如 2026-09-07，周次计算基准）➔ 点击「开始导入」即可！"
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
