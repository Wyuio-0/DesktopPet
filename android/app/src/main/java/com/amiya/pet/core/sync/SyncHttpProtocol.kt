package com.amiya.pet.core.sync

import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction

/** Byte-based HTTP framing, independent of Android so boundary cases can be tested on the JVM. */
internal object SyncHttpProtocol {
    const val MAX_BODY = 4 * 1024 * 1024
    const val MAX_PAIR = 4096
    const val MAX_CLIPBOARD = 256 * 1024
    private const val MAX_HEADERS = 16384

    class Rejected(val code: Int, message: String) : Exception(message)
    data class Request(val method: String, val uri: String, val headers: Map<String, String>, val body: String)

    fun read(input: InputStream, authorized: (Map<String, String>) -> Boolean): Request {
        val buffer = ByteArrayOutputStream()
        var tail = 0
        while (true) {
            val value = input.read()
            if (value == -1) throw Rejected(400, "Incomplete headers")
            buffer.write(value)
            tail = (tail shl 8) or value
            if (buffer.size() > MAX_HEADERS) throw Rejected(431, "Headers too large")
            if (tail == 0x0d0a0d0a) break
        }
        val headerBytes = buffer.toByteArray()
        if (headerBytes.any { (it.toInt() and 0xff) > 127 }) throw Rejected(400, "Invalid headers")
        val lines = String(headerBytes, Charsets.US_ASCII).removeSuffix("\r\n\r\n").split("\r\n")
        val first = lines.first().split(" ")
        if (first.size != 3 || !first[1].startsWith("/") || first[2] !in listOf("HTTP/1.0", "HTTP/1.1")) {
            throw Rejected(400, "Invalid request line")
        }
        val method = first[0]
        val uri = first[1]
        val path = uri.substringBefore('?')
        val headers = mutableMapOf<String, String>()
        for (line in lines.drop(1)) {
            val colon = line.indexOf(':')
            if (colon < 1) throw Rejected(400, "Invalid header")
            val key = line.substring(0, colon).lowercase()
            if (!key.matches(Regex("[a-z0-9-]+")) || headers.containsKey(key)) throw Rejected(400, "Duplicate or invalid header")
            headers[key] = line.substring(colon + 1).trim()
        }
        if (method == "OPTIONS" || "origin" in headers || "sec-fetch-site" in headers) throw Rejected(403, "Browser access is not supported")
        if (method !in listOf("GET", "POST")) throw Rejected(405, "Method not allowed")
        if ("transfer-encoding" in headers) throw Rejected(400, "Chunked requests are not supported")
        val rawLength = headers["content-length"] ?: if (method == "GET" || path == "/api/sync/pull") "0" else throw Rejected(400, "Missing Content-Length")
        if (!rawLength.matches(Regex("[0-9]+"))) throw Rejected(400, "Invalid Content-Length")
        val length = rawLength.toLongOrNull() ?: throw Rejected(413, "Body too large")
        val limit = when (path) {
            "/api/pair/request" -> MAX_PAIR
            "/api/clipboard" -> MAX_CLIPBOARD
            else -> MAX_BODY
        }
        if (length > limit) throw Rejected(413, "Body too large")
        val public = method == "GET" && path == "/api/info" || method == "POST" && path == "/api/pair/request"
        if (!public && !authorized(headers)) throw Rejected(401, "Unauthorized")
        if (length > 0 && headers["content-type"]?.substringBefore(';')?.trim()?.lowercase() != "application/json") throw Rejected(415, "JSON required")
        val body = ByteArray(length.toInt())
        var read = 0
        while (read < body.size) {
            val count = input.read(body, read, body.size - read)
            if (count < 0) throw Rejected(400, "Incomplete body")
            read += count
        }
        val text = try {
            Charsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(body)).toString()
        } catch (_: Exception) { throw Rejected(400, "Invalid UTF-8") }
        return Request(method, uri, headers, text)
    }
}
