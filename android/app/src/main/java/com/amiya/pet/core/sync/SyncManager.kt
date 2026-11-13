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
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.security.MessageDigest
import kotlinx.coroutines.sync.Semaphore
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
    private val connectionSlots = Semaphore(16)
    private var secure = SyncCrypto.Server()
    fun createPairingInvite(): String = secure.createInvite()
    fun pairingCode(secret: String): String = runCatching { SyncCrypto.pairingCode(secret) }.getOrDefault("无效密钥")

    // 待确认配对请求映射 requestId -> CompletableDeferred<Boolean>
    private val pendingPairRequests = ConcurrentHashMap<String, CompletableDeferred<Boolean>>()
    private val pendingPairModels = ConcurrentHashMap<String, PairRequest>()
    private val pairAttempts = mutableMapOf<String, List<Long>>()

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
        secure = SyncCrypto.Server()

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
                    if (!connectionSlots.tryAcquire()) {
                        client.close()
                        continue
                    }
                    ioScope.launch {
                        try { handleClientConnection(context.applicationContext, client) }
                        finally { connectionSlots.release() }
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
        pendingPairRequests.values.forEach { it.complete(false) }
        pendingPairRequests.clear()
        pendingPairModels.clear()
    }

    // ── HTTP 请求分发处理 ─────────────────────────────────────────────

    private suspend fun handleClientConnection(context: Context, client: Socket) = withContext(Dispatchers.IO) {
        val watchdog = ioScope.launch { delay(45000); try { client.close() } catch (_: Exception) {} }
        var claim: Pair<String, String>? = null
        try {
            client.soTimeout = 5000
            val request = SyncHttpProtocol.read(client.getInputStream()) { it["x-rhodes-protocol"] == "2" }
            val path = request.uri.substringBefore('?')
            var response: String
            if (request.method == "GET" && path == "/api/info") {
                response = routeRequest(context, request.method, request.uri, request.headers, "", client.inetAddress.hostAddress ?: "")
            } else {
                val envelope = envelope(JSONObject(request.body))
                val record = trustedRecords(context).firstOrNull { it.optInt("protocol") == 2 &&
                    it.optString("sync_key").isNotEmpty() && SyncCrypto.keyId(it.getString("sync_key")) == envelope.kid }
                val secret = if (path == "/api/pair/request") secure.inviteSecret(envelope.kid) else record?.optString("sync_key")
                require(!secret.isNullOrEmpty())
                val plain = secure.accept(secret, path, envelope)
                if (path == "/api/pair/request") { require(secure.claimInvite(secret, envelope.id)); claim = secret to envelope.id }
                val limit = when(path) { "/api/pair/request" -> SyncHttpProtocol.MAX_PAIR; "/api/clipboard" -> SyncHttpProtocol.MAX_CLIPBOARD; else -> SyncCrypto.MAX_PLAIN }
                require(plain.size <= limit)
                val payload = JSONObject(String(plain, Charsets.UTF_8))
                if (path != "/api/pair/request") {
                    val token = payload.optString("_auth_token")
                    require(token.isNotEmpty() && record != null && MessageDigest.isEqual(token.toByteArray(), record.optString("token").toByteArray()))
                }
                val headers = request.headers + ("authorization" to "Bearer ${payload.optString("_auth_token")}")
                val result = routeRequest(context, request.method, path, headers, payload.toString(), client.inetAddress.hostAddress ?: "", secret)
                val status = result.substringAfter(' ').substringBefore(' ').toInt()
                val cipher = SyncCrypto.seal(secret, path, result.substringAfter("\r\n\r\n").toByteArray(Charsets.UTF_8), envelope, "response", status)
                response = makeHttpResponse(status, "Sync", wire(cipher).toString())
            }
            val writer = OutputStreamWriter(client.getOutputStream(), Charsets.UTF_8)
            writer.write(response)
            writer.flush()
        } catch (e: SyncHttpProtocol.Rejected) {
            try {
                val body = JSONObject().put("error", e.message ?: "Invalid request").toString()
                client.getOutputStream().write(makeHttpResponse(e.code, "Request Rejected", body).toByteArray(Charsets.UTF_8))
                client.getOutputStream().flush()
            } catch (_: Exception) {}
        } catch (_: SocketTimeoutException) {
            try { client.getOutputStream().write(makeHttpResponse(408, "Request Timeout", "{}").toByteArray(Charsets.UTF_8)) } catch (_: Exception) {}
        } catch (_: Exception) {
            try { client.getOutputStream().write(makeHttpResponse(401, "Unauthorized", "{\"error\":\"Encrypted authentication failed\"}").toByteArray(Charsets.UTF_8)) } catch (_: Exception) {}
        } finally {
            claim?.let { secure.releaseInvite(it.first, it.second) }
            watchdog.cancel()
            try { client.close() } catch (_: Exception) {}
        }
    }

    private suspend fun routeRequest(
        context: Context,
        method: String,
        uri: String,
        headers: Map<String, String>,
        body: String,
        clientIp: String,
        secret: String? = null
    ): String {
        val path = if (uri.contains("?")) uri.substring(0, uri.indexOf("?")) else uri

        if (method == "POST" && body.isNotEmpty()) {
            try { JSONObject(body) }
            catch (_: Exception) { return makeHttpResponse(400, "Bad Request", "{\"error\":\"Invalid JSON object\"}") }
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
                put("protocol", 2)
                put("epoch", secure.epoch)
            }
            return makeHttpResponse(200, "OK", res.toString())
        }

        // 2. 蓝牙式配对握手请求：必须屏幕确认
        if (method == "POST" && path == "/api/pair/request") {
            return handlePairRequest(context, body, clientIp, requireNotNull(secret))
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
        if (method == "POST" && path == "/api/pair/unpair") {
            val id = JSONObject(body).optString("device_id")
            val root = JSONObject(context.getSharedPreferences(PREFS_SYNC, Context.MODE_PRIVATE).getString("paired_list", "{}") ?: "{}")
            val peer = root.optJSONObject(id)
            if (peer == null || !MessageDigest.isEqual(token.toByteArray(), peer.optString("token").toByteArray())) {
                return makeHttpResponse(403, "Forbidden", "{\"error\":\"Can only unpair your own device\"}")
            }
            unpairDevice(context, id)
            return makeHttpResponse(200, "OK", "{\"status\":\"unpaired\"}")
        }

        return makeHttpResponse(404, "Not Found", "{\"error\":\"Not Found\"}")
    }

    private suspend fun handlePairRequest(context: Context, body: String, clientIp: String, secret: String): String {
        val payload = try { JSONObject(body) } catch (_: Exception) { JSONObject() }
        val clientId = payload.optString("client_id", "")
        val clientName = payload.optString("client_name", "未知设备")
        val clientPort = payload.optInt("client_port", 23333)
        val effectiveIp = clientIp
        val pin = SyncCrypto.pairingCode(secret)

        if (clientId.isEmpty() || clientId.length > 128 || clientName.isEmpty() || clientName.length > 128 ||
            clientPort !in 1..65535 || !pin.matches(Regex("[0-9]{6}"))) {
            return makeHttpResponse(400, "Bad Request", "{\"error\":\"Missing client_id\"}")
        }

        val reqId = UUID.randomUUID().toString()
        val pairReq = PairRequest(reqId, clientId, clientName, effectiveIp, clientPort, pin)
        val deferred = CompletableDeferred<Boolean>()
        synchronized(pendingPairRequests) {
            if (pendingPairRequests.size >= 8 || pendingPairModels.values.any { it.clientIp == effectiveIp }) {
                return makeHttpResponse(429, "Too Many Requests", "{\"error\":\"Pairing already pending\"}")
            }
            val now = android.os.SystemClock.elapsedRealtime()
            for (ip in pairAttempts.keys.toList()) {
                val recent = pairAttempts.getValue(ip).filter { now - it < 60000L }
                if (recent.isEmpty()) pairAttempts.remove(ip) else pairAttempts[ip] = recent
            }
            val attempts = pairAttempts[effectiveIp] ?: emptyList()
            if (attempts.size >= 5 || (effectiveIp !in pairAttempts && pairAttempts.size >= 128)) {
                return makeHttpResponse(429, "Too Many Requests", "{\"error\":\"Pairing too frequent\"}")
            }
            pairAttempts[effectiveIp] = attempts + now
            pendingPairRequests[reqId] = deferred
            pendingPairModels[reqId] = pairReq
        }

        // 等待博士在屏幕上确认，超时 30 秒
        val confirmed = try {
            withTimeout(30000L) {
                withContext(Dispatchers.Main) { onPairRequestedListener?.invoke(pairReq) }
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
            saveTrustedDevice(context, clientId, clientName, effectiveIp, clientPort, token, secret)
            secure.consumeInvite(secret)
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

    private fun readLimitedResponse(input: InputStream): String {
        val output = ByteArrayOutputStream()
        val buffer = ByteArray(8192)
        while (true) {
            val count = input.read(buffer)
            if (count < 0) break
            if (output.size() + count > SyncCrypto.MAX_WIRE) throw IllegalArgumentException("Sync response too large")
            output.write(buffer, 0, count)
        }
        return output.toString("UTF-8")
    }

    private fun makeHttpResponse(code: Int, statusText: String, bodyJson: String): String {
        val bodyBytes = bodyJson.toByteArray(Charsets.UTF_8)
        return "HTTP/1.1 $code $statusText\r\n" +
                "Content-Type: application/json; charset=utf-8\r\n" +
                "Content-Length: ${bodyBytes.size}\r\n" +
                "Cache-Control: no-store\r\n" +
                "X-Content-Type-Options: nosniff\r\n" +
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
            val conn = url.openConnection(Proxy.NO_PROXY) as HttpURLConnection
            conn.instanceFollowRedirects = false
            conn.connectTimeout = 3000
            conn.readTimeout = 3000
            conn.requestMethod = "GET"
            if (conn.responseCode == 200) {
                val text = conn.inputStream.use { readLimitedResponse(it) }
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
    private fun wire(e: SyncCrypto.Envelope): JSONObject = JSONObject().apply {
        put("v", e.v); put("kid", e.kid); put("epoch", e.epoch); put("id", e.id)
        put("ts", e.ts); put("s", e.s); put("nonce", e.nonce); put("ct", e.ct)
    }
    private fun envelope(j: JSONObject) = SyncCrypto.Envelope(j.getInt("v"), j.getString("kid"), j.getString("epoch"),
        j.getString("id"), j.getLong("ts"), j.getInt("s"), j.getString("nonce"), j.getString("ct"))
    private fun trustedRecords(context: Context): List<JSONObject> {
        val root = JSONObject(context.getSharedPreferences(PREFS_SYNC, Context.MODE_PRIVATE).getString("paired_list", "{}") ?: "{}")
        return root.keys().asSequence().mapNotNull { root.optJSONObject(it) }.toList()
    }
    private fun keyForToken(context: Context, token: String): String = trustedRecords(context).firstOrNull {
        token.isNotEmpty() && it.optInt("protocol") == 2 && MessageDigest.isEqual(token.toByteArray(), it.optString("token").toByteArray())
    }?.getString("sync_key") ?: throw IllegalArgumentException("请升级并重新配对")
    private fun exchange(ip: String, port: Int, path: String, payload: JSONObject, secret: String, token: String? = null): Pair<Int, JSONObject> {
        val probe = URL("http://$ip:$port/api/info").openConnection(Proxy.NO_PROXY) as HttpURLConnection
        val info = try {
            probe.instanceFollowRedirects = false; probe.connectTimeout = 3000; probe.readTimeout = 3000
            require(probe.responseCode == 200)
            JSONObject(probe.inputStream.use { readLimitedResponse(it) })
        } finally { probe.disconnect() }
        require(info.optInt("protocol") == 2) { "目标设备需要升级加密协议" }
        if (token != null) payload.put("_auth_token", token)
        val request = SyncCrypto.request(secret, path, payload.toString().toByteArray(Charsets.UTF_8), info.getString("epoch"))
        val conn = URL("http://$ip:$port$path").openConnection(Proxy.NO_PROXY) as HttpURLConnection
        return try {
            conn.instanceFollowRedirects = false; conn.connectTimeout = 3000
            conn.readTimeout = if (path == "/api/pair/request") 35000 else 10000
            conn.requestMethod = "POST"; conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setRequestProperty("X-Rhodes-Protocol", "2")
            conn.outputStream.use { it.write(wire(request).toString().toByteArray(Charsets.UTF_8)) }
            val status = conn.responseCode
            val body = (if (status in 200..299) conn.inputStream else conn.errorStream).use { readLimitedResponse(it) }
            val plain = SyncCrypto.response(secret, path, envelope(JSONObject(body)), request, status)
            status to JSONObject(String(plain, Charsets.UTF_8))
        } finally { conn.disconnect() }
    }
    suspend fun requestPairToRemote(context: Context, ip: String, port: Int = 23333, pairingSecret: String = ""): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        try {
            SyncCrypto.keyId(pairingSecret)
            val payload = JSONObject().apply {
                put("client_id", getMyDeviceId(context)); put("client_name", getMyDeviceName(context)); put("client_port", localHttpPort)
                put("pin", SyncCrypto.pairingCode(pairingSecret))
            }
            val (status, result) = exchange(ip, port, "/api/pair/request", payload, pairingSecret)
            if (status != 200 || result.optString("status") != "accepted") return@withContext false to result.optString("error", "配对被拒绝")
            val token = result.getString("auth_token"); val id = result.getString("device_id")
            require(token.isNotEmpty() && id.isNotEmpty())
            saveTrustedDevice(context, id, result.optString("device_name", ip), ip, port, token, pairingSecret)
            true to "加密配对成功"
        } catch (_: Exception) { false to "加密配对失败：请确认配对密钥正确、未过期，并在目标设备确认。" }
    }
    suspend fun syncPull(context: Context, ip: String, port: Int, token: String): SyncReport = withContext(Dispatchers.IO) {
        try {
            val (status, payload) = exchange(ip, port, "/api/sync/pull", JSONObject(), keyForToken(context, token), token)
            require(status == 200)
            val report = applyReceivedData(context, payload, "merge")
            withContext(Dispatchers.Main) { ScheduleWidgetProvider.sendUpdateBroadcast(context) }
            report
        } catch (_: Exception) { SyncReport(false, "加密拉取失败，请升级并重新配对") }
    }
    suspend fun syncPush(context: Context, ip: String, port: Int, token: String, mode: String = "replace"): SyncReport = withContext(Dispatchers.IO) {
        try {
            val (status, _) = exchange(ip, port, "/api/sync/push", packAllData(context).put("mode", mode), keyForToken(context, token), token)
            SyncReport(status == 200, if (status == 200) "加密推送成功" else "推送被拒绝")
        } catch (_: Exception) { SyncReport(false, "加密推送失败，请升级并重新配对") }
    }
    suspend fun sendClipboard(context: Context, ip: String, port: Int, token: String, text: String): Boolean = withContext(Dispatchers.IO) {
        try {
            exchange(ip, port, "/api/clipboard", JSONObject().put("text", text).put("title", getMyDeviceName(context)), keyForToken(context, token), token).first == 200
        } catch (_: Exception) { false }
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

    fun saveTrustedDevice(context: Context, id: String, name: String, ip: String, port: Int, token: String, secret: String) {
        val prefs = context.getSharedPreferences(PREFS_SYNC, Context.MODE_PRIVATE)
        val jsonStr = prefs.getString("paired_list", "{}") ?: "{}"
        val root = try { JSONObject(jsonStr) } catch (_: Exception) { JSONObject() }
        root.put(id, JSONObject().apply {
            put("name", name)
            put("ip", ip)
            put("port", port)
            put("token", token)
            put("sync_key", secret)
            put("protocol", 2)
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
                if (MessageDigest.isEqual(root.getJSONObject(k).optString("token").toByteArray(Charsets.UTF_8), token.toByteArray(Charsets.UTF_8))) return true
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
