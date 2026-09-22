import Foundation

public struct ChatMessage: Identifiable, Hashable {
    public let id: String
    public var role: String // "user", "assistant", "system"
    public var content: String
    public var reasoningContent: String
    public var isThinking: Bool
    public var isStreaming: Bool
    public var timestamp: Date

    // 结构化交互卡片载荷
    public var addedCourse: Course?
    public var deletedCourse: Course?
    public var startedPomodoroMinutes: Int?
    public var createdNote: Note?
    public var adjustedScheduleList: [ScheduleAdjustment]?

    public init(
        id: String = UUID().uuidString,
        role: String,
        content: String,
        reasoningContent: String = "",
        isThinking: Bool = false,
        isStreaming: Bool = false,
        timestamp: Date = Date(),
        addedCourse: Course? = nil,
        deletedCourse: Course? = nil,
        startedPomodoroMinutes: Int? = nil,
        createdNote: Note? = nil,
        adjustedScheduleList: [ScheduleAdjustment]? = nil
    ) {
        self.id = id
        self.role = role
        self.content = content
        self.reasoningContent = reasoningContent
        self.isThinking = isThinking
        self.isStreaming = isStreaming
        self.timestamp = timestamp
        self.addedCourse = addedCourse
        self.deletedCourse = deletedCourse
        self.startedPomodoroMinutes = startedPomodoroMinutes
        self.createdNote = createdNote
        self.adjustedScheduleList = adjustedScheduleList
    }

    public var isUser: Bool { role == "user" }
}
