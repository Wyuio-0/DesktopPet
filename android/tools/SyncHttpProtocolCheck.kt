package com.amiya.pet.core.sync

import java.io.ByteArrayInputStream

/** Run on a JVM without Android: tools/check_sync_protocol.py. */
fun main() {
    var checks = 0
    fun reject(code: Int, raw: ByteArray, authorized: Boolean = true) {
        try {
            SyncHttpProtocol.read(ByteArrayInputStream(raw)) { authorized }
            error("Expected rejection $code")
        } catch (e: SyncHttpProtocol.Rejected) {
            check(e.code == code) { "Expected $code, got ${e.code}" }
            checks++
        }
    }
    fun request(headers: String, body: ByteArray = byteArrayOf(), path: String = "/api/clipboard") =
        ("POST $path HTTP/1.1\r\nHost: localhost\r\n$headers\r\n").toByteArray() + body

    val chinese = "{\"text\":\"你好，博士\"}".toByteArray(Charsets.UTF_8)
    val parsed = SyncHttpProtocol.read(ByteArrayInputStream(request(
        "Content-Length: ${chinese.size}\r\nContent-Type: application/json\r\n", chinese))) { true }
    check(parsed.body == String(chinese, Charsets.UTF_8)); checks++
    val legacy = "POST /api/sync/pull HTTP/1.1\r\nHost: localhost\r\n\r\n".toByteArray()
    check(SyncHttpProtocol.read(ByteArrayInputStream(legacy)) { true }.body.isEmpty()); checks++
    reject(400, request("Content-Length: -1\r\n"))
    reject(400, request("Content-Length: 0\r\nContent-Length: 0\r\n"))
    reject(400, request("Transfer-Encoding: chunked\r\n"))
    reject(413, request("Content-Length: ${SyncHttpProtocol.MAX_PAIR + 1}\r\n", path = "/api/pair/request"))
    reject(413, request("Content-Length: ${SyncHttpProtocol.MAX_BODY + 1}\r\n"))
    reject(403, request("Origin: https://evil.example\r\nContent-Length: 0\r\n"))
    reject(403, request("Sec-Fetch-Site: same-site\r\nContent-Length: 0\r\n"))
    reject(415, request("Content-Length: 2\r\nContent-Type: text/plain\r\n", "{}".toByteArray()))
    reject(400, request("Content-Length: 5\r\nContent-Type: application/json\r\n", "{}".toByteArray()))
    reject(400, request("Content-Length: 1\r\nContent-Type: application/json\r\n", byteArrayOf(0xff.toByte())))
    reject(431, request("X-Flood: ${"a".repeat(17000)}\r\nContent-Length: 0\r\n"))
    val unread = ByteArrayInputStream(request("Content-Length: ${chinese.size}\r\nContent-Type: application/json\r\n", chinese))
    try { SyncHttpProtocol.read(unread) { false }; error("Expected unauthorized") }
    catch (e: SyncHttpProtocol.Rejected) { check(e.code == 401); check(unread.available() == chinese.size); checks++ }
    println("Sync protocol checks passed: $checks")
}
