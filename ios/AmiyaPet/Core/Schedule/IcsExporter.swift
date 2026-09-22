import Foundation

public class IcsExporter {
    public static func exportToIcs(
        courses: [Course],
        termStart: Date,
        sections: [String: String],
        remindMinutes: Int = 20
    ) -> String {
        let calendar = Calendar.current
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyyMMdd'T'HHmmss"
        dateFormatter.timeZone = TimeZone.current

        var ics = "BEGIN:VCALENDAR\r\n"
        ics += "VERSION:2.0\r\n"
        ics += "PRODID:-//AmiyaPet//Rhodes Island Course Exporter//CN\r\n"
        ics += "CALSCALE:GREGORIAN\r\n"
        ics += "METHOD:PUBLISH\r\n"
        ics += "X-WR-CALNAME:阿米娅排课日程\r\n"

        for course in courses {
            guard let startTime = course.startTime(weekNo: course.weekStart, sections: sections) else {
                continue
            }
            // 计算第一周对应的星期几
            // 默认第一周从 termStart 开始推算
            let weekdayOffset = (course.weekday - 1)
            guard let courseStartDate = calendar.date(byAdding: .day, value: (course.weekStart - 1) * 7 + weekdayOffset, to: termStart) else {
                continue
            }

            var startComponents = calendar.dateComponents([.year, .month, .day], from: courseStartDate)
            startComponents.hour = startTime.hour
            startComponents.minute = startTime.minute
            startComponents.second = 0
            guard let eventStart = calendar.date(from: startComponents) else { continue }

            // 计算结束时间
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

            let totalWeeks = course.weekEnd - course.weekStart + 1
            let interval = (course.parity == "all") ? 1 : 2
            let count = (course.parity == "all") ? totalWeeks : (totalWeeks / 2 + 1)

            ics += "BEGIN:VEVENT\r\n"
            ics += "UID:\(course.id)-\(UUID().uuidString.prefix(8))\r\n"
            ics += "DTSTAMP:\(dateFormatter.string(from: Date()))\r\n"
            ics += "DTSTART:\(dateFormatter.string(from: eventStart))\r\n"
            ics += "DTEND:\(dateFormatter.string(from: eventEnd))\r\n"
            ics += "SUMMARY:\(course.name)\r\n"
            ics += "LOCATION:\(course.room)\r\n"
            ics += "DESCRIPTION:教师: \(course.teacher) | 节次: \(course.formattedSectionDisplay()) | \(course.note)\r\n"
            ics += "RRULE:FREQ=WEEKLY;INTERVAL=\(interval);COUNT=\(count)\r\n"

            if remindMinutes > 0 {
                ics += "BEGIN:VALARM\r\n"
                ics += "TRIGGER:-PT\(remindMinutes)M\r\n"
                ics += "ACTION:DISPLAY\r\n"
                ics += "DESCRIPTION:阿米娅提醒博士：该上 \(course.name) 啦！\r\n"
                ics += "END:VALARM\r\n"
            }
            ics += "END:VEVENT\r\n"
        }

        ics += "END:VCALENDAR\r\n"
        return ics
    }
}
