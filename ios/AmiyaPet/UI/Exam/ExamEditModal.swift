import SwiftUI

public struct ExamEditModal: View {
    var existingExam: ExamItem?
    var onSaved: (ExamItem) -> Void
    @Environment(\.dismiss) var dismiss

    @State private var title: String = ""
    @State private var examDate: Date = Date().addingTimeInterval(86400 * 3)
    @State private var durationMinutes: Int = 120
    @State private var location: String = ""
    @State private var seatNumber: String = ""
    @State private var examType: String = "闭卷"
    @State private var note: String = ""

    private let examTypes = ["闭卷", "开卷", "大作业", "答辩", "机考"]

    public init(existingExam: ExamItem? = nil, onSaved: @escaping (ExamItem) -> Void) {
        self.existingExam = existingExam
        self.onSaved = onSaved
    }

    public var body: some View {
        NavigationStack {
            Form {
                Section(header: Text("考试科目")) {
                    TextField("科目名称 (如: 高等数学期末统考)", text: $title)
                    Picker("考试形式", selection: $examType) {
                        ForEach(examTypes, id: \.self) { t in
                            Text(t).tag(t)
                        }
                    }
                }

                Section(header: Text("时间与考场")) {
                    DatePicker("开考时间", selection: $examDate, displayedComponents: [.date, .hourAndMinute])
                    Picker("考试时长", selection: $durationMinutes) {
                        Text("60 分钟 (1小时)").tag(60)
                        Text("90 分钟 (1.5小时)").tag(90)
                        Text("120 分钟 (2小时)").tag(120)
                        Text("150 分钟 (2.5小时)").tag(150)
                    }
                    TextField("考场地点 (如: 主教楼 302)", text: $location)
                    TextField("座位号 (如: 第4排 12号)", text: $seatNumber)
                }

                Section(header: Text("备考事项")) {
                    TextField("携带文具、计算器或复习要点", text: $note)
                }
            }
            .navigationTitle(existingExam == nil ? "录入期末考" : "编辑考试")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("保存") {
                        save()
                    }
                    .disabled(title.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
            .onAppear {
                if let e = existingExam {
                    title = e.title
                    examDate = Date(timeIntervalSince1970: TimeInterval(e.examTimeMillis) / 1000.0)
                    durationMinutes = e.durationMinutes
                    location = e.location
                    seatNumber = e.seatNumber
                    examType = e.examType
                    note = e.note
                }
            }
        }
    }

    private func save() {
        let item = ExamItem(
            id: existingExam?.id ?? UUID().uuidString,
            title: title.trimmingCharacters(in: .whitespaces),
            examTimeMillis: Int64(examDate.timeIntervalSince1970 * 1000),
            durationMinutes: durationMinutes,
            location: location.trimmingCharacters(in: .whitespaces),
            seatNumber: seatNumber.trimmingCharacters(in: .whitespaces),
            examType: examType,
            note: note.trimmingCharacters(in: .whitespaces)
        )
        if existingExam != nil {
            ExamManager.shared.updateExam(item)
        } else {
            ExamManager.shared.addExam(item)
        }
        onSaved(item)
        dismiss()
    }
}
