import Foundation

public struct ScheduleAdjustment: Codable, Identifiable, Hashable {
    public var id: String
    public var date: String              // "yyyy-MM-dd", 例如 "2026-09-20"
    public var type: String              // "substitute" 或 "suspend" 或 "normal"
    public var targetWeek: Int?          // 若 substitute，按第几周课表执行
    public var targetWeekday: Int?       // 若 substitute，按周几课表执行 (1=周一, 7=周日)
    public var reason: String            // 调整原因，例如 "按第5周周二执行"、"国庆放假停课"

    public init(
        id: String = UUID().uuidString,
        date: String,
        type: String = "substitute",
        targetWeek: Int? = nil,
        targetWeekday: Int? = nil,
        reason: String = ""
    ) {
        self.id = id
        self.date = date
        self.type = type
        self.targetWeek = targetWeek
        self.targetWeekday = targetWeekday
        self.reason = reason
    }

    public var isSubstitute: Bool { type == "substitute" }
    public var isSuspend: Bool { type == "suspend" }

    enum CodingKeys: String, CodingKey {
        case id
        case date
        case type
        case targetWeek = "target_week"
        case targetWeekday = "target_weekday"
        case reason
    }
}
