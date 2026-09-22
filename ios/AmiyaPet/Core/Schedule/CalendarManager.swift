import Foundation
import EventKit

public class CalendarManager {
    public static let shared = CalendarManager()
    private let eventStore = EKEventStore()

    private init() {}

    public func requestAccess(completion: @escaping (Bool, Error?) -> Void) {
        if #available(iOS 17.0, *) {
            eventStore.requestWriteOnlyAccessToEvents { granted, error in
                DispatchQueue.main.async {
                    completion(granted, error)
                }
            }
        } else {
            eventStore.requestAccess(to: .event) { granted, error in
                DispatchQueue.main.async {
                    completion(granted, error)
                }
            }
        }
    }

    public func syncCoursesToCalendar(
        courses: [Course],
        termStart: Date,
        sections: [String: String],
        remindMinutes: Int = 20,
        completion: @escaping (Int, Error?) -> Void
    ) {
        requestAccess { [weak self] granted, error in
            guard let self = self else { return }
            guard granted else {
                completion(0, error ?? NSError(domain: "CalendarManager", code: 403, userInfo: [NSLocalizedDescriptionKey: "用户未授予日历访问权限"]))
                return
            }

            DispatchQueue.global(qos: .userInitiated).async {
                let calendar = Calendar.current
                var insertedCount = 0

                guard let defaultCalendar = self.eventStore.defaultCalendarForNewEvents else {
                    DispatchQueue.main.async {
                        completion(0, NSError(domain: "CalendarManager", code: 404, userInfo: [NSLocalizedDescriptionKey: "找不到系统默认日历"]))
                    }
                    return
                }

                for course in courses {
                    guard let startTime = course.startTime(weekNo: course.weekStart, sections: sections) else {
                        continue
                    }
                    let weekdayOffset = (course.weekday - 1)
                    guard let courseStartDate = calendar.date(byAdding: .day, value: (course.weekStart - 1) * 7 + weekdayOffset, to: termStart) else {
                        continue
                    }

                    var startComponents = calendar.dateComponents([.year, .month, .day], from: courseStartDate)
                    startComponents.hour = startTime.hour
                    startComponents.minute = startTime.minute
                    guard let eventStart = calendar.date(from: startComponents) else { continue }

                    let endHour: Int
                    let endMinute: Int
                    if let endStr = ScheduleManager.defaultSectionEndTimes[String(course.secEnd)] {
                        let parts = endStr.components(separatedBy: ":")
                        endHour = Int(parts[0]) ?? (startTime.hour + 1)
                        endMinute = Int(parts[1]) ?? startTime.minute
                    } else {
                        endHour = startTime.hour + 1
                        endMinute = startTime.minute
                    }
                    var endComponents = startComponents
                    endComponents.hour = endHour
                    endComponents.minute = endMinute
                    guard let eventEnd = calendar.date(from: endComponents) else { continue }

                    let event = EKEvent(eventStore: self.eventStore)
                    event.title = course.name
                    event.location = course.room
                    event.notes = "阿米娅排课提醒\n教师: \(course.teacher)\n节次: \(course.formattedSectionDisplay())"
                    event.startDate = eventStart
                    event.endDate = eventEnd
                    event.calendar = defaultCalendar

                    let recurrenceInterval = (course.parity == "all") ? 1 : 2
                    let recurrenceRule = EKRecurrenceRule(
                        recurrenceWith: .weekly,
                        interval: recurrenceInterval,
                        end: EKRecurrenceEnd(occurrenceCount: course.weekEnd - course.weekStart + 1)
                    )
                    event.addRecurrenceRule(recurrenceRule)

                    if remindMinutes > 0 {
                        let alarm = EKAlarm(relativeOffset: -Double(remindMinutes * 60))
                        event.addAlarm(alarm)
                    }

                    do {
                        try self.eventStore.save(event, span: .futureEvents)
                        insertedCount += 1
                    } catch {
                        print("Failed to save event: \(error)")
                    }
                }

                DispatchQueue.main.async {
                    completion(insertedCount, nil)
                }
            }
        }
    }
}
