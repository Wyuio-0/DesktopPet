import Foundation
import Combine

public struct ExamItem: Codable, Identifiable, Hashable {
    public var id: String
    public var title: String
    public var examTimeMillis: Int64
    public var durationMinutes: Int
    public var location: String
    public var seatNumber: String
    public var examType: String
    public var note: String
    public var relatedCourseId: String?

    public init(
        id: String = UUID().uuidString,
        title: String,
        examTimeMillis: Int64,
        durationMinutes: Int = 120,
        location: String = "",
        seatNumber: String = "",
        examType: String = "闭卷",
        note: String = "",
        relatedCourseId: String? = nil
    ) {
        self.id = id
        self.title = title
        self.examTimeMillis = examTimeMillis
        self.durationMinutes = durationMinutes
        self.location = location
        self.seatNumber = seatNumber
        self.examType = examType
        self.note = note
        self.relatedCourseId = relatedCourseId
    }

    public var endTimeMillis: Int64 {
        examTimeMillis + Int64(durationMinutes) * 60_000
    }

    public func isFinished(now: Int64 = Int64(Date().timeIntervalSince1970 * 1000)) -> Bool {
        now > endTimeMillis
    }

    public func isOngoing(now: Int64 = Int64(Date().timeIntervalSince1970 * 1000)) -> Bool {
        now >= examTimeMillis && now <= endTimeMillis
    }

    public func remainingDays(now: Int64 = Int64(Date().timeIntervalSince1970 * 1000)) -> Int {
        let diff = examTimeMillis - now
        if diff <= 0 { return 0 }
        return Int((diff + 86_399_999) / 86_400_000)
    }

    public func formattedDateStr() -> String {
        let date = Date(timeIntervalSince1970: TimeInterval(examTimeMillis) / 1000.0)
        let sdf = DateFormatter()
        sdf.locale = Locale(identifier: "zh_CN")
        sdf.dateFormat = "M月d日 EEEE"
        return sdf.string(from: date)
    }

    public func formattedTimeRangeStr() -> String {
        let start = Date(timeIntervalSince1970: TimeInterval(examTimeMillis) / 1000.0)
        let end = Date(timeIntervalSince1970: TimeInterval(endTimeMillis) / 1000.0)
        let sdf = DateFormatter()
        sdf.dateFormat = "HH:mm"
        return "\(sdf.string(from: start)) - \(sdf.string(from: end))"
    }

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case examTimeMillis = "exam_time_millis"
        case durationMinutes = "duration_minutes"
        case location
        case seatNumber = "seat_number"
        case examType = "exam_type"
        case note
        case relatedCourseId = "related_course_id"
    }
}

public class ExamManager: ObservableObject {
    public static let shared = ExamManager()

    @Published public var exams: [ExamItem] = []

    private let fileURL: URL

    private init() {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        fileURL = docs.appendingPathComponent("exams.json")
        load()
    }

    public func load() {
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            initSampleExams()
            return
        }
        do {
            let data = try Data(contentsOf: fileURL)
            let items = try JSONDecoder().decode([ExamItem].self, from: data)
            exams = items.sorted { $0.examTimeMillis < $1.examTimeMillis }
        } catch {
            print("Failed to load exams.json: \(error)")
        }
    }

    private func initSampleExams() {
        // 初始示例考试数据（两门期末考）
        let now = Date().timeIntervalSince1970 * 1000
        let dayMs: Double = 86_400_000
        exams = [
            ExamItem(
                title: "高等数学 (期末考试)",
                examTimeMillis: Int64(now + dayMs * 3),
                durationMinutes: 120,
                location: "主教楼 302",
                seatNumber: "第4排 12号",
                examType: "闭卷",
                note: "请携带2B铅笔、橡皮与学生证"
            ),
            ExamItem(
                title: "大学物理 (期末统考)",
                examTimeMillis: Int64(now + dayMs * 7),
                durationMinutes: 120,
                location: "实验楼 101",
                seatNumber: "第2排 05号",
                examType: "闭卷",
                note: "允许携带无编程功能的科学计算器"
            )
        ]
        save()
    }

    public func save() {
        do {
            let data = try JSONEncoder().encode(exams)
            try data.write(to: fileURL)
        } catch {
            print("Failed to save exams.json: \(error)")
        }
    }

    public func addExam(_ exam: ExamItem) {
        exams.append(exam)
        exams.sort { $0.examTimeMillis < $1.examTimeMillis }
        save()
    }

    public func updateExam(_ exam: ExamItem) {
        if let idx = exams.firstIndex(where: { $0.id == exam.id }) {
            exams[idx] = exam
            exams.sort { $0.examTimeMillis < $1.examTimeMillis }
            save()
        }
    }

    public func deleteExam(id: String) {
        exams.removeAll { $0.id == id }
        save()
    }

    public func hasUrgentExam(withinHours hours: Int = 24) -> Bool {
        let now = Int64(Date().timeIntervalSince1970 * 1000)
        let limit = now + Int64(hours) * 3600 * 1000
        return exams.contains { !$0.isFinished(now: now) && $0.examTimeMillis <= limit }
    }
}
