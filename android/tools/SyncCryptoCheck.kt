package com.amiya.pet.core.sync

import java.io.File

fun checkCryptoVectors(path: String) {
    var checks = 0
    for (line in File(path).readLines(Charsets.UTF_8).drop(1)) {
        val p = line.split('\t')
        val env = SyncCrypto.Envelope(2, SyncCrypto.keyId(p[0]), p[3], p[4], p[5].toLong(), p[6].toInt(), p[7], p[8])
        val plain = SyncCrypto.decode(p[9])
        check(SyncCrypto.open(p[0], p[1], env, p[2]).contentEquals(plain)); checks++
        val fresh = SyncCrypto.seal(p[0], p[1], plain, env, p[2], env.s)
        check(SyncCrypto.open(p[0], p[1], fresh, p[2]).contentEquals(plain)); checks++
        val damaged = SyncCrypto.decode(env.ct); damaged[damaged.lastIndex] = (damaged.last().toInt() xor 1).toByte()
        check(runCatching { SyncCrypto.open(p[0], p[1], env.copy(ct=SyncCrypto.b64(damaged)), p[2]) }.isFailure); checks++
        check(runCatching { SyncCrypto.open(p[0], "/api/status", env, p[2]) }.isFailure); checks++
        if (p[2] == "response") {
            check(SyncCrypto.response(p[0], p[1], env, env.copy(s=0), env.s).contentEquals(plain)); checks++
            check(runCatching { SyncCrypto.response(p[0], p[1], env, env.copy(s=0), 500) }.isFailure); checks++
            check(runCatching { SyncCrypto.response(p[0], p[1], env, env.copy(id=SyncCrypto.b64(ByteArray(16))), env.s) }.isFailure); checks++
        }
    }
    val server = SyncCrypto.Server(); val secret = server.createInvite()
    val request = SyncCrypto.request(secret, "/api/status", "{}".toByteArray(), server.epoch)
    check(server.accept(secret, "/api/status", request).contentEquals("{}".toByteArray())); checks++
    check(runCatching { server.accept(secret, "/api/status", request) }.isFailure); checks++
    check(runCatching { SyncCrypto.Server().accept(secret, "/api/status", request) }.isFailure); checks++
    check(server.claimInvite(secret, "one")); checks++
    check(!server.claimInvite(secret, "two")); checks++
    server.releaseInvite(secret, "one")
    check(server.claimInvite(secret, "two")); checks++
    println("Sync crypto checks passed: $checks")
}
