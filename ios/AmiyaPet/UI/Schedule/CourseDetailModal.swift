import SwiftUI

public struct CourseDetailModal: View {
    let course: Course
    var onEdit: () -> Void
    var onDelete: () -> Void
    var onAnalyze: () -> Void
    @Environment(\.dismiss) var dismiss

    public var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                // 课程头部
                VStack(spacing: 6) {
                    Text(course.name)
                        .font(.system(size: 20, weight: .bold))
                        .multilineTextAlignment(.center)
                    Text("节次：\(course.formattedSectionDisplay())")
                        .font(.system(size: 14))
                        .foregroundColor(.secondary)
                }
                .padding(.top, 12)

                // 详细信息列表
                VStack(spacing: 12) {
                    infoRow(icon: "mappin.and.ellipse", title: "上课教室", value: course.room.isEmpty ? "未指定教室" : course.room)
                    infoRow(icon: "person.text.rectangle", title: "授课教师", value: course.teacher.isEmpty ? "未填写教师" : course.teacher)
                    infoRow(icon: "calendar", title: "教学周次", value: "第 \(course.weekStart)-\(course.weekEnd) 周 (\(parityDisplay(course.parity)))")
                    if course.isActivity {
                        infoRow(icon: "clock.badge.checkmark", title: "精确作息", value: course.customTime)
                    }
                    if !course.note.isEmpty {
                        infoRow(icon: "text.bubble", title: "备注文档", value: course.note)
                    }
                }
                .padding()
                .background(Color.amiyaCardBg)
                .cornerRadius(14)

                Spacer()

                // 操作按钮组
                VStack(spacing: 10) {
                    Button(action: {
                        dismiss()
                        onAnalyze()
                    }) {
                        HStack {
                            Image(systemName: "sparkles")
                            Text("向阿米娅咨询学情与复习建议")
                        }
                        .font(.system(size: 15, weight: .semibold))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(Color.amiyaPrimary)
                        .foregroundColor(.white)
                        .cornerRadius(12)
                    }

                    HStack(spacing: 12) {
                        Button(action: {
                            dismiss()
                            onEdit()
                        }) {
                            Text("编辑课程")
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 10)
                                .background(Color.secondary.opacity(0.12))
                                .foregroundColor(.primary)
                                .cornerRadius(10)
                        }

                        Button(role: .destructive, action: {
                            ScheduleManager.shared.deleteCourse(id: course.id)
                            dismiss()
                            onDelete()
                        }) {
                            Text("删除课程")
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 10)
                                .background(Color.red.opacity(0.12))
                                .foregroundColor(.red)
                                .cornerRadius(10)
                        }
                    }
                }
                .padding(.bottom, 16)
            }
            .padding(.horizontal)
            .navigationTitle("课程详情")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("关闭") { dismiss() }
                }
            }
        }
    }

    private func infoRow(icon: String, title: String, value: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .foregroundColor(Color.amiyaPrimary)
                .frame(width: 20)
            Text(title)
                .foregroundColor(.secondary)
                .frame(width: 70, alignment: .leading)
            Spacer()
            Text(value)
                .font(.system(size: 14, weight: .medium))
        }
        .font(.system(size: 14))
    }

    private func parityDisplay(_ parity: String) -> String {
        switch parity {
        case "odd": return "单周"
        case "even": return "双周"
        default: return "每周"
        }
    }
}
