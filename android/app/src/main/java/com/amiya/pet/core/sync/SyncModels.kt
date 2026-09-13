package com.amiya.pet.core.sync

import org.json.JSONObject

/**
 * 局域网互联设备信息
 */
data class DeviceInfo(
    val deviceId: String,
    val deviceName: String,
    val deviceType: String, // "pc" or "android"
    val ip: String,
    val httpPort: Int = 23334,
    val version: String = "1.9.0",
    val paired: Boolean = false
) {
    fun toJson(): JSONObject {
        return JSONObject().apply {
            put("device_id", deviceId)
            put("device_name", deviceName)
            put("device_type", deviceType)
            put("ip", ip)
            put("http_port", httpPort)
            put("version", version)
            put("paired", paired)
        }
    }

    companion object {
        fun fromJson(json: JSONObject, fallbackIp: String = ""): DeviceInfo {
            return DeviceInfo(
                deviceId = json.optString("device_id", ""),
                deviceName = json.optString("device_name", "未知设备"),
                deviceType = json.optString("device_type", "pc"),
                ip = json.optString("ip", fallbackIp),
                httpPort = json.optInt("http_port", 23333),
                version = json.optString("version", "1.0.0"),
                paired = json.optBoolean("paired", false)
            )
        }
    }
}

/**
 * 等待用户显式确认的配对请求
 */
data class PairRequest(
    val requestId: String,
    val clientId: String,
    val clientName: String,
    val clientIp: String,
    val clientPort: Int,
    val pin: String
)

/**
 * 战术快传投递内容
 */
data class TacticalDrop(
    val text: String,
    val title: String = "来自博士的终端",
    val timestamp: Long = System.currentTimeMillis()
)

/**
 * 学业数据同步结果汇报
 */
data class SyncReport(
    val success: Boolean,
    val message: String,
    val courseCount: Int = 0,
    val examCount: Int = 0,
    val noteCount: Int = 0
)
