import SwiftUI

@main
struct AmiyaPetApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @Environment(\.scenePhase) var scenePhase

    var body: some Scene {
        WindowGroup {
            MainTabView()
                .onChange(of: scenePhase) { newPhase in
                    if newPhase == .active {
                        PomodoroTimer.shared.refreshTime()
                        checkAndRefreshLiveActivity()
                    }
                }
        }
    }

    private func checkAndRefreshLiveActivity() {
        guard ScheduleManager.shared.liveClassEnabled else { return }
        if let active = ScheduleManager.shared.getActiveCourseNow() {
            let nextInfo = ScheduleManager.shared.getNextUpcomingCourse()
            let nextStr = nextInfo != nil ? "▷ 下一节课：\(nextInfo!.course.formattedSectionDisplay()) 《\(nextInfo!.course.name)》（📍\(nextInfo!.course.room)）" : "今日课程已全部结束，注意休息哦~"
            LiveActivityManager.shared.startCourseActivity(
                course: active.course,
                elapsedMinutes: active.elapsedMinutes,
                remainingMinutes: active.remainingMinutes,
                progress: active.progress,
                nextCoursePreview: nextStr
            )
        }
    }
}
