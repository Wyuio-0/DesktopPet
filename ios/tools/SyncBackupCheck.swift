import Foundation

@main struct SyncBackupCheck {
    static func main() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("amiya-backup-check-" + UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: dir) }
        let store = SyncBackupStore(directory: dir)
        let payload: [String: Any] = ["data": ["notes": [["id": "example-note", "content": "中文与 emoji 😀"]]], "local": ["notes": [String: Any]()]]
        var checks = 0
        func fails(_ operation: () throws -> Void) {
            do { try operation(); fatalError("Expected rejection") } catch { checks += 1 }
        }
        let id = try store.create(payload)
        let restored = try store.load(id)
        let notes = (restored["data"] as! [String: Any])["notes"] as! [[String: Any]]
        precondition(notes[0]["content"] as? String == "中文与 emoji 😀"); checks += 1
        fails { _ = try store.load("../notes") }
        fails { _ = try store.create(["data": ["settings": [String: Any]()], "local": ["settings": [String: Any]()]]) }
        for _ in 0..<12 { try store.create(payload) }
        let retained = try store.list()
        print("Retained backup count: \(retained.count)")
        precondition(retained.count == SyncBackupStore.keep); checks += 1
        let recovery = try store.create(payload, reason: "before_restore")
        let recoveryEntries = try store.list()
        precondition(recoveryEntries.contains { $0.id == recovery && $0.reason == "before_restore" }); checks += 1
        let file = dir.appendingPathComponent(recovery + ".json")
        var envelope = try JSONSerialization.jsonObject(with: Data(contentsOf: file)) as! [String: Any]
        envelope["payload"] = (envelope["payload"] as! String) + " "
        try JSONSerialization.data(withJSONObject: envelope).write(to: file)
        fails { _ = try store.load(recovery) }
        let damaged = try store.list()
        precondition(damaged.contains { $0.id == recovery && !$0.valid }); checks += 1
        envelope["payload"] = (envelope["payload"] as! String).dropLast().description
        envelope["platform"] = "android"
        try JSONSerialization.data(withJSONObject: envelope).write(to: file)
        fails { _ = try store.load(recovery) }
        print("Sync backup checks passed: \(checks)")
    }
}
