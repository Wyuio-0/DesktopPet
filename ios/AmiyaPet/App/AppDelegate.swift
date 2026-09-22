import UIKit
import UserNotifications

public class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    public func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        NotificationManager.shared.requestAuthorization { granted in
            if granted {
                let manager = ScheduleManager.shared
                NotificationManager.shared.scheduleCourseReminders(
                    courses: manager.courses,
                    sections: manager.sections,
                    remindMinutes: manager.remindMinutes
                )
            }
        }
        SyncManager.shared.start()
        return true
    }

    public func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        // 应用在前台时同样弹出通知横幅和声音
        completionHandler([.banner, .sound, .badge])
    }
}
