import Foundation
import Combine

public class ScheduleManager: ObservableObject {
    public static let shared = ScheduleManager()

    public static let defaultSections: [String: String] = [
        "1": "08:00", "2": "08:50", "3": "09:50", "4": "10:40", "5": "11:30",
        "6": "14:05", "7": "14:55", "8": "15:45", "9": "16:40", "10": "17:30",
        "11": "18:30", "12": "19:20", "13": "20:10"
    ]

    public static let defaultSectionEndTimes: [String: String] = [
        "1": "08:45", "2": "09:35", "3": "10:35", "4": "11:25", "5": "12:15",
        "6": "14:50", "7": "15:40", "8": "16:30", "9": "17:25", "10": "18:15",
        "11": "19:15", "12": "20:05", "13": "20:55"
    ]

    @Published public var termStart: Date?
    @Published public var sections: [String: String] = ScheduleManager.defaultSections
    @Published public var remindEnabled: Bool = true
    @Published public var dismissRemindEnabled: Bool = true
    @Published public var liveClassEnabled: Bool = true
    @Published public var remindMinutes: Int = 20
    @Published public var weekStartDay: String = "sunday" // "sunday" or "monday"
    @Published public var courses: [Course] = []
    @Published public var notes: [String] = []
    @Published public var adjustments: [ScheduleAdjustment] = []
    @Published public var coursesVersion: Int = 0

    private let fileURL: URL

    private init() {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        fileURL = docs.appendingPathComponent("schedule.json")
        load()
    }

    public func getScheduleFile() -> URL {
        return fileURL
    }

    public func load() {
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            initSampleScheduleIfNeeded()
            return
        }
        do {
            let data = try Data(contentsOf: fileURL)
            if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] {
                parseJson(json)
            }
        } catch {
            print("Failed to load schedule.json: \(error)")
        }
    }

    private func initSampleScheduleIfNeeded() {
        // 默认开学日期为本学期初（如2026年9月1日所在周一或周日）
        let calendar = Calendar.current
        var comps = calendar.dateComponents([.year, .month], from: Date())
        comps.day = 1
        termStart = calendar.date(from: comps)
        courses = [
            Course(name: "高等数学", weekday: 1, secStart: 1, secEnd: 2, weekStart: 1, weekEnd: 16, parity: "all", room: "主教楼 302", teacher: "王教授"),
            Course(name: "大学物理", weekday: 1, secStart: 6, secEnd: 7, weekStart: 1, weekEnd: 16, parity: "all", room: "实验楼 201", teacher: "李老师"),
            Course(name: "数据结构与算法", weekday: 2, secStart: 3, secEnd: 4, weekStart: 1, weekEnd: 16, parity: "all", room: "信息楼 102", teacher: "张教授"),
            Course(name: "毛泽东思想概论", weekday: 3, secStart: 1, secEnd: 2, weekStart: 1, weekEnd: 16, parity: "all", room: "文理楼 405", teacher: "刘老师"),
            Course(name: "人工智能导论", weekday: 4, secStart: 6, secEnd: 8, weekStart: 1, weekEnd: 16, parity: "all", room: "科技楼 501", teacher: "陈教授"),
            Course(name: "学术英语", weekday: 5, secStart: 3, secEnd: 4, weekStart: 1, weekEnd: 16, parity: "all", room: "外语楼 208", teacher: "Sarah")
        ]
        save()
    }

    private func parseJson(_ json: [String: Any]) {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        if let termStr = json["term_start"] as? String {
            termStart = formatter.date(from: termStr)
        }
        if let secMap = json["sections"] as? [String: String] {
            sections = secMap
        }
        if let rEnabled = json["remind_enabled"] as? Bool {
            remindEnabled = rEnabled
        }
        if let dEnabled = json["dismiss_remind_enabled"] as? Bool {
            dismissRemindEnabled = dEnabled
        }
        if let lEnabled = json["live_class_enabled"] as? Bool {
            liveClassEnabled = lEnabled
        }
        if let rMin = json["remind_minutes"] as? Int {
            remindMinutes = rMin
        }
        if let wStart = json["week_start_day"] as? String {
            weekStartDay = wStart
        }
        if let notesList = json["notes"] as? [String] {
            notes = notesList
        }

        if let courseData = try? JSONSerialization.data(withJSONObject: json["courses"] ?? []),
           let parsedCourses = try? JSONDecoder().decode([Course].self, from: courseData) {
            courses = parsedCourses
        }

        if let adjData = try? JSONSerialization.data(withJSONObject: json["adjustments"] ?? []),
           let parsedAdj = try? JSONDecoder().decode([ScheduleAdjustment].self, from: adjData) {
            adjustments = parsedAdj
        }
    }

    public func save() {
        var dict: [String: Any] = [:]
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        if let termStart = termStart {
            dict["term_start"] = formatter.string(from: termStart)
        }
        dict["sections"] = sections
        dict["remind_enabled"] = remindEnabled
        dict["dismiss_remind_enabled"] = dismissRemindEnabled
        dict["live_class_enabled"] = liveClassEnabled
        dict["remind_minutes"] = remindMinutes
        dict["week_start_day"] = weekStartDay
        dict["notes"] = notes

        if let courseData = try? JSONEncoder().encode(courses),
           let courseObj = try? JSONSerialization.jsonObject(with: courseData) {
            dict["courses"] = courseObj
        }
        if let adjData = try? JSONEncoder().encode(adjustments),
           let adjObj = try? JSONSerialization.jsonObject(with: adjData) {
            dict["adjustments"] = adjObj
        }

        do {
            let data = try JSONSerialization.data(withJSONObject: dict, options: .prettyPrinted)
            try data.write(to: fileURL)
            coursesVersion += 1
            NotificationCenter.default.post(name: NSNotification.Name("AmiyaScheduleUpdated"), object: nil)
        } catch {
            print("Failed to save schedule.json: \(error)")
        }
    }

    public func getWeekNo(for date: Date = Date()) -> Int {
        guard let start = termStart else { return 1 }
        let calendar = Calendar.current
        let startDay = calendar.startOfDay(for: start)
        let currentDay = calendar.startOfDay(for: date)
        let diff = calendar.dateComponents([.day], from: startDay, to: currentDay).day ?? 0
        if diff < 0 { return 1 }
        return (diff / 7) + 1
    }

    public func getDatesForWeek(weekNo: Int) -> [Date] {
        var calendar = Calendar.current
        calendar.firstWeekday = (weekStartDay == "sunday") ? 1 : 2
        let start = termStart ?? Date()
        guard let targetWeekStart = calendar.date(byAdding: .day, value: (weekNo - 1) * 7, to: start) else {
            return []
        }
        var dates: [Date] = []
        for i in 0..<7 {
            if let d = calendar.date(byAdding: .day, value: i, to: targetWeekStart) {
                dates.append(d)
            }
        }
        return dates
    }

    public func getAdjustment(for date: Date) -> ScheduleAdjustment? {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        let dateStr = formatter.string(from: date)
        return adjustments.first { $0.date == dateStr }
    }

    public func getCoursesForDay(weekNo: Int, weekday: Int, date: Date? = nil) -> [Course] {
        if let d = date, let adj = getAdjustment(for: d) {
            if adj.isSuspend {
                return []
            }
            if adj.isSubstitute, let tw = adj.targetWeek, let twd = adj.targetWeekday {
                return courses.filter { $0.weekday == twd && $0.activeOn(weekNo: tw) }
                    .sorted { $0.secStart < $1.secStart }
            }
        }
        return courses.filter { $0.weekday == weekday && $0.activeOn(weekNo: weekNo) }
            .sorted { $0.secStart < $1.secStart }
    }

    public func getTodayCourses() -> [Course] {
        let calendar = Calendar.current
        let today = Date()
        let weekNo = getWeekNo(for: today)
        // Calendar weekday: 1 is Sunday, 2 is Monday
        let calWeekday = calendar.component(.weekday, from: today)
        let weekday = (calWeekday == 1) ? 7 : (calWeekday - 1)
        return getCoursesForDay(weekNo: weekNo, weekday: weekday, date: today)
    }

    public func getActiveCourseNow() -> (course: Course, elapsedMinutes: Int, remainingMinutes: Int, progress: Double)? {
        let todayCourses = getTodayCourses()
        let calendar = Calendar.current
        let now = Date()
        let currentHour = calendar.component(.hour, from: now)
        let currentMinute = calendar.component(.minute, from: now)
        let currentTotalMins = currentHour * 60 + currentMinute

        for c in todayCourses {
            guard let startTimeStr = sections[String(c.secStart)],
                  let endTimeStr = ScheduleManager.defaultSectionEndTimes[String(c.secEnd)] else {
                continue
            }
            let sParts = startTimeStr.components(separatedBy: ":")
            let eParts = endTimeStr.components(separatedBy: ":")
            guard sParts.count == 2, eParts.count == 2,
                  let sh = Int(sParts[0]), let sm = Int(sParts[1]),
                  let eh = Int(eParts[0]), let em = Int(eParts[1]) else {
                continue
            }
            let startMins = sh * 60 + sm
            let endMins = eh * 60 + em

            if currentTotalMins >= startMins && currentTotalMins <= endMins {
                let totalDuration = max(1, endMins - startMins)
                let elapsed = currentTotalMins - startMins
                let remaining = max(0, endMins - currentTotalMins)
                let progress = min(1.0, max(0.0, Double(elapsed) / Double(totalDuration)))
                return (c, elapsed, remaining, progress)
            }
        }
        return nil
    }

    public func getNextUpcomingCourse() -> (course: Course, startsInMinutes: Int)? {
        let todayCourses = getTodayCourses()
        let calendar = Calendar.current
        let now = Date()
        let currentHour = calendar.component(.hour, from: now)
        let currentMinute = calendar.component(.minute, from: now)
        let currentTotalMins = currentHour * 60 + currentMinute

        for c in todayCourses {
            guard let startTimeStr = sections[String(c.secStart)] else { continue }
            let sParts = startTimeStr.components(separatedBy: ":")
            guard sParts.count == 2, let sh = Int(sParts[0]), let sm = Int(sParts[1]) else { continue }
            let startMins = sh * 60 + sm
            if startMins > currentTotalMins {
                return (c, startMins - currentTotalMins)
            }
        }
        return nil
    }

    public func addCourse(_ course: Course) {
        courses.append(course)
        save()
    }

    public func deleteCourse(id: String) {
        courses.removeAll { $0.id == id }
        save()
    }

    public func updateCourse(_ updated: Course) {
        if let idx = courses.firstIndex(where: { $0.id == updated.id }) {
            courses[idx] = updated
            save()
        }
    }

    public func buildScheduleAnalysisContext() -> String {
        let weekNo = getWeekNo()
        let activeCourses = courses.filter { $0.activeOn(weekNo: weekNo) }
        var result = "【博士当前真实排课档案】：\n"
        result += "- 当前学期进行至：第 \(weekNo) 周\n"
        result += "- 本周修读课程总门数：\(Set(activeCourses.map { $0.name }).count) 门，共计 \(activeCourses.count) 个课时段\n"
        result += "- 课程列表：\n"
        for c in activeCourses.prefix(15) {
            let weekdayStr = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][max(0, min(6, c.weekday - 1))]
            result += "  · \(c.name) (\(weekdayStr) \(c.formattedSectionDisplay()) 📍\(c.room))\n"
        }
        return result
    }
}
