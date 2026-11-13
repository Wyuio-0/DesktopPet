import Foundation
import CryptoKit
import Security

enum SyncCrypto {
    static let maxPlain = 4 * 1024 * 1024
    static let maxWire = (maxPlain + 16) * 4 / 3 + 2048
    static let paths: Set<String> = ["/api/pair/request", "/api/sync/pull", "/api/sync/push", "/api/clipboard", "/api/status", "/api/pair/unpair"]
    enum Failure: Error { case invalid }
    struct Envelope: Codable {
        var v: Int; var kid: String; var epoch: String; var id: String
        var ts: Int64; var s: Int; var nonce: String; var ct: String
    }
    static func random(_ count: Int) -> Data {
        var bytes = [UInt8](repeating: 0, count: count)
        precondition(SecRandomCopyBytes(kSecRandomDefault, count, &bytes) == errSecSuccess)
        return Data(bytes)
    }
    static func b64(_ data: Data) -> String {
        data.base64EncodedString().replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "=", with: "")
    }
    static func decode(_ value: String, size: Int? = nil) throws -> Data {
        guard value.utf8.count <= maxWire else { throw Failure.invalid }
        let encoded = value.replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")
        let padded = encoded + String(repeating: "=", count: (4 - encoded.count % 4) % 4)
        guard let data = Data(base64Encoded: padded), b64(data) == value,
              size == nil || data.count == size else { throw Failure.invalid }
        return data
    }
    static func newSecret() -> String { b64(random(32)) }
    static func keyId(_ secret: String) throws -> String { b64(Data(SHA256.hash(data: try decode(secret, size: 32)))) }
    static func pairingCode(_ secret: String) throws -> String {
        let hash = SHA256.hash(data: try decode(secret, size: 32))
        let value = hash.prefix(4).reduce(UInt32(0)) { ($0 << 8) | UInt32($1) }
        return String(format: "%06u", value % 1000000)
    }
    static func aad(_ path: String, _ env: Envelope, _ direction: String) throws -> Data {
        guard paths.contains(path), env.v == 2 else { throw Failure.invalid }
        _ = try decode(env.kid, size: 32); _ = try decode(env.epoch, size: 32); _ = try decode(env.id, size: 16)
        return Data("RhodesSync/2|\(direction)|POST|\(path)|\(env.kid)|\(env.epoch)|\(env.id)|\(env.ts)|\(env.s)".utf8)
    }
    static func seal(_ secret: String, _ path: String, _ plain: Data, _ context: Envelope, _ direction: String, _ status: Int) throws -> Envelope {
        guard plain.count <= maxPlain else { throw Failure.invalid }
        var env = context
        env.v = 2; env.kid = try keyId(secret); env.s = status
        let box = try AES.GCM.seal(plain, using: SymmetricKey(data: try decode(secret, size: 32)), authenticating: aad(path, env, direction))
        env.nonce = b64(box.nonce.withUnsafeBytes { Data($0) }); env.ct = b64(box.ciphertext + box.tag)
        return env
    }
    static func open(_ secret: String, _ path: String, _ env: Envelope, _ direction: String) throws -> Data {
        guard env.kid == (try keyId(secret)) else { throw Failure.invalid }
        let ct = try decode(env.ct)
        guard ct.count >= 16 && ct.count <= maxPlain + 16 else { throw Failure.invalid }
        let box = try AES.GCM.SealedBox(nonce: AES.GCM.Nonce(data: decode(env.nonce, size: 12)), ciphertext: ct.dropLast(16), tag: ct.suffix(16))
        return try AES.GCM.open(box, using: SymmetricKey(data: decode(secret, size: 32)), authenticating: aad(path, env, direction))
    }
    static func request(_ secret: String, _ path: String, _ plain: Data, _ epoch: String) throws -> Envelope {
        let context = Envelope(v: 2, kid: try keyId(secret), epoch: epoch, id: b64(random(16)),
            ts: Int64(Date().timeIntervalSince1970), s: 0, nonce: "", ct: "")
        return try seal(secret, path, plain, context, "request", 0)
    }
    static func response(_ secret: String, _ path: String, _ env: Envelope, _ request: Envelope, _ status: Int) throws -> Data {
        guard env.s == status && env.epoch == request.epoch && env.id == request.id && env.ts == request.ts else { throw Failure.invalid }
        return try open(secret, path, env, "response")
    }
    final class Server {
        let epoch = newSecret()
        private let lock = NSRecursiveLock()
        private var invite: (String, TimeInterval)?
        private var claimed: String?
        private var seen: [String: TimeInterval] = [:]
        func createInvite() -> String {
            lock.lock(); defer { lock.unlock() }
            let secret = newSecret(); invite = (secret, ProcessInfo.processInfo.systemUptime + 300); claimed = nil
            return secret
        }
        func inviteSecret(_ kid: String) -> String? {
            lock.lock(); defer { lock.unlock() }
            guard let item = invite, item.1 > ProcessInfo.processInfo.systemUptime,
                  (try? keyId(item.0)) == kid else { return nil }
            return item.0
        }
        func consumeInvite(_ secret: String) {
            lock.lock(); defer { lock.unlock() }
            if invite?.0 == secret { invite = nil; claimed = nil }
        }
        func claimInvite(_ secret: String, _ id: String) -> Bool {
            lock.lock(); defer { lock.unlock() }
            guard inviteSecret((try? keyId(secret)) ?? "") == secret && claimed == nil else { return false }
            claimed = secret + "." + id; return true
        }
        func releaseInvite(_ secret: String, _ id: String) {
            lock.lock(); defer { lock.unlock() }
            if claimed == secret + "." + id { claimed = nil }
        }
        func accept(_ secret: String, _ path: String, _ env: Envelope) throws -> Data {
            let plain = try open(secret, path, env, "request")
            guard env.epoch == epoch && env.s == 0 && abs(Date().timeIntervalSince1970 - Double(env.ts)) <= 120 else { throw Failure.invalid }
            lock.lock(); defer { lock.unlock() }
            let now = ProcessInfo.processInfo.systemUptime
            seen = seen.filter { $0.value > now }
            let identity = env.kid + "." + env.id
            guard seen[identity] == nil && seen.count < 4096 else { throw Failure.invalid }
            seen[identity] = now + 241
            return plain
        }
    }
}
