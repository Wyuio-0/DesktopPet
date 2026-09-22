import Foundation
import UserNotifications
import UIKit

public class NotificationManager {
    public static let shared = NotificationManager()

    private init() {}

    public func requestAuthorization(completion: @escaping (Bool) -> Void) {
        let center = UNUserNotificationCenter.current()
        center.requestAuthorization(options: [.alert, .sound, .badge]) { granted, error in
            DispatchQueue.main.async {
                completion(granted)
            }
        }
    }

    public func scheduleCourseReminders(courses: [Course], sections: [String: String], remindMinutes: Int = 20) {
        let center = UNUserNotificationCenter.current()
        center.removeAllPendingNotificationRequests()

        guard ScheduleManager.shared.remindEnabled else { return }

        let calendar = Calendar.current
        let today = Date()
        let weekNo = ScheduleManager.shared.getWeekNo(for: today)

        for course in courses {
            guard course.activeOn(weekNo: weekNo),
                  let start = course.startTime(weekNo: weekNo, sections: sections) else {
                continue
            }

            // 计算提醒时间 = 开课时间 - remindMinutes
            var triggerDateComponents = DateComponents()
            triggerDateComponents.weekday = (course.weekday == 7) ? 1 : (course.weekday + 1)
            let totalStartMins = start.hour * 60 + start.minute
            let remindTotalMins = totalStartMins - remindMinutes
            if remindTotalMins < 0 { continue }
            triggerDateComponents.hour = remindTotalMins / 60
            triggerDateComponents.minute = remindTotalMins % 60

            let content = UNMutableNotificationContent()
            content.title = "⏰ 上课提醒: 《\(course.name)》"
            content.body = "博士，还有 \(remindMinutes) 分钟就要上课啦（\(course.formattedSectionDisplay())），地点在 📍\(course.room)。请带好书本和水杯哦~"
            content.sound = .default
            content.badge = 1

            let trigger = UNCalendarNotificationTrigger(dateMatching: triggerDateComponents, repeats: true)
            let request = UNNotificationRequest(identifier: "course_remind_\(course.id)", content: content, trigger: trigger)
            center.add(request)
        }
    }

    public func sendTestReminder(isDismissal: Bool = false) {
        let content = UNMutableNotificationContent()
        if isDismissal {
            content.title = "🚶 下课换教室提醒 (测试)"
            content.body = "博士，《高等数学》下课啦！下一节是第 6-7 节《大学物理》（📍实验楼 201），请留意换教室别跑错教学楼哦~"
        } else {
            content.title = "⏰ 课前提醒 (测试)"
            content.body = "博士，还有 20 分钟就要上课啦！第 3-4 节《高等数学》（📍主教楼 302），请带好书本和水杯哦~"
        }
        content.sound = .default

        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 1.0, repeats: false)
        let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: trigger)
        UNUserNotificationCenter.current().add(request)
    }
}
