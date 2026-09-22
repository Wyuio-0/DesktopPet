import Foundation

public struct Course: Codable, Identifiable, Hashable {
    public var id: String
    public var name: String
    public var weekday: Int // 1=周一, 7=周日
    public var secStart: Int
    public var secEnd: Int
    public var weekStart: Int
    public var weekEnd: Int
    public var parity: String // "all", "odd", "even"
    public var room: String
    public var teacher: String
    public var campus: String
    public var note: String
    public var customTime: String // 如 "14:15-15:30"

    public init(
        id: String = UUID().uuidString,
        name: String,
        weekday: Int,
        secStart: Int,
        secEnd: Int,
        weekStart: Int,
        weekEnd: Int,
        parity: String = "all",
        room: String = "",
        teacher: String = "",
        campus: String = "",
        note: String = "",
        customTime: String = ""
    ) {
        self.id = id
        self.name = name
        self.weekday = weekday
        self.secStart = secStart
        self.secEnd = secEnd
        self.weekStart = weekStart
        self.weekEnd = weekEnd
        self.parity = parity
        self.room = room
        self.teacher = teacher
        self.campus = campus
        self.note = note
        self.customTime = customTime
    }

    public var isActivity: Bool {
        !customTime.trimmingCharacters(in: .whitespaces).isEmpty
    }

    public func activeOn(weekNo: Int) -> Bool {
        if weekNo < weekStart || weekNo > weekEnd { return false }
        switch parity.lowercased() {
        case "even": return weekNo % 2 == 0
        case "odd": return weekNo % 2 == 1
        default: return true
        }
    }

    public func startTime(weekNo: Int, sections: [String: String]) -> (hour: Int, minute: Int)? {
        guard activeOn(weekNo: weekNo) else { return nil }
        if !customTime.isEmpty && customTime.contains(":") {
            let delimiters = CharacterSet(charactersIn: "-~至到")
            let parts = customTime.components(separatedBy: delimiters)
            if let startPart = parts.first?.trimmingCharacters(in: .whitespaces) {
                let timeParts = startPart.components(separatedBy: ":")
                if timeParts.count >= 2,
                   let h = Int(timeParts[0].trimmingCharacters(in: .whitespaces)),
                   let m = Int(timeParts[1].trimmingCharacters(in: .whitespaces)),
                   (0...23).contains(h), (0...59).contains(m) {
                    return (h, m)
                }
            }
        }
        guard let timeStr = sections[String(secStart)] else { return nil }
        let parts = timeStr.components(separatedBy: ":")
        if parts.count == 2,
           let h = Int(parts[0]),
           let m = Int(parts[1]),
           (0...23).contains(h), (0...59).contains(m) {
            return (h, m)
        }
        return nil
    }

    public func formattedSectionDisplay() -> String {
        if isActivity {
            return customTime
        }
        if secStart == secEnd {
            return "第\(secStart)节"
        }
        return "第\(secStart)-\(secEnd)节"
    }

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case weekday
        case secStart = "sec_start"
        case secEnd = "sec_end"
        case weekStart = "week_start"
        case weekEnd = "week_end"
        case parity
        case room
        case teacher
        case campus
        case note
        case customTime = "custom_time"
    }
}
