import Foundation

final class SyncDeletionStore {
    static let shared = SyncDeletionStore()
    static let categories = ["schedule", "exams", "notes"]
    private let lock = NSRecursiveLock()
    private let fileURL: URL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!.appendingPathComponent("sync_tombstones.json")
    private let maximumIds = 10_000
    private let maximumIdLength = 128

    private func empty() -> [String: Set<String>] { Dictionary(uniqueKeysWithValues: Self.categories.map { ($0, Set<String>()) }) }

    private func load() throws -> [String: Set<String>] {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return empty() }
        let body = try JSONSerialization.jsonObject(with: Data(contentsOf: fileURL)) as? [String: Any]
        guard let body = body, body["schema"] as? Int == 1,
              Set(body.keys).isSubset(of: Set(["schema"] + Self.categories)) else { throw StudyBackupFailure.invalid }
        var result = empty()
        for category in Self.categories {
            let rows: [String]
            if let raw = body[category] {
                guard let parsed = raw as? [String] else { throw StudyBackupFailure.invalid }
                rows = parsed
            } else { rows = [] }
            guard rows.count <= maximumIds, Set(rows).count == rows.count,
                  rows.allSatisfy({ !$0.isEmpty && $0.utf8.count <= maximumIdLength }) else { throw StudyBackupFailure.invalid }
            result[category] = Set(rows)
        }
        return result
    }

    private func save(_ value: [String: Set<String>]) throws {
        var body: [String: Any] = ["schema": 1]
        for category in Self.categories {
            guard let ids = value[category], ids.count <= maximumIds else { throw StudyBackupFailure.backupFailed }
            body[category] = ids.sorted()
        }
        let data = try JSONSerialization.data(withJSONObject: body, options: [.sortedKeys])
        try FileManager.default.createDirectory(at: fileURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: fileURL, options: .atomic)
    }

    func snapshot() throws -> [String: [String]] {
        lock.lock(); defer { lock.unlock() }
        let value = try load()
        return value.mapValues { $0.sorted() }
    }

    func validate(_ incoming: [String: [String]]) throws -> [String: [String]] {
        guard Set(incoming.keys).isSubset(of: Set(Self.categories)) else { throw SyncCrypto.Failure.invalid }
        for rows in incoming.values where rows.count > maximumIds || Set(rows).count != rows.count ||
            !rows.allSatisfy({ !$0.isEmpty && $0.utf8.count <= maximumIdLength }) {
            throw SyncCrypto.Failure.invalid
        }
        return incoming
    }

    @discardableResult func record(_ category: String, _ id: String) -> Bool {
        lock.lock(); defer { lock.unlock() }
        guard Self.categories.contains(category), !id.isEmpty, id.utf8.count <= maximumIdLength else { return false }
        do {
            var value = try load()
            value[category, default: []].insert(id)
            try save(value)
            return true
        } catch { return false }
    }

    func forget(_ category: String, _ id: String) {
        lock.lock(); defer { lock.unlock() }
        do { var value = try load(); value[category]?.remove(id); try save(value) } catch {}
    }

    func apply(_ incoming: [String: [String]], mode: String, replacing: Set<String>,
               localIds: [String: Set<String>], liveIds: [String: Set<String>]) throws -> [String: Set<String>] {
        lock.lock(); defer { lock.unlock() }
        _ = try validate(incoming)
        var value = try load()
        var remote = empty()
        for category in Self.categories {
            let rows = incoming[category] ?? []
            guard rows.count <= maximumIds, Set(rows).count == rows.count,
                  rows.allSatisfy({ !$0.isEmpty && $0.utf8.count <= maximumIdLength }) else { throw SyncCrypto.Failure.invalid }
            remote[category] = Set(rows)
            value[category, default: []].formUnion(rows)
        }
        if mode == "replace" {
            for category in replacing {
                value[category, default: []].formUnion((localIds[category] ?? []).subtracting(liveIds[category] ?? []))
                value[category, default: []].subtract((liveIds[category] ?? []).subtracting(remote[category] ?? []))
            }
        }
        try save(value)
        return value
    }
}
