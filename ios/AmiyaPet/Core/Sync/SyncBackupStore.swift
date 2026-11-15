import Foundation
import CryptoKit

enum StudyBackupFailure: LocalizedError {
    case invalid, backupFailed, writeFailed
    var errorDescription: String? {
        switch self {
        case .invalid: return "备份损坏、已丢失或不兼容，未恢复。"
        case .backupFailed: return "无法安全保存备份，覆盖已取消。请检查本机存储。"
        case .writeFailed: return "学业数据写入失败，请检查本机存储及已保存的备份。"
        }
    }
}

struct StudyBackupEntry: Identifiable {
    let id: String
    let createdMillis: Int64
    let reason: String
    let categories: [String]
    let valid: Bool
}

final class SyncBackupStore {
    static let shared = SyncBackupStore(directory: FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!.appendingPathComponent("sync_backups"))
    static let keep = 10
    private let maximum = 16 * 1024 * 1024
    private let directory: URL
    private let lock = NSRecursiveLock()
    init(directory: URL) { self.directory = directory }
    private func validId(_ id: String) -> Bool {
        id.range(of: "^b-[0-9]{13}-[a-f0-9]{32}$", options: .regularExpression) != nil
    }
    private func file(_ id: String) throws -> URL {
        guard validId(id) else { throw StudyBackupFailure.invalid }
        let url = directory.appendingPathComponent(id + ".json")
        if (try? url.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink) == true { throw StudyBackupFailure.invalid }
        return url
    }
    private func files() throws -> [URL] {
        guard FileManager.default.fileExists(atPath: directory.path) else { return [] }
        return try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)
            .filter { $0.pathExtension == "json" && validId($0.deletingPathExtension().lastPathComponent) }
            .sorted { $0.lastPathComponent > $1.lastPathComponent }
    }
    private func digest(_ body: String) -> String { SHA256.hash(data: Data(body.utf8)).map { String(format: "%02x", $0) }.joined() }
    private func check(_ payload: [String: Any]) throws {
        guard Set(payload.keys) == Set(["data", "local"]), let data = payload["data"] as? [String: Any],
              !data.isEmpty, Set(data.keys).isSubset(of: Set(["schedule", "exams", "notes"])),
              let local = payload["local"] as? [String: Any], Set(local.keys) == Set(data.keys) else { throw StudyBackupFailure.invalid }
    }
    private func read(_ id: String) throws -> ([String: Any], [String: Any]) {
        do {
            let url = try file(id)
            let size = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? maximum + 1
            guard size <= maximum else { throw StudyBackupFailure.invalid }
            let bytes = try Data(contentsOf: url)
            guard bytes.count <= maximum, let envelope = try JSONSerialization.jsonObject(with: bytes) as? [String: Any],
                  envelope["schema"] as? Int == 1, envelope["platform"] as? String == "ios", envelope["id"] as? String == id,
                  let created = envelope["created_ms"] as? Int64, created > 0, created < 253402300800000,
                  let reason = envelope["reason"] as? String, ["before_replace", "before_restore"].contains(reason),
                  let body = envelope["payload"] as? String, envelope["sha256"] as? String == digest(body),
                  let payload = try JSONSerialization.jsonObject(with: Data(body.utf8)) as? [String: Any] else { throw StudyBackupFailure.invalid }
            try check(payload)
            return (envelope, payload)
        } catch { throw StudyBackupFailure.invalid }
    }
    func load(_ id: String) throws -> [String: Any] {
        lock.lock(); defer { lock.unlock() }
        return try read(id).1
    }
    @discardableResult func create(_ payload: [String: Any], reason: String = "before_replace") throws -> String {
        lock.lock(); defer { lock.unlock() }
        do {
            try check(payload)
            guard ["before_replace", "before_restore"].contains(reason), try files().count <= Self.keep else { throw StudyBackupFailure.backupFailed }
            let now = Int64(Date().timeIntervalSince1970 * 1000)
            let id = "b-\(now)-" + UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased()
            let url = try file(id)
            let body = String(decoding: try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]), as: UTF8.self)
            let envelope: [String: Any] = ["schema": 1, "platform": "ios", "id": id, "created_ms": now,
                "reason": reason, "payload": body, "sha256": digest(body)]
            let bytes = try JSONSerialization.data(withJSONObject: envelope)
            guard bytes.count <= maximum else { throw StudyBackupFailure.backupFailed }
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            try bytes.write(to: url, options: .atomic)
            _ = try read(id)
            // Directory enumeration can produce a differently based URL for the
            // same file. Protect the new snapshot by its validated filename.
            for old in try files().filter({ $0.lastPathComponent != id + ".json" }).dropFirst(Self.keep - 1) { try FileManager.default.removeItem(at: old) }
            return id
        } catch { throw StudyBackupFailure.backupFailed }
    }
    func list() throws -> [StudyBackupEntry] {
        lock.lock(); defer { lock.unlock() }
        return try files().map { url in
            let id = url.deletingPathExtension().lastPathComponent
            do {
                let (entry, payload) = try read(id)
                return StudyBackupEntry(id: id, createdMillis: (entry["created_ms"] as? NSNumber)?.int64Value ?? 0,
                    reason: entry["reason"] as? String ?? "", categories: Array((payload["data"] as! [String: Any]).keys).sorted(), valid: true)
            } catch { return StudyBackupEntry(id: id, createdMillis: 0, reason: "corrupt", categories: [], valid: false) }
        }
    }
}
