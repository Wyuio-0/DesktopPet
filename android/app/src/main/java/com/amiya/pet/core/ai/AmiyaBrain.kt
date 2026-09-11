package com.amiya.pet.core.ai

import android.content.Context
import com.amiya.pet.core.schedule.ScheduleManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class ChatMessage(
    val role: String,
    val content: String,
    val reasoningContent: String = "",
    val isThinking: Boolean = false,
    val isStreaming: Boolean = false,
    val timestamp: Long = System.currentTimeMillis()
)

class AmiyaBrain private constructor(private val context: Context) {

    private val prefs = context.getSharedPreferences("amiya_ai_prefs", Context.MODE_PRIVATE)

    var baseUrl: String
        get() = prefs.getString("base_url", "https://api.deepseek.com") ?: "https://api.deepseek.com"
        set(value) = prefs.edit().putString("base_url", value.trim()).apply()

    var apiKey: String
        get() = prefs.getString("api_key", "") ?: ""
        set(value) = prefs.edit().putString("api_key", value.trim()).apply()

    var model: String
        get() = prefs.getString("model", "deepseek-chat") ?: "deepseek-chat"
        set(value) = prefs.edit().putString("model", value.trim()).apply()

    /**
     * 公共免 Key 线路端点（基于 Cloudflare Worker 或统一代理）
     */
    var publicRelayUrl: String
        get() = prefs.getString("public_relay_url", DEFAULT_PUBLIC_RELAY_URL) ?: DEFAULT_PUBLIC_RELAY_URL
        set(value) = prefs.edit().putString("public_relay_url", value.trim()).apply()

    private fun buildSystemPrompt(): String = buildString {
        append(
            "你是《明日方舟》中的阿米娅，罗德岛的公开领袖。你温柔、坚定、富有责任感，" +
            "面对博士时既尊敬又亲近。你称呼对方为「博士」，自称「阿米娅」或「我」。" +
            "你说话礼貌、真诚，偶尔流露少女的关心与坚强。不要使用括号动作描写或表情符号，只用中文回答。\n" +
            "【表达规范】：日常闲聊与日常互动时回答简洁自然（一般一到三句话），像日常手机聊天；但当博士询问学情分析、课表建议、复习备考或作息规划等需要深度指导的问题时，请条理清晰、层次分明地展开专业分析并给出切实可行的规划与关怀建议。"
        )

        // 现实时间感知
        val sdf = SimpleDateFormat("yyyy-MM-dd EEEE HH:mm", Locale.CHINESE)
        append("\n\n【当前现实时间】：").append(sdf.format(Date()))

        // 课表与学情真实数据注入
        val scheduleDossier = ScheduleManager.buildScheduleAnalysisContext(context)
        if (scheduleDossier.isNotEmpty()) {
            append("\n\n").append(scheduleDossier).append("\n\n")
            append(
                "【学情分析与学业指导规范】：\n" +
                "1. 博士已将其在教务系统导入的真实课表数据同步至罗德岛 PRTS 神经元。当博士询问今天/明天/本周的课程、课表概况、学情分析或学习作息建议时，必须严格基于上述真实课表数据回答；\n" +
                "2. 做学情分析时，请评估整体学业负荷（总课时与修读门数），分析课程节奏（指出高负荷密集日与空闲自习日），指出重难点学科的复习时间窗口，并从作息调理与罗德岛领袖的关怀角度给出切实可行的 3~4 条建议；\n" +
                "3. 若博士询问某具体课程的时间地点或下一节课，请准确告知节次、时间与教学楼/教室。"
            )
        }
    }

    private val fallbackReplies = listOf(
        "博士，您辛苦了。有什么需要阿米娅协助的吗？",
        "罗德岛随时待命。今天的工作也请一起加油吧，博士！",
        "无论前路如何，阿米娅都会一直陪在博士身边。",
        "请适当休息一会儿，博士，阿米娅给您准备了热茶。",
        "博士，今天的干员训练计划已经安排妥当了。",
        "只要博士还愿意前行，罗德岛的航向就不会迷失。",
        "工作再忙碌，也别忘了按时休息呀，博士。"
    )

    private val history = mutableListOf<ChatMessage>()
    val chatHistory: List<ChatMessage> get() = history.toList()

    fun clearHistory() {
        history.clear()
    }

    suspend fun sendMessage(userText: String): String {
        return sendMessageStream(userText) { _, _, _ -> }
    }

    suspend fun sendMessageStream(
        userText: String,
        onUpdate: (reasoning: String, content: String, isThinking: Boolean) -> Unit
    ): String = withContext(Dispatchers.IO) {
        val trimmed = userText.trim()
        if (trimmed.isEmpty()) return@withContext ""

        history.add(ChatMessage("user", trimmed))

        val customKey = apiKey.trim()
        val isCustomKey = customKey.isNotEmpty()

        // 确定访问端点与模型：若配置了自定义 Key 优先走自定义，否则走公共免费 AI 线路
        val endpoint: String
        val targetModel: String
        val authHeader: String?

        if (isCustomKey) {
            val base = baseUrl.trim()
            endpoint = if (base.endsWith("/chat/completions")) base
                       else if (base.endsWith("/")) "${base}v1/chat/completions"
                       else if (base.endsWith("/v1")) "$base/chat/completions"
                       else "$base/v1/chat/completions"
            targetModel = model.ifBlank { "deepseek-chat" }
            authHeader = "Bearer $customKey"
        } else {
            val relay = publicRelayUrl.trim().ifBlank { DEFAULT_PUBLIC_RELAY_URL }
            endpoint = if (relay.endsWith("/chat/completions")) relay
                       else if (relay.endsWith("/")) "${relay}v1/chat/completions"
                       else if (relay.endsWith("/v1")) "$relay/chat/completions"
                       else "$relay/v1/chat/completions"
            targetModel = "glm-4-flash"
            authHeader = null // 由 Worker 云端自动注入免费 Key
        }

        try {
            val url = URL(endpoint)
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 15000
                readTimeout = 60000 // 流式传输支持最长 60s 响应读取
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "text/event-stream")
                if (authHeader != null) {
                    setRequestProperty("Authorization", authHeader)
                }
                setRequestProperty("User-Agent", "AmiyaPet-Android")
            }

            val reqBody = JSONObject().apply {
                put("model", targetModel)
                put("temperature", 0.75)
                put("stream", true)
                val messages = JSONArray()
                // System Persona & Real-time Knowledge
                messages.put(JSONObject().apply {
                    put("role", "system")
                    put("content", buildSystemPrompt())
                })
                // 最近 8 轮历史（仅发送最终文本，不包含 CoT 思考过程避免 prompt 污染）
                val recent = history.takeLast(16)
                for (msg in recent) {
                    if (msg.content.isNotBlank()) {
                        messages.put(JSONObject().apply {
                            put("role", msg.role)
                            put("content", msg.content)
                        })
                    }
                }
                put("messages", messages)
            }

            OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use {
                it.write(reqBody.toString())
                it.flush()
            }

            if (conn.responseCode in 200..299) {
                val reader = conn.inputStream.bufferedReader(Charsets.UTF_8)
                val accumulatedReasoning = StringBuilder()
                val accumulatedContent = StringBuilder()
                var inThinkTag = false
                var isThinking = false

                var line = reader.readLine()
                while (line != null) {
                    val trimmedLine = line.trim()
                    if (trimmedLine.startsWith("data:")) {
                        val data = trimmedLine.removePrefix("data:").trim()
                        if (data == "[DONE]") {
                            break
                        }
                        if (data.isNotEmpty()) {
                            try {
                                val json = JSONObject(data)
                                val choices = json.optJSONArray("choices")
                                if (choices != null && choices.length() > 0) {
                                    val delta = choices.getJSONObject(0).optJSONObject("delta")
                                    if (delta != null) {
                                        // 1. 检查 reasoning_content 字段 (DeepSeek-R1 / SiliconFlow / OpenAI 官方标准)
                                        val reasoningChunk = delta.optString("reasoning_content", "")
                                        if (reasoningChunk.isNotEmpty()) {
                                            accumulatedReasoning.append(reasoningChunk)
                                            isThinking = true
                                            onUpdate(accumulatedReasoning.toString(), accumulatedContent.toString(), true)
                                        }

                                        // 2. 检查 content 字段
                                        val contentChunk = delta.optString("content", "")
                                        if (contentChunk.isNotEmpty()) {
                                            // 解析可能包含在 content 中的 <think> ... </think> 标签（兼容直接返回 think 标签的开源模型）
                                            var remaining = contentChunk
                                            while (remaining.isNotEmpty()) {
                                                if (!inThinkTag) {
                                                    val thinkStart = remaining.indexOf("<think>")
                                                    if (thinkStart != -1) {
                                                        accumulatedContent.append(remaining.substring(0, thinkStart))
                                                        inThinkTag = true
                                                        isThinking = true
                                                        remaining = remaining.substring(thinkStart + "<think>".length)
                                                    } else {
                                                        accumulatedContent.append(remaining)
                                                        isThinking = false
                                                        remaining = ""
                                                    }
                                                } else {
                                                    val thinkEnd = remaining.indexOf("</think>")
                                                    if (thinkEnd != -1) {
                                                        accumulatedReasoning.append(remaining.substring(0, thinkEnd))
                                                        inThinkTag = false
                                                        isThinking = false
                                                        remaining = remaining.substring(thinkEnd + "</think>".length)
                                                    } else {
                                                        accumulatedReasoning.append(remaining)
                                                        isThinking = true
                                                        remaining = ""
                                                    }
                                                }
                                            }
                                            onUpdate(accumulatedReasoning.toString(), accumulatedContent.toString(), isThinking)
                                        }
                                    }
                                }
                            } catch (ignored: Exception) {
                            }
                        }
                    }
                    line = reader.readLine()
                }

                val finalReasoning = accumulatedReasoning.toString().trim()
                val finalContent = accumulatedContent.toString().trim()
                val finalReply = if (finalContent.isNotEmpty()) finalContent else if (finalReasoning.isNotEmpty()) "（思考完毕）" else "博士，阿米娅在听呢。"

                history.add(ChatMessage("assistant", finalReply, reasoningContent = finalReasoning))
                return@withContext finalReply
            }

            // 响应非 200 时：自定义 Key 提示配置，公共免 Key 则无缝降级为温馨陪伴台词
            val reply = if (isCustomKey) {
                "（通信连接异常[${conn.responseCode}]，博士。请检查 API Key、Base URL 或网络连接。）"
            } else {
                fallbackReplies.random()
            }
            history.add(ChatMessage("assistant", reply))
            onUpdate("", reply, false)
            reply
        } catch (e: Exception) {
            val reply = if (isCustomKey) {
                "（网络连接出错了，博士稍后再试呢。）"
            } else {
                fallbackReplies.random()
            }
            history.add(ChatMessage("assistant", reply))
            onUpdate("", reply, false)
            reply
        }
    }

    companion object {
        const val DEFAULT_PUBLIC_RELAY_URL = "https://wmntwvrw57.sealosbja.site/v1/chat/completions"

        @Volatile
        private var INSTANCE: AmiyaBrain? = null

        fun getInstance(context: Context): AmiyaBrain {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: AmiyaBrain(context.applicationContext).also { INSTANCE = it }
            }
        }
    }
}
