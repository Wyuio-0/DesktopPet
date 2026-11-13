import Foundation

@main struct SyncCryptoCheck {
    static func main() throws {
        let rows = try String(contentsOfFile: CommandLine.arguments[1], encoding: .utf8).split(separator: "\n").dropFirst()
        var checks = 0
        for row in rows {
            let p = row.split(separator: "\t", omittingEmptySubsequences: false).map(String.init)
            let env = SyncCrypto.Envelope(v: 2, kid: try SyncCrypto.keyId(p[0]), epoch: p[3], id: p[4], ts: Int64(p[5])!, s: Int(p[6])!, nonce: p[7], ct: p[8])
            let plain = try SyncCrypto.decode(p[9])
            let decoded = try SyncCrypto.open(p[0], p[1], env, p[2]); precondition(decoded == plain); checks += 1
            let fresh = try SyncCrypto.seal(p[0], p[1], plain, env, p[2], env.s)
            let opened = try SyncCrypto.open(p[0], p[1], fresh, p[2]); precondition(opened == plain); checks += 1
            var damaged = try SyncCrypto.decode(env.ct); damaged[damaged.count - 1] ^= 1
            var changed = env; changed.ct = SyncCrypto.b64(damaged)
            precondition((try? SyncCrypto.open(p[0], p[1], changed, p[2])) == nil); checks += 1
            precondition((try? SyncCrypto.open(p[0], "/api/status", env, p[2])) == nil); checks += 1
            if p[2] == "response" {
                var request = env; request.s = 0
                let bound = try SyncCrypto.response(p[0], p[1], env, request, env.s); precondition(bound == plain); checks += 1
                precondition((try? SyncCrypto.response(p[0], p[1], env, request, 500)) == nil); checks += 1
                request.id = SyncCrypto.b64(Data(repeating: 0, count: 16))
                precondition((try? SyncCrypto.response(p[0], p[1], env, request, env.s)) == nil); checks += 1
            }
        }
        let server = SyncCrypto.Server(); let secret = server.createInvite()
        let request = try SyncCrypto.request(secret, "/api/status", Data("{}".utf8), server.epoch)
        let accepted = try server.accept(secret, "/api/status", request); precondition(accepted == Data("{}".utf8)); checks += 1
        precondition((try? server.accept(secret, "/api/status", request)) == nil); checks += 1
        precondition((try? SyncCrypto.Server().accept(secret, "/api/status", request)) == nil); checks += 1
        precondition(server.claimInvite(secret, "one")); checks += 1
        precondition(!server.claimInvite(secret, "two")); checks += 1
        server.releaseInvite(secret, "one")
        precondition(server.claimInvite(secret, "two")); checks += 1
        print("Sync crypto checks passed: \(checks)")
    }
}
