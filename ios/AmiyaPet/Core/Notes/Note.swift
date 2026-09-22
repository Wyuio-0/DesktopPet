import Foundation

public struct Note: Codable, Identifiable, Hashable {
    public var id: String
    public var title: String
    public var content: String
    public var createdAt: String
    public var updatedAt: String
    public var pinned: Bool

    public init(
        id: String = "note_" + UUID().uuidString.prefix(8),
        title: String = "灵感随记",
        content: String = "",
        createdAt: String = Note.currentTimestamp(),
        updatedAt: String = Note.currentTimestamp(),
        pinned: Bool = false
    ) {
        self.id = id
        self.title = title
        self.content = content
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.pinned = pinned
    }

    public func autoDeriveTitle(maxLen: Int = 16) -> String {
        guard let firstLine = content.components(separatedBy: .newlines).first(where: { !$0.trimmingCharacters(in: .whitespaces).isEmpty }) else {
            return "空白便签"
        }
        let cleaned = firstLine.trimmingCharacters(in: CharacterSet(charactersIn: "#-*• "))
        if cleaned.count > maxLen {
            return String(cleaned.prefix(maxLen)) + "…"
        }
        return cleaned
    }

    public static func currentTimestamp() -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd HH:mm"
        return formatter.string(from: Date())
    }

    enum CodingKeys: String, CodingKey {
        case id, title, content, pinned
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}
