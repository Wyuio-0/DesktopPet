package com.amiya.pet.core.sync

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import com.amiya.pet.core.notes.Note
import com.amiya.pet.core.notes.NotesManager
import com.amiya.pet.core.schedule.Course
import com.amiya.pet.core.schedule.ExamItem
import com.amiya.pet.core.schedule.ExamManager
import com.amiya.pet.core.schedule.ScheduleManager
import com.amiya.pet.floating.FloatingPetManager
import com.amiya.pet.widget.ScheduleWidgetProvider
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.*
import java.text.SimpleDateFormat
import java.util.*
import java.util.concurrent.ConcurrentHashMap

/**
 * 罗德岛跨端协同管理核心单例 (Android 端)
 */
object SyncManager {

    const val DEFAULT_HTTP_PORT = 23334
    const val DEFAULT_UDP_PORT = 23332
    private const val PREFS_SYNC = "amiya_paired_devices"

    var localHttpPort = DEFAULT_HTTP_PORT
        private set

    var isServerRunning = false
        private set

    private var serverSocket: ServerSocket? = null
    private var serverJob: Job? = null
    private var udpJob: Job? = null
    private val mainScope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private val ioScope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    // 待确认配对请求映射 requestId -> CompletableDeferred<Boolean>
    private val pendingPairRequests = ConcurrentHashMap<String, CompletableDeferred<Boolean>>()
    private val pendingPairModels = ConcurrentHashMap<String, PairRequest>()

    // UI 配对弹窗回调监听器
    var onPairRequestedListener: ((PairRequest) -> Unit)? = null

    // 快传与状态回调
    var onTacticalDropReceived: ((String, String) -> Unit)? = null
    var onDataSyncedListener: ((SyncReport) -> Unit)? = null
    var onDevicesChangedListener: (() -> Unit)? = null

    /**
     * 启动局域网互联服务（HTTP Server 与 UDP 监听）
     */
    fun start(context: Context) {
        if (isServerRunning) return
        isServerRunning = true

        // 1. 启动轻量 HTTP 服务端
        serverJob = ioScope.launch {
            for (port in DEFAULT_HTTP_PORT..(DEFAULT_HTTP_PORT + 10)) {
                try {
                    serverSocket = ServerSocket(port)
                    localHttpPort = port
                    break
                } catch (e: Exception) {
                    continue
                }
            }

            val socket = serverSocket ?: return@launch
            while (isActive && !socket.isClosed) {
                try {
                    val client = socket.accept()
                    ioScope.launch {
                        handleClientConnection(context.applicationContext, client)
                    }
                } catch (e: Exception) {
                    break
                }
            }
        }

        // 2. 启动 UDP 发现监听
        udpJob = ioScope.launch {
            var udpSocket: DatagramSocket? = null
            try {
                udpSocket = DatagramSocket(null).apply {
                    reuseAddress = true
                    bind(InetSocketAddress(DEFAULT_UDP_PORT))
                }
                val buffer = ByteArray(2048)
                while (isActive && !udpSocket.isClosed) {
                    val packet = DatagramPacket(buffer, buffer.size)
                    udpSocket.receive(packet)
                    val dataStr = String(packet.data, 0, packet.length, Charsets.UTF_8)
                    try {
                        val json = JSONObject(dataStr)
                        if (json.optString("cmd") == "DISCOVER") {
                            val replyJson = JSONObject().apply {
                                put("cmd", "DISCOVER_ACK")
                                put("device_id", getMyDeviceId(context))
                                put("device_name", getMyDeviceName(context))
                                put("device_type", "android")
                                put("http_port", localHttpPort)
                                put("version", "1.9.0")
                            }
                            val replyBytes = replyJson.toString().toByteArray(Charsets.UTF_8)
                            val replyPacket = DatagramPacket(replyBytes, replyBytes.size, packet.address, packet.port)
                            udpSocket.send(replyPacket)
                        }
                    } catch (_: Exception) {}
                }
            } catch (_: Exception) {
            } finally {
                try { udpSocket?.close() } catch (_: Exception) {}
            }
        }
    }

    /**
     * 停止服务
     */
    fun stop() {
        isServerRunning = false
        serverJob?.cancel()
        udpJob?.cancel()
        try { serverSocket?.close() } catch (_: Exception) {}
        serverSocket = null
    }

    // ── HTTP 请求分发处理 ─────────────────────────────────────────────

    private suspend fun handleClientConnection(context: Context, client: Socket) = withContext(Dispatchers.IO) {
        try {
            client.soTimeout = 30000
            val reader = BufferedReader(InputStreamReader(client.getInputStream(), Charsets.UTF_8))
            val firstLine = reader.readLine() ?: return@withContext
            val parts = firstLine.split(" ")
            if (parts.size < 2) return@withContext
            val method = parts[0].uppercase()
            val uri = parts[1]

            val headers = mutableMapOf<String, String>()
            var line: String?
            while (reader.readLine().also { line = it } != null) {
                if (line.isNullOrEmpty()) break
                val idx = line!!.indexOf(":")
                if (idx != -1) {
                    val k = line!!.substring(0, idx).trim().lowercase()
                    val v = line!!.substring(idx + 1).trim()
                    headers[k] = v
                }
            }

            var postBody = ""
            val contentLength = headers["content-length"]?.toIntOrNull() ?: 0
            if (contentLength > 0) {
                val chars = CharArray(contentLength)
                var readCount = 0
                while (readCount < contentLength) {
                    val count = reader.read(chars, readCount, contentLength - readCount)
                    if (count == -1) break
                    readCount += count
                }
                postBody = String(chars, 0, readCount)
            }

            // 路由处理
            val clientIp = client.inetAddress.hostAddress ?: "127.0.0.1"
            val response = routeRequest(context, method, uri, headers, postBody, clientIp)
            val writer = OutputStreamWriter(client.getOutputStream(), Charsets.UTF_8)
            writer.write(response)
            writer.flush()
        } catch (_: Exception) {
        } finally {
            try { client.close() } catch (_: Exception) {}
        }
    }

    private suspend fun routeRequest(
        context: Context,
        method: String,
        uri: String,
        headers: Map<String, String>,
        body: String,
        clientIp: String
    ): String {
        val path = if (uri.contains("?")) uri.substring(0, uri.indexOf("?")) else uri

        if (method == "OPTIONS") {
            return makeHttpResponse(200, "OK", "{}")
        }

        // 1. 公开接口：设备探测
        if (method == "GET" && path == "/api/info") {
            val res = JSONObject().apply {
                put("device_id", getMyDeviceId(context))
                put("device_name", getMyDeviceName(context))
                put("device_type", "android")
                put("http_port", localHttpPort)
                put("version", "1.9.0")
                put("paired", getTrustedDevices(context).isNotEmpty())
            }
            return makeHttpResponse(200, "OK", res.toString())
        }

        // 2. 蓝牙式配对握手请求：必须屏幕确认
        if (method == "POST" && path == "/api/pair/request") {
            return handlePairRequest(context, body, clientIp)
        }

        // 3. 受保护接口鉴权验证
        val authHeader = headers["authorization"] ?: ""
        val token = if (authHeader.startsWith("Bearer ")) authHeader.substring(7).trim() else ""
        if (!isTokenValid(context, token)) {
            val err = JSONObject().apply { put("error", "Unauthorized. 请先在手机屏幕完成配对确认。") }
            return makeHttpResponse(401, "Unauthorized", err.toString())
        }

        if ((method == "POST" || method == "GET") && path == "/api/sync/pull") {
            val data = packAllData(context)
            return makeHttpResponse(200, "OK", data.toString())
        }

        if (method == "POST" && path == "/api/sync/push") {
            val payload = try { JSONObject(body) } catch (_: Exception) { JSONObject() }
            val mode = payload.optString("mode", "merge")
            val report = applyReceivedData(context, payload, mode)
            withContext(Dispatchers.Main) {
                onDataSyncedListener?.invoke(report)
            }
            val res = JSONObject().apply {
                put("status", "ok")
                put("result", JSONObject().apply {
                    put("schedule", report.courseCount)
                    put("exams", report.examCount)
                    put("notes", report.noteCount)
                })
            }
            return makeHttpResponse(200, "OK", res.toString())
        }

        if (method == "POST" && path == "/api/clipboard") {
            val payload = try { JSONObject(body) } catch (_: Exception) { JSONObject() }
            val text = payload.optString("text", "")
            val title = payload.optString("title", "来自博士的电脑")
            if (text.isNotEmpty()) {
                withContext(Dispatchers.Main) {
                    handleIncomingClipboard(context, text, title)
                }
            }
            return makeHttpResponse(200, "OK", JSONObject().apply { put("status", "ok") }.toString())
        }

        if (method == "POST" && path == "/api/status") {
            return makeHttpResponse(200, "OK", JSONObject().apply { put("status", "ok") }.toString())
        }

        return makeHttpResponse(404, "Not Found", "{\"error\":\"Not Found\"}")
    }

    private suspend fun handlePairRequest(context: Context, body: String, clientIp: String): String {
        val payload = try { JSONObject(body) } catch (_: Exception) { JSONObject() }
        val clientId = payload.optString("client_id", "")
        val clientName = payload.optString("client_name", "未知设备")
        val clientPort = payload.optInt("client_port", 23333)
        val payloadIp = payload.optString("client_ip", "")
        val effectiveIp = if (payloadIp.isNotEmpty() && (clientIp == "127.0.0.1" || clientIp == "::1" || clientIp == "localhost")) payloadIp else clientIp
        val pin = payload.optString("pin", "")

        if (clientId.isEmpty()) {
            return makeHttpResponse(400, "Bad Request", "{\"error\":\"Missing client_id\"}")
        }

        val reqId = UUID.randomUUID().toString().substring(0, 8)
        val pairReq = PairRequest(reqId, clientId, clientName, effectiveIp, clientPort, pin)
        val deferred = CompletableDeferred<Boolean>()
        pendingPairRequests[reqId] = deferred
        pendingPairModels[reqId] = pairReq

        // 触发 UI 弹窗
        withContext(Dispatchers.Main) {
            onPairRequestedListener?.invoke(pairReq)
        }

        // 等待博士在屏幕上确认，超时 30 秒
        val confirmed = try {
            withTimeout(30000L) {
                deferred.await()
            }
        } catch (e: TimeoutCancellationException) {
            false
        } finally {
            pendingPairRequests.remove(reqId)
            pendingPairModels.remove(reqId)
        }

        if (confirmed) {
            val token = "rhodes_m_" + UUID.randomUUID().toString().replace("-", "")
            saveTrustedDevice(context, clientId, clientName, effectiveIp, clientPort, token)
            val res = JSONObject().apply {
                put("status", "accepted")
                put("auth_token", token)
                put("device_name", getMyDeviceName(context))
                put("device_id", getMyDeviceId(context))
            }
            return makeHttpResponse(200, "OK", res.toString())
        } else {
            val res = JSONObject().apply {
                put("status", "rejected")
                put("error", "配对请求被拒绝或超时未确认")
            }
            return makeHttpResponse(403, "Forbidden", res.toString())
        }
    }

    /**
     * UI 确认配对
     */
    fun confirmPairRequest(requestId: String, accept: Boolean) {
        val deferred = pendingPairRequests[requestId]
        deferred?.complete(accept)
    }

    private fun handleIncomingClipboard(context: Context, text: String, title: String) {
        try {
            val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            cm.setPrimaryClip(ClipData.newPlainText("RhodesDrop", text))
        } catch (_: Exception) {}

        Toast.makeText(context, "📥 收到来自电脑的快传并已复制！", Toast.LENGTH_SHORT).show()

        // 联动悬浮桌宠弹出气泡
        onTacticalDropReceived?.invoke(text, title)
    }

    private fun makeHttpResponse(code: Int, statusText: String, bodyJson: String): String {
        val bodyBytes = bodyJson.toByteArray(Charsets.UTF_8)
        return "HTTP/1.1 $code $statusText\r\n" +
                "Content-Type: application/json; charset=utf-8\r\n" +
                "Content-Length: ${bodyBytes.size}\r\n" +
                "Access-Control-Allow-Origin: *\r\n" +
                "Connection: close\r\n\r\n" +
                bodyJson
    }

    // ── 客户端对外主动请求能力 ───────────────────────────────────────

    /**
     * 广播扫描局域网内的设备
     */
    suspend fun scanLanDevices(timeoutMs: Long = 1800L): List<DeviceInfo> = withContext(Dispatchers.IO) {
        val results = mutableListOf<DeviceInfo>()
        var sock: DatagramSocket? = null
        try {
            sock = DatagramSocket().apply {
                broadcast = true
                soTimeout = 200
            }
            val msg = JSONObject().apply {
                put("cmd", "DISCOVER")
                put("device_type", "android")
                put("http_port", localHttpPort)
            }
            val bytes = msg.toString().toByteArray(Charsets.UTF_8)
            val packet = DatagramPacket(bytes, bytes.size, InetAddress.getByName("255.255.255.255"), DEFAULT_UDP_PORT)
            sock.send(packet)

            val buf = ByteArray(2048)
            val startTime = System.currentTimeMillis()
            while (System.currentTimeMillis() - startTime < timeoutMs) {
                try {
                    val recvPacket = DatagramPacket(buf, buf.size)
                    sock.receive(recvPacket)
                    val jsonStr = String(recvPacket.data, 0, recvPacket.length, Charsets.UTF_8)
                    val json = JSONObject(jsonStr)
                    if (json.optString("cmd") == "DISCOVER_ACK") {
                        val ip = recvPacket.address.hostAddress ?: ""
                        results.add(DeviceInfo.fromJson(json, ip))
                    }
                } catch (_: SocketTimeoutException) {
                } catch (_: Exception) {}
            }
        } catch (_: Exception) {
        } finally {
            try { sock?.close() } catch (_: Exception) {}
        }
        results.distinctBy { it.deviceId.ifEmpty { it.ip } }
    }

    /**
     * 直连探测设备（应对 AP 隔离）
     */
    suspend fun probeDevice(ip: String, port: Int = 23333): DeviceInfo? = withContext(Dispatchers.IO) {
        try {
            val url = URL("http://$ip:$port/api/info")
            val conn = url.openConnection() as HttpURLConnection
            conn.connectTimeout = 3000
            conn.readTimeout = 3000
            conn.requestMethod = "GET"
            if (conn.responseCode == 200) {
                val text = conn.inputStream.bufferedReader().readText()
                val json = JSONObject(text)
                return@withContext DeviceInfo.fromJson(json, ip)
            }
        } catch (_: Exception) {}
        null
    }

    fun getCandidateIps(primaryIp: String): List<String> {
        val list = mutableListOf<String>()
        val trimmed = primaryIp.trim()
        if (trimmed.isNotEmpty()) {
            list.add(trimmed)
        }
        if ("127.0.0.1" !in list) list.add("127.0.0.1")
        if ("10.0.2.2" !in list) list.add("10.0.2.2")
        return list
    }

    private fun updateDeviceIp(context: Context, oldIp: String, newIp: String) {
        val prefs = context.getSharedPreferences(PREFS_SYNC, Context.MODE_PRIVATE)
        val jsonStr = prefs.getString("paired_list", "{}") ?: "{}"
        try {
            val root = JSONObject(jsonStr)
            var changed = false
            for (k in root.keys()) {
                val dev = root.getJSONObject(k)
                if (dev.optString("ip") == oldIp) {
                    dev.put("ip", newIp)
                    changed = true
                }
            }
            if (changed) {
                prefs.edit().putString("paired_list", root.toString()).commit()
                mainScope.launch {
                    onDevicesChangedListener?.invoke()
                }
            }
        } catch (_: Exception) {}
    }

    /**
     * 主动向电脑端发起配对请求，等待电脑端屏幕核验确认
     */
    suspend fun requestPairToRemote(
        context: Context,
        ip: String,
        port: Int = 23333,
        pin: String = (100000..999999).random().toString()
    ): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val candidates = getCandidateIps(ip)
        var lastErr = ""
        for (targetIp in candidates) {
            try {
                val url = URL("http://$targetIp:$port/api/pair/request")
                val conn = (url.openConnection() as HttpURLConnection).apply {
                    connectTimeout = 3000
                    readTimeout = 35000
                    requestMethod = "POST"
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                }
                val payload = JSONObject().apply {
                    put("client_id", getMyDeviceId(context))
                    put("client_name", getMyDeviceName(context))
                    put("client_port", localHttpPort)
                    put("pin", pin)
                }
                conn.outputStream.bufferedWriter().use { it.write(payload.toString()) }

                val code = conn.responseCode
                val respText = if (code in 200..299) {
                    conn.inputStream.bufferedReader().readText()
                } else {
                    conn.errorStream?.bufferedReader()?.readText() ?: ""
                }
                val json = try { JSONObject(respText) } catch (_: Exception) { JSONObject() }
                if (code == 200 && json.optString("status") == "accepted") {
                    val token = json.optString("auth_token", "")
                    val devName = json.optString("device_name", targetIp)
                    val devId = json.optString("device_id", targetIp)
                    saveTrustedDevice(context, devId, devName, targetIp, port, token)
                    return@withContext Pair(true, "配对成功！已与「$devName」建立信任互联。")
                } else {
                    val err = json.optString("error", "电脑端拒绝或超时未确认")
                    return@withContext Pair(false, err)
                }
            } catch (e: Exception) {
                lastErr = "连接目标电脑失败: ${e.localizedMessage}"
            }
        }
        return@withContext Pair(false, lastErr)
    }

    /**
     * 从电脑端拉取学业数据并合并到本地
     */
    suspend fun syncPull(context: Context, ip: String, port: Int, token: String): SyncReport = withContext(Dispatchers.IO) {
        val candidates = getCandidateIps(ip)
        var lastErr = ""
        for (targetIp in candidates) {
            try {
                val url = URL("http://$targetIp:$port/api/sync/pull")
                val conn = (url.openConnection() as HttpURLConnection).apply {
                    connectTimeout = 3000
                    readTimeout = 8000
                    requestMethod = "POST"
                    setRequestProperty("Authorization", "Bearer $token")
                }
                if (conn.responseCode == 200) {
                    val jsonStr = conn.inputStream.bufferedReader().readText()
                    val payload = JSONObject(jsonStr)
                    val report = applyReceivedData(context, payload, "merge")
                    withContext(Dispatchers.Main) {
                        ScheduleWidgetProvider.sendUpdateBroadcast(context)
                    }
                    if (targetIp != ip) {
                        updateDeviceIp(context, ip, targetIp)
                    }
                    return@withContext report
                } else {
                    lastErr = "拉取失败 (HTTP ${conn.responseCode})"
                }
            } catch (e: Exception) {
                lastErr = "拉取异常: ${e.localizedMessage}"
            }
        }
        return@withContext SyncReport(false, lastErr)
    }

    /**
     * 推送手机数据到电脑端
     */
    suspend fun syncPush(context: Context, ip: String, port: Int, token: String, mode: String = "replace"): SyncReport = withContext(Dispatchers.IO) {
        val candidates = getCandidateIps(ip)
        var lastErr = ""
        for (targetIp in candidates) {
            try {
                val url = URL("http://$targetIp:$port/api/sync/push")
                val conn = (url.openConnection() as HttpURLConnection).apply {
                    connectTimeout = 3000
                    readTimeout = 8000
                    requestMethod = "POST"
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    setRequestProperty("Authorization", "Bearer $token")
                }
                val payload = packAllData(context).apply {
                    put("mode", mode)
                }
                conn.outputStream.bufferedWriter().use { it.write(payload.toString()) }

                if (conn.responseCode == 200) {
                    if (targetIp != ip) {
                        updateDeviceIp(context, ip, targetIp)
                    }
                    return@withContext SyncReport(true, "推送学业数据到电脑成功！")
                } else {
                    lastErr = "推送失败 (HTTP ${conn.responseCode})"
                }
            } catch (e: Exception) {
                lastErr = "推送异常: ${e.localizedMessage}"
            }
        }
        return@withContext SyncReport(false, lastErr)
    }

    /**
     * 发送当前剪贴板/文本至电脑
     */
    suspend fun sendClipboard(context: Context, ip: String, port: Int, token: String, text: String): Boolean = withContext(Dispatchers.IO) {
        val candidates = getCandidateIps(ip)
        for (targetIp in candidates) {
            try {
                val url = URL("http://$targetIp:$port/api/clipboard")
                val conn = (url.openConnection() as HttpURLConnection).apply {
                    connectTimeout = 3000
                    readTimeout = 5000
                    requestMethod = "POST"
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    setRequestProperty("Authorization", "Bearer $token")
                }
                val payload = JSONObject().apply {
                    put("text", text)
                    put("title", getMyDeviceName(context))
                    put("timestamp", System.currentTimeMillis())
                }
                conn.outputStream.bufferedWriter().use { it.write(payload.toString()) }
                if (conn.responseCode == 200) {
                    if (targetIp != ip) {
                        updateDeviceIp(context, ip, targetIp)
                    }
                    return@withContext true
                }
            } catch (e: Exception) {
                android.util.Log.e("SyncManager", "sendClipboard try $targetIp error: ${e.localizedMessage}")
            }
        }
        return@withContext false
    }

    // ── 数据打包与应用引擎 ───────────────────────────────────────────

    fun packAllData(context: Context): JSONObject {
        // 1. 课表
        ScheduleManager.load(context)
        val coursesArr = JSONArray()
        for (c in ScheduleManager.courses) {
            coursesArr.put(JSONObject().apply {
                put("name", c.name)
                put("weekday", c.weekday)
                put("sec_start", c.secStart)
                put("sec_end", c.secEnd)
                put("week_start", c.weekStart)
                put("week_end", c.weekEnd)
                put("parity", c.parity)
                put("room", c.room)
                put("teacher", c.teacher)
                put("campus", c.campus)
                put("note", c.note)
                put("id", c.id)
            })
        }
        val termStartStr = ScheduleManager.termStart?.let {
            SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(it)
        } ?: ""

        val schedObj = JSONObject().apply {
            put("term_start", termStartStr)
            val secObj = JSONObject()
            ScheduleManager.sections.forEach { (k, v) -> secObj.put(k, v) }
            put("sections", secObj)
            put("courses", coursesArr)
        }

        // 2. 考试
        ExamManager.load(context)
        val examsArr = JSONArray()
        for (e in ExamManager.exams) {
            examsArr.put(e.toJson())
        }

        // 3. 便签
        val notesMgr = NotesManager.getInstance(context)
        val notesArr = JSONArray()
        for (n in notesMgr.notes) {
            notesArr.put(n.toJsonObject())
        }

        return JSONObject().apply {
            put("schedule", schedObj)
            put("exams", examsArr)
            put("notes", notesArr)
            put("timestamp", System.currentTimeMillis())
        }
    }

    fun applyReceivedData(context: Context, payload: JSONObject, mode: String = "merge"): SyncReport {
        var courseCount = 0
        var examCount = 0
        var noteCount = 0

        // 1. 课表处理
        val schedObj = payload.optJSONObject("schedule")
        if (schedObj != null) {
            ScheduleManager.load(context)
            val coursesArray = schedObj.optJSONArray("courses") ?: JSONArray()
            val newCourses = mutableListOf<Course>()
            for (i in 0 until coursesArray.length()) {
                val c = coursesArray.getJSONObject(i)
                newCourses.add(Course(
                    name = c.optString("name", ""),
                    weekday = c.optInt("weekday", 1),
                    secStart = c.optInt("sec_start", 1),
                    secEnd = c.optInt("sec_end", 1),
                    weekStart = c.optInt("week_start", 1),
                    weekEnd = c.optInt("week_end", 1),
                    parity = c.optString("parity", "all"),
                    room = c.optString("room", ""),
                    teacher = c.optString("teacher", ""),
                    campus = c.optString("campus", ""),
                    note = c.optString("note", ""),
                    id = c.optString("id", UUID.randomUUID().toString())
                ))
            }

            if (mode == "replace" || ScheduleManager.courses.isEmpty()) {
                ScheduleManager.courses = newCourses
            } else {
                val existingKeys = ScheduleManager.courses.map { Triple(it.name, it.weekday, it.secStart) }.toSet()
                val merged = ScheduleManager.courses.toMutableList()
                for (c in newCourses) {
                    if (Triple(c.name, c.weekday, c.secStart) !in existingKeys) {
                        merged.add(c)
                    }
                }
                ScheduleManager.courses = merged
            }

            val termStartStr = schedObj.optString("term_start", "")
            if (termStartStr.isNotEmpty()) {
                try {
                    ScheduleManager.termStart = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).parse(termStartStr)
                } catch (_: Exception) {}
            }
            ScheduleManager.save(context)
            courseCount = ScheduleManager.courses.size
        }

        // 2. 考试日程处理
        val examsArr = payload.optJSONArray("exams")
        if (examsArr != null) {
            ExamManager.load(context)
            val existingTitles = ExamManager.exams.map { it.title }.toSet()
            var addedExams = 0
            for (i in 0 until examsArr.length()) {
                val item = examsArr.getJSONObject(i)
                val exam = ExamItem.fromJson(item)
                if (mode == "merge" && exam.title in existingTitles) continue
                ExamManager.exams.add(exam)
                addedExams++
            }
            ExamManager.save(context)
            examCount = addedExams
        }

        // 3. 便签处理
        val notesArr = payload.optJSONArray("notes")
        if (notesArr != null) {
            val notesMgr = NotesManager.getInstance(context)
            var addedNotes = 0
            for (i in 0 until notesArr.length()) {
                val item = notesArr.getJSONObject(i)
                val remoteNote = Note.fromJsonObject(item)
                val localNote = notesMgr.notes.find { it.id == remoteNote.id }
                if (localNote != null) {
                    if (remoteNote.updatedAt > localNote.updatedAt) {
                        localNote.title = remoteNote.title
                        localNote.content = remoteNote.content
                        localNote.updatedAt = remoteNote.updatedAt
                        localNote.pinned = remoteNote.pinned
                        addedNotes++
                    }
                } else {
                    notesMgr.addNote(remoteNote)
                    addedNotes++
                }
            }
            notesMgr.saveNotes()
            noteCount = addedNotes
        }

        return SyncReport(
            success = true,
            message = "同步成功！更新课表 $courseCount 门，考试日程 $examCount 场，便签 $noteCount 篇。",
            courseCount = courseCount,
            examCount = examCount,
            noteCount = noteCount
        )
    }

    // ── 受信任设备管理 ───────────────────────────────────────────────

    fun getTrustedDevices(context: Context): Map<String, DeviceInfo> {
        val prefs = context.getSharedPreferences(PREFS_SYNC, Context.MODE_PRIVATE)
        val jsonStr = prefs.getString("paired_list", "{}") ?: "{}"
        val res = mutableMapOf<String, DeviceInfo>()
        try {
            val root = JSONObject(jsonStr)
            for (k in root.keys()) {
                val devObj = root.getJSONObject(k)
                res[k] = DeviceInfo(
                    deviceId = k,
                    deviceName = devObj.optString("name", "电脑终端"),
                    deviceType = "pc",
                    ip = devObj.optString("ip", ""),
                    httpPort = devObj.optInt("port", 23333),
                    paired = true
                )
            }
        } catch (_: Exception) {}
        return res
    }

    fun getDeviceToken(context: Context, deviceId: String): String {
        val prefs = context.getSharedPreferences(PREFS_SYNC, Context.MODE_PRIVATE)
        val jsonStr = prefs.getString("paired_list", "{}") ?: "{}"
        try {
            val root = JSONObject(jsonStr)
            return root.optJSONObject(deviceId)?.optString("token", "") ?: ""
        } catch (_: Exception) {}
        return ""
    }

    fun saveTrustedDevice(context: Context, id: String, name: String, ip: String, port: Int, token: String) {
        val prefs = context.getSharedPreferences(PREFS_SYNC, Context.MODE_PRIVATE)
        val jsonStr = prefs.getString("paired_list", "{}") ?: "{}"
        val root = try { JSONObject(jsonStr) } catch (_: Exception) { JSONObject() }
        root.put(id, JSONObject().apply {
            put("name", name)
            put("ip", ip)
            put("port", port)
            put("token", token)
            put("paired_at", SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()).format(Date()))
        })
        prefs.edit().putString("paired_list", root.toString()).commit()
        mainScope.launch {
            onDevicesChangedListener?.invoke()
        }
    }

    fun unpairDevice(context: Context, id: String) {
        val prefs = context.getSharedPreferences(PREFS_SYNC, Context.MODE_PRIVATE)
        val jsonStr = prefs.getString("paired_list", "{}") ?: "{}"
        try {
            val root = JSONObject(jsonStr)
            root.remove(id)
            prefs.edit().putString("paired_list", root.toString()).commit()
            mainScope.launch {
                onDevicesChangedListener?.invoke()
            }
        } catch (_: Exception) {}
    }

    private fun isTokenValid(context: Context, token: String): Boolean {
        if (token.isEmpty()) return false
        val prefs = context.getSharedPreferences(PREFS_SYNC, Context.MODE_PRIVATE)
        val jsonStr = prefs.getString("paired_list", "{}") ?: "{}"
        try {
            val root = JSONObject(jsonStr)
            for (k in root.keys()) {
                if (root.getJSONObject(k).optString("token") == token) return true
            }
        } catch (_: Exception) {}
        return false
    }

    fun getMyDeviceId(context: Context): String {
        val prefs = context.getSharedPreferences(PREFS_SYNC, Context.MODE_PRIVATE)
        var id = prefs.getString("my_device_id", "") ?: ""
        if (id.isEmpty()) {
            id = "android_" + UUID.randomUUID().toString().substring(0, 8)
            prefs.edit().putString("my_device_id", id).apply()
        }
        return id
    }

    fun getMyDeviceName(context: Context): String {
        return "博士的 Android 终端"
    }

    fun getLocalIpAddress(): String {
        try {
            val en = NetworkInterface.getNetworkInterfaces()
            while (en.hasMoreElements()) {
                val intf = en.nextElement()
                val enumIpAddr = intf.inetAddresses
                while (enumIpAddr.hasMoreElements()) {
                    val inetAddress = enumIpAddr.nextElement()
                    if (!inetAddress.isLoopbackAddress && inetAddress is Inet4Address) {
                        val host = inetAddress.hostAddress ?: ""
                        if (!host.startsWith("127.") && !host.startsWith("169.254.")) {
                            return host
                        }
                    }
                }
            }
        } catch (_: Exception) {}
        return "127.0.0.1"
    }
}
