import SwiftUI

public struct CourseEditModal: View {
    var existingCourse: Course?
    var onSaved: (Course) -> Void
    @Environment(\.dismiss) var dismiss

    @State private var name: String = ""
    @State private var weekday: Int = 1
    @State private var secStart: Int = 1
    @State private var secEnd: Int = 2
    @State private var weekStart: Int = 1
    @State private var weekEnd: Int = 16
    @State private var parity: String = "all"
    @State private var room: String = ""
    @State private var teacher: String = ""
    @State private var customTime: String = ""
    @State private var note: String = ""

    private let weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    public init(existingCourse: Course? = nil, defaultWeekday: Int = 1, defaultSecStart: Int = 1, onSaved: @escaping (Course) -> Void) {
        self.existingCourse = existingCourse
        self.onSaved = onSaved
        _weekday = State(initialValue: existingCourse?.weekday ?? defaultWeekday)
        _secStart = State(initialValue: existingCourse?.secStart ?? defaultSecStart)
        _secEnd = State(initialValue: existingCourse?.secEnd ?? (defaultSecStart + 1))
    }

    public var body: some View {
        NavigationStack {
            Form {
                Section(header: Text("基础信息")) {
                    TextField("课程名称 (如: 高等数学)", text: $name)
                    Picker("星期", selection: $weekday) {
                        ForEach(1...7, id: \.self) { w in
                            Text(weekdays[w - 1]).tag(w)
                        }
                    }
                    HStack {
                        Picker("起始节", selection: $secStart) {
                            ForEach(1...13, id: \.self) { s in
                                Text("第\(s)节").tag(s)
                            }
                        }
                        Picker("结束节", selection: $secEnd) {
                            ForEach(secStart...13, id: \.self) { s in
                                Text("第\(s)节").tag(s)
                            }
                        }
                    }
                }

                Section(header: Text("地点与教师")) {
                    TextField("教室 / 地点 (如: 主教楼 302)", text: $room)
                    TextField("授课教师 (如: 王教授)", text: $teacher)
                }

                Section(header: Text("周期与作息")) {
                    HStack {
                        Stepper("第 \(weekStart) 周", value: $weekStart, in: 1...weekEnd)
                        Spacer()
                        Text("至")
                        Spacer()
                        Stepper("第 \(weekEnd) 周", value: $weekEnd, in: weekStart...30)
                    }
                    Picker("单双周", selection: $parity) {
                        Text("每周").tag("all")
                        Text("仅单周").tag("odd")
                        Text("仅双周").tag("even")
                    }
                    .pickerStyle(SegmentedPickerStyle())

                    TextField("精确作息时间 (选填，如 14:15-15:30)", text: $customTime)
                }

                Section(header: Text("备注")) {
                    TextField("课程备注或实验要求", text: $note)
                }
            }
            .navigationTitle(existingCourse == nil ? "录入新课程" : "编辑课程")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("保存") {
                        save()
                    }
                    .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
            .onAppear {
                if let c = existingCourse {
                    name = c.name
                    weekday = c.weekday
                    secStart = c.secStart
                    secEnd = c.secEnd
                    weekStart = c.weekStart
                    weekEnd = c.weekEnd
                    parity = c.parity
                    room = c.room
                    teacher = c.teacher
                    customTime = c.customTime
                    note = c.note
                }
            }
        }
    }

    private func save() {
        let course = Course(
            id: existingCourse?.id ?? UUID().uuidString,
            name: name.trimmingCharacters(in: .whitespaces),
            weekday: weekday,
            secStart: secStart,
            secEnd: max(secStart, secEnd),
            weekStart: weekStart,
            weekEnd: weekEnd,
            parity: parity,
            room: room.trimmingCharacters(in: .whitespaces),
            teacher: teacher.trimmingCharacters(in: .whitespaces),
            note: note.trimmingCharacters(in: .whitespaces),
            customTime: customTime.trimmingCharacters(in: .whitespaces)
        )
        if existingCourse != nil {
            ScheduleManager.shared.updateCourse(course)
        } else {
            ScheduleManager.shared.addCourse(course)
        }
        onSaved(course)
        dismiss()
    }
}
