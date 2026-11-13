package com.amiya.pet.core.sync

import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/** Rhodes Sync v2 AES-256-GCM wire format; no Android dependency. */
internal object SyncCrypto {
    const val MAX_PLAIN = 4 * 1024 * 1024
    const val MAX_WIRE = (MAX_PLAIN + 16) * 4 / 3 + 2048
    val paths = setOf("/api/pair/request", "/api/sync/pull", "/api/sync/push", "/api/clipboard", "/api/status", "/api/pair/unpair")
    private val random = SecureRandom()
    data class Envelope(val v: Int, val kid: String, val epoch: String, val id: String,
                        val ts: Long, val s: Int, val nonce: String, val ct: String)
    fun b64(bytes: ByteArray): String = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes)
    fun decode(text: String, size: Int? = null): ByteArray {
        require(text.length <= MAX_WIRE)
        val bytes = Base64.getUrlDecoder().decode(text)
        require(b64(bytes) == text && (size == null || bytes.size == size))
        return bytes
    }
    private fun bytes(size: Int) = ByteArray(size).also { random.nextBytes(it) }
    fun newSecret() = b64(bytes(32))
    fun keyId(secret: String) = b64(MessageDigest.getInstance("SHA-256").digest(decode(secret, 32)))
    fun pairingCode(secret: String): String {
        val hash = MessageDigest.getInstance("SHA-256").digest(decode(secret, 32))
        val value = java.nio.ByteBuffer.wrap(hash, 0, 4).int.toLong() and 0xffffffffL
        return (value % 1000000).toString().padStart(6, '0')
    }
    fun aad(path: String, env: Envelope, direction: String): ByteArray {
        require(path in paths && env.v == 2)
        decode(env.kid, 32); decode(env.epoch, 32); decode(env.id, 16)
        return "RhodesSync/2|$direction|POST|$path|${env.kid}|${env.epoch}|${env.id}|${env.ts}|${env.s}".toByteArray(Charsets.UTF_8)
    }
    fun seal(secret: String, path: String, plain: ByteArray, context: Envelope, direction: String, status: Int): Envelope {
        require(plain.size <= MAX_PLAIN)
        val env = context.copy(v=2, kid=keyId(secret), s=status, nonce=b64(bytes(12)), ct="")
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(decode(secret, 32), "AES"), GCMParameterSpec(128, decode(env.nonce, 12)))
        cipher.updateAAD(aad(path, env, direction))
        return env.copy(ct=b64(cipher.doFinal(plain)))
    }
    fun open(secret: String, path: String, env: Envelope, direction: String): ByteArray {
        require(env.kid == keyId(secret))
        val ciphertext = decode(env.ct)
        require(ciphertext.size in 16..MAX_PLAIN + 16)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(decode(secret, 32), "AES"), GCMParameterSpec(128, decode(env.nonce, 12)))
        cipher.updateAAD(aad(path, env, direction))
        return cipher.doFinal(ciphertext)
    }
    fun request(secret: String, path: String, plain: ByteArray, epoch: String): Envelope {
        val context = Envelope(2, keyId(secret), epoch, b64(bytes(16)), System.currentTimeMillis()/1000, 0, "", "")
        return seal(secret, path, plain, context, "request", 0)
    }
    fun response(secret: String, path: String, env: Envelope, request: Envelope, status: Int): ByteArray {
        require(env.s == status && env.epoch == request.epoch && env.id == request.id && env.ts == request.ts)
        return open(secret, path, env, "response")
    }
    class Server {
        val epoch = newSecret()
        private var invite: Pair<String, Long>? = null
        private var claimed: Pair<String, String>? = null
        private val seen = mutableMapOf<String, Long>()
        @Synchronized fun createInvite(): String = newSecret().also { invite = it to (System.nanoTime() + 300_000_000_000L); claimed = null }
        @Synchronized fun inviteSecret(kid: String): String? = invite?.let {
            if (it.second > System.nanoTime() && keyId(it.first) == kid) it.first else null
        }
        @Synchronized fun consumeInvite(secret: String) { if (invite?.first == secret) { invite = null; claimed = null } }
        @Synchronized fun claimInvite(secret: String, id: String): Boolean {
            if (inviteSecret(keyId(secret)) != secret || claimed != null) return false
            claimed = secret to id; return true
        }
        @Synchronized fun releaseInvite(secret: String, id: String) { if (claimed == (secret to id)) claimed = null }
        @Synchronized fun accept(secret: String, path: String, env: Envelope): ByteArray {
            val plain = open(secret, path, env, "request")
            require(env.epoch == epoch && env.s == 0 && kotlin.math.abs(System.currentTimeMillis()/1000.0 - env.ts.toDouble()) <= 120)
            val now = System.nanoTime()
            seen.entries.removeAll { it.value <= now }
            val identity = "${env.kid}.${env.id}"
            require(identity !in seen && seen.size < 4096)
            seen[identity] = now + 241_000_000_000L
            return plain
        }
    }
}
