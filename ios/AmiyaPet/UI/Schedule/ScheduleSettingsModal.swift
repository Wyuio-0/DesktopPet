import SwiftUI

public struct ScheduleSettingsModal: View {
    @ObservedObject var manager = ScheduleManager.shared
    @Environment(\.dismiss) var dismiss

    @State private var termStartDate: Date = Date()
    @State private var weekStartDay: String = "sunday"
    @State private var remindEnabled: Bool = true
    @State private var dismissRemindEnabled: Bool = true
    @State private var liveClassEnabled: Bool = true
    @State private var remindMinutes: Int = 20

    public init() {}

    public var body: some View {
        NavigationStack {
            Form {
                Section(header: Text("学期与周次设定")) {
                    DatePicker("第一周开学日期", selection: $termStartDate, displayedComponents: [.date])
                    Picker("周视图首列起始日", selection: $weekStartDay) {
                        Text("周日为首列 (日 一 二 三 四 五 六)").tag("sunday")
                        Text("周一为首列 (一 二 三 四 五 六 日)").tag("monday")
                    }
                }

                Section(header: Text("灵动微卡片 (Live Activity)"), footer: Text("在上课期间，iPhone 灵动岛与锁屏将常驻显示实时下课进度条、倒计时与下节课教室预告。")) {
                    Toggle("锁屏/灵动岛上课实时进度", isOn: $liveClassEnabled)
                    Button("⚡ 立即测试灵动微卡片 (Live Activity)") {
                        testLiveActivity()
                    }
                    .foregroundColor(Color.amiyaPrimary)
                }

                Section(header: Text("准点上课与下课关怀")) {
                    Toggle("课前提醒 (带好水杯书本)", isOn: $remindEnabled)
                    if remindEnabled {
                        Picker("提前提醒时间", selection: $remindMinutes) {
                            Text("提前 10 分钟").tag(10)
                            Text("提前 15 分钟").tag(15)
                            Text("提前 20 分钟").tag(20)
                            Text("提前 30 分钟").tag(30)
                        }
                    }
                    Toggle("下课换教室与就餐关怀提醒", isOn: $dismissRemindEnabled)

                    HStack {
                        Button("测试课前提醒") {
                            NotificationManager.shared.sendTestReminder(isDismissal: false)
                        }
                        Spacer()
                        Button("测试下课提醒") {
                            NotificationManager.shared.sendTestReminder(isDismissal: true)
                        }
                    }
                    .foregroundColor(Color.amiyaPrimary)
                }
            }
            .navigationTitle("课表作息与提醒设置")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("保存") {
                        save()
                    }
                }
            }
            .onAppear {
                termStartDate = manager.termStart ?? Date()
                weekStartDay = manager.weekStartDay
                remindEnabled = manager.remindEnabled
                dismissRemindEnabled = manager.dismissRemindEnabled
                liveClassEnabled = manager.liveClassEnabled
                remindMinutes = manager.remindMinutes
            }
        }
    }

    private func save() {
        manager.termStart = termStartDate
        manager.weekStartDay = weekStartDay
        manager.remindEnabled = remindEnabled
        manager.dismissRemindEnabled = dismissRemindEnabled
        manager.liveClassEnabled = liveClassEnabled
        manager.remindMinutes = remindMinutes
        manager.save()
        dismiss()
    }

    private func testLiveActivity() {
        let testCourse = Course(
            name: "高等数学",
            weekday: 1,
            secStart: 3,
            secEnd: 4,
            weekStart: 1,
            weekEnd: 16,
            room: "主教楼 302",
            teacher: "王教授"
        )
        LiveActivityManager.shared.startCourseActivity(
            course: testCourse,
            elapsedMinutes: 77,
            remainingMinutes: 18,
            progress: 0.81,
            nextCoursePreview: "▷ 下一节课：14:05 第 6-7 节《大学物理》（📍实验楼 201）"
        )
    }
}
