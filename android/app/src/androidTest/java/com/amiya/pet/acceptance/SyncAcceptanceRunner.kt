package com.amiya.pet.acceptance

import android.app.Activity
import android.app.Instrumentation
import android.os.Bundle
import com.amiya.pet.core.sync.SyncManager
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.Proxy
import java.net.URL
import java.io.FileInputStream
import java.util.concurrent.atomic.AtomicReference

/** ADB instrumentation for the separate .syncacceptance application only. */
class SyncAcceptanceRunner : Instrumentation() {
    private lateinit var arguments: Bundle
    private val checks = JSONArray()
    private var approval = "accept"
    private val lastIncoming = AtomicReference("")
    private val app get() = targetContext.applicationContext
    private val host get() = arguments.getString("host", "127.0.0.1")
    private val pcPort get() = arguments.getString("pc_port")!!.toInt()
    private fun token() = SyncManager.getDeviceToken(app, "acceptance-pc")

    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        this.arguments = arguments ?: Bundle()
        start()
    }

    private fun control(action: String, fields: JSONObject = JSONObject()): JSONObject {
        fields.put("action", action)
        val port = arguments.getString("control_port")!!.toInt()
        val conn = URL("http://127.0.0.1:$port/").openConnection(Proxy.NO_PROXY) as HttpURLConnection
        return try {
            conn.connectTimeout = 5000; conn.readTimeout = 45000; conn.doOutput = true; conn.requestMethod = "POST"
            conn.instanceFollowRedirects = false
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setRequestProperty("Authorization", "Bearer " + arguments.getString("control_token"))
            conn.outputStream.use { it.write(fields.toString().toByteArray(Charsets.UTF_8)) }
            check(conn.responseCode == 200) { "acceptance control rejected $action" }
            JSONObject(conn.inputStream.bufferedReader().use { it.readText() })
        } finally { conn.disconnect() }
    }

    private suspend fun case(name: String, block: suspend () -> Unit) {
        val result = JSONObject().put("name", name)
        try { block(); result.put("passed", true) }
        catch (error: Throwable) {
            result.put("passed", false).put("error", error.javaClass.simpleName + ": " + (error.message ?: "failed").take(180))
        }
        checks.put(result)
        android.util.Log.i("SyncAcceptance", name + ": " + result.optBoolean("passed"))
        sendStatus(0, Bundle().apply { putString("stream", name + ": " + if (result.optBoolean("passed")) "PASS\n" else "FAIL\n") })
    }

    private fun snapshot() = SyncManager.packAllData(app)
    private fun item(array: JSONArray, id: String): JSONObject? = (0 until array.length())
        .map { array.getJSONObject(it) }.firstOrNull { it.optString("id") == id }

    override fun onStart() {
        val summary = JSONObject()
        try {
            check(app.packageName == "com.amiya.pet.syncacceptance") { "Refusing to test a production data directory" }
            android.util.Log.i("SyncAcceptance", "Starting isolated foreground")
            uiAutomation.executeShellCommand("am start -W -n " + app.packageName + "/com.amiya.pet.acceptance.SyncAcceptanceActivity").use {
                FileInputStream(it.fileDescriptor).use { input -> input.readBytes() }
            }
            android.util.Log.i("SyncAcceptance", "Preparing native sync")
            val prefs = app.getSharedPreferences("amiya_paired_devices", 0)
            prefs.edit().clear().putString("my_device_id", "acceptance-android").commit()
            runBlocking {
                SyncManager.onPairRequestedListener = { request ->
                    lastIncoming.set(request.requestId)
                    if (request.clientId == "acceptance-pc" && approval != "hold") {
                        SyncManager.confirmPairRequest(request.requestId, approval == "accept")
                    }
                }
                SyncManager.start(app)
                repeat(40) { if (SyncManager.isServerRunning) delay(100) }
                control("phone_port", JSONObject().put("port", SyncManager.localHttpPort))
                val expected = control("seed").getJSONObject("expected")
                case("legacy_pair_cannot_send") {
                    prefs.edit().putString("paired_list", JSONObject().put("legacy", JSONObject()
                        .put("token", "legacy-test-token").put("name", "legacy").put("ip", host).put("port", pcPort)).toString()).commit()
                    check(!SyncManager.sendClipboard(app, host, pcPort, "legacy-test-token", "must not arrive"))
                }
                case("wrong_secret_rejected") {
                    // A valid 256-bit key tests the receiver, rather than local format validation.
                    val wrongKey = android.util.Base64.encodeToString(
                        java.security.SecureRandom().generateSeed(32),
                        android.util.Base64.URL_SAFE or android.util.Base64.NO_PADDING or android.util.Base64.NO_WRAP)
                    check(!SyncManager.requestPairToRemote(app, host, pcPort, wrongKey).first)
                }
                case("android_to_pc_pair") {
                    val result = SyncManager.requestPairToRemote(app, host, pcPort, arguments.getString("pairing_secret")!!)
                    check(result.first) { result.second }
                    control("phone_port", JSONObject().put("port", SyncManager.localHttpPort))
                }
                case("pull_from_pc") { check(SyncManager.syncPull(app, host, pcPort, token()).success) }
                case("course_fields_survive_pull") {
                    val wanted = expected.getJSONObject("schedule").getJSONArray("courses").getJSONObject(0)
                    val actual = item(snapshot().getJSONObject("schedule").getJSONArray("courses"), wanted.getString("id"))
                    check(actual != null) { "course id was lost" }
                    for (field in listOf("name", "weekday", "sec_start", "sec_end", "week_start", "week_end", "parity", "custom_time", "room", "teacher", "campus", "note")) {
                        check(actual.optString(field) == wanted.optString(field)) { "course $field changed" }
                    }
                    check(snapshot().getJSONObject("schedule").getJSONObject("sections").getString("1") == "08:07") { "section time changed" }
                }
                case("exam_fields_survive_pull") {
                    val wanted = expected.getJSONArray("exams").getJSONObject(0)
                    val actual = item(snapshot().getJSONArray("exams"), wanted.getString("id"))
                    check(actual != null) { "exam id was lost" }
                    for (field in listOf("title", "examTimeMillis", "durationMinutes", "location", "seatNumber", "examType", "note", "relatedCourseId")) {
                        check(actual.optString(field) == wanted.optString(field)) { "exam $field changed" }
                    }
                }
                case("unicode_note_survives_pull") {
                    val wanted = expected.getJSONArray("notes").getJSONObject(0)
                    check(item(snapshot().getJSONArray("notes"), wanted.getString("id"))?.getString("content") == wanted.getString("content"))
                }
                case("android_to_pc_unicode_clipboard") {
                    check(SyncManager.sendClipboard(app, host, pcPort, token(), "Android 真机中文快传 😀"))
                    check(control("check_clipboard").getBoolean("ok"))
                }
                case("pc_to_android_unicode_clipboard") {
                    val received = AtomicReference("")
                    SyncManager.onTacticalDropReceived = { text, _ -> received.set(text) }
                    check(control("send_clipboard").getBoolean("ok"))
                    check(received.get() == "PC 中文快传到真机 😀")
                }
                case("android_push_and_pc_pull") {
                    check(SyncManager.syncPush(app, host, pcPort, token(), "merge").success)
                    check(control("pull_phone").getBoolean("ok"))
                    check(control("check_pc_data").getBoolean("ok")) { "PC round trip changed fixture fields" }
                }
                case("pc_push_and_repeat_merge_no_duplicates") {
                    check(control("push_phone").getBoolean("ok"))
                    val before = snapshot()
                    check(SyncManager.syncPull(app, host, pcPort, token()).success)
                    val after = snapshot()
                    check(after.getJSONArray("exams").length() == before.getJSONArray("exams").length()) { "duplicate exams" }
                    check(after.getJSONObject("schedule").getJSONArray("courses").length() == before.getJSONObject("schedule").getJSONArray("courses").length()) { "duplicate courses" }
                }
                case("pc_service_restart_keeps_trust") {
                    control("restart_pc")
                    check(SyncManager.syncPull(app, host, pcPort, token()).success)
                }
                case("android_service_restart_keeps_trust") {
                    SyncManager.stop(); delay(700); SyncManager.start(app); delay(1000)
                    control("phone_port", JSONObject().put("port", SyncManager.localHttpPort))
                    check(control("pull_phone").getBoolean("ok"))
                }
                case("receiver_rejects_pair_without_replacing_trust") {
                    val before = token(); approval = "reject"
                    check(!control("pair_phone", JSONObject().put("secret", SyncManager.createPairingInvite())).getBoolean("ok"))
                    check(token() == before); approval = "accept"
                }
                case("expired_invitation_rejected") {
                    val expired = control("expired_invite").getString("secret")
                    check(!SyncManager.requestPairToRemote(app, host, pcPort, expired).first)
                }
                case("revoked_credentials_fail_closed") {
                    SyncManager.unpairDevice(app, "acceptance-pc")
                    check(!control("send_clipboard").getBoolean("ok"))
                }
                case("repair_after_revocation") {
                    val fresh = control("new_invite").getString("secret")
                    check(SyncManager.requestPairToRemote(app, host, pcPort, fresh).first)
                    control("phone_port", JSONObject().put("port", SyncManager.localHttpPort))
                    check(control("pull_phone").getBoolean("ok"))
                }
            }
            summary.put("checks", checks).put("passed", (0 until checks.length()).all { checks.getJSONObject(it).optBoolean("passed") })
        } catch (error: Throwable) {
            summary.put("passed", false).put("fatal", error.javaClass.simpleName + ": " + (error.message ?: "failed").take(180)).put("checks", checks)
        } finally {
            SyncManager.onPairRequestedListener = null; SyncManager.onTacticalDropReceived = null; SyncManager.stop()
        }
        finish(if (summary.optBoolean("passed")) Activity.RESULT_OK else Activity.RESULT_CANCELED,
            Bundle().apply { putString("summary", summary.toString()) })
    }
}
