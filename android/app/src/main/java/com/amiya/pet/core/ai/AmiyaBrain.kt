package com.amiya.pet.core.ai

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

data class ChatMessage(
    val role: String,
    val content: String,
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

    private val persona = (
        "你是《明日方舟》中的阿米娅，罗德岛的公开领袖。你温柔、坚定、富有责任感，" +
        "面对博士时既尊敬又亲近。你称呼对方为「博士」，自称「阿米娅」或「我」。" +
        "你说话礼貌、真诚，偶尔流露少女的关心与坚强。回答简洁自然，一般一到三句话，" +
        "像日常手机聊天，不要长篇大论，不要使用括号动作描写或表情符号，只用中文回答。"
    )

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

    suspend fun sendMessage(userText: String): String = withContext(Dispatchers.IO) {
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
                connectTimeout = 12000
                readTimeout = 20000
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                if (authHeader != null) {
                    setRequestProperty("Authorization", authHeader)
                }
                setRequestProperty("User-Agent", "AmiyaPet-Android")
            }

            val reqBody = JSONObject().apply {
                put("model", targetModel)
                put("temperature", 0.75)
                val messages = JSONArray()
                // System Persona
                messages.put(JSONObject().apply {
                    put("role", "system")
                    put("content", persona)
                })
                // 最近 8 轮历史
                val recent = history.takeLast(16)
                for (msg in recent) {
                    messages.put(JSONObject().apply {
                        put("role", msg.role)
                        put("content", msg.content)
                    })
                }
                put("messages", messages)
            }

            OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use {
                it.write(reqBody.toString())
                it.flush()
            }

            if (conn.responseCode in 200..299) {
                val respStr = conn.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
                val respJson = JSONObject(respStr)
                val choices = respJson.optJSONArray("choices")
                if (choices != null && choices.length() > 0) {
                    val choice = choices.getJSONObject(0)
                    val reply = choice.optJSONObject("message")?.optString("content")?.trim() ?: "博士，阿米娅在听呢。"
                    history.add(ChatMessage("assistant", reply))
                    return@withContext reply
                }
            }

            // 响应非 200 时：自定义 Key 提示配置，公共免 Key 则无缝降级为温馨陪伴台词
            val reply = if (isCustomKey) {
                "（通信连接异常[${conn.responseCode}]，博士。请检查 API Key、Base URL 或网络连接。）"
            } else {
                fallbackReplies.random()
            }
            history.add(ChatMessage("assistant", reply))
            reply
        } catch (e: Exception) {
            val reply = if (isCustomKey) {
                "（网络连接出错了，博士稍后再试呢。）"
            } else {
                fallbackReplies.random()
            }
            history.add(ChatMessage("assistant", reply))
            reply
        }
    }

    companion object {
        const val DEFAULT_PUBLIC_RELAY_URL = "https://amiya-ai-relay.wyuio-0.workers.dev/v1/chat/completions"

        @Volatile
        private var INSTANCE: AmiyaBrain? = null

        fun getInstance(context: Context): AmiyaBrain {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: AmiyaBrain(context.applicationContext).also { INSTANCE = it }
            }
        }
    }
}
