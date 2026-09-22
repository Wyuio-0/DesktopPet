import SwiftUI

public struct IcsExportModal: View {
    @Environment(\.dismiss) var dismiss
    @State private var isExportingToCalendar: Bool = false
    @State private var exportStatusMessage: String?
    @State private var isSharingIcs: Bool = false
    @State private var icsFileURL: URL?

    public init() {}

    public var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                Image(systemName: "calendar.badge.clock")
                    .font(.system(size: 60))
                    .foregroundColor(Color.amiyaPrimary)
                    .padding(.top, 20)

                VStack(spacing: 6) {
                    Text("导出课表至系统日程")
                        .font(.system(size: 18, weight: .bold))
                    Text("将当前排课、节次时间与上课提醒导入至 Apple 系统日历，可在 iPhone、iPad 与 Apple Watch 间无缝同步。")
                        .font(.system(size: 14))
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                }

                if let msg = exportStatusMessage {
                    Text(msg)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(Color.amiyaPrimary)
                        .padding(10)
                        .background(Color.amiyaPrimary.opacity(0.1))
                        .cornerRadius(10)
                }

                Spacer()

                VStack(spacing: 12) {
                    // 方式 1: 直接写入 Apple 原生日历
                    Button(action: exportDirectlyToCalendar) {
                        HStack {
                            Image(systemName: "calendar")
                            Text("直接写入 Apple 系统日历")
                        }
                        .font(.system(size: 15, weight: .semibold))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(Color.amiyaPrimary)
                        .foregroundColor(.white)
                        .cornerRadius(12)
                    }
                    .disabled(isExportingToCalendar)

                    // 方式 2: 生成标准 .ics 文件分享
                    Button(action: exportAndShareIcs) {
                        HStack {
                            Image(systemName: "square.and.arrow.up")
                            Text("导出 .ics 文件并分享")
                        }
                        .font(.system(size: 15, weight: .semibold))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(Color.secondary.opacity(0.12))
                        .foregroundColor(.primary)
                        .cornerRadius(12)
                    }
                }
                .padding(.horizontal)
                .padding(.bottom, 20)
            }
            .navigationTitle("日历同步与导出")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("关闭") { dismiss() }
                }
            }
            .sheet(isPresented: $isSharingIcs) {
                if let url = icsFileURL {
                    ActivityView(activityItems: [url])
                }
            }
        }
    }

    private func exportDirectlyToCalendar() {
        isExportingToCalendar = true
        exportStatusMessage = "正在请求系统权限并写入日历..."
        let manager = ScheduleManager.shared
        CalendarManager.shared.syncCoursesToCalendar(
            courses: manager.courses,
            termStart: manager.termStart ?? Date(),
            sections: manager.sections,
            remindMinutes: manager.remindMinutes
        ) { count, err in
            isExportingToCalendar = false
            if let err = err {
                exportStatusMessage = "写入失败: \(err.localizedDescription)"
            } else {
                exportStatusMessage = "✅ 成功向系统日历添加了 \(count) 门周期性课程！"
            }
        }
    }

    private func exportAndShareIcs() {
        let manager = ScheduleManager.shared
        let icsContent = IcsExporter.exportToIcs(
            courses: manager.courses,
            termStart: manager.termStart ?? Date(),
            sections: manager.sections,
            remindMinutes: manager.remindMinutes
        )
        let tempDir = FileManager.default.temporaryDirectory
        let file = tempDir.appendingPathComponent("amiya_schedule.ics")
        try? icsContent.write(to: file, atomically: true, encoding: .utf8)
        self.icsFileURL = file
        self.isSharingIcs = true
    }
}

public struct ActivityView: UIViewControllerRepresentable {
    let activityItems: [Any]
    public func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: activityItems, applicationActivities: nil)
    }
    public func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
