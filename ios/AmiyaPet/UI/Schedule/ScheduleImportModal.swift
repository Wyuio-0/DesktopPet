import SwiftUI
import PhotosUI

public struct ScheduleImportModal: View {
    @Environment(\.dismiss) var dismiss
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var selectedImage: UIImage?
    @State private var isAnalyzing: Bool = false
    @State private var recognizedCourses: [Course] = []
    @State private var selectedCourseIds: Set<String> = []
    @State private var errorMessage: String?

    public init() {}

    public var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                if recognizedCourses.isEmpty {
                    // 选图 / 拍照引导界面
                    VStack(spacing: 20) {
                        Image(systemName: "camera.viewfinder")
                            .font(.system(size: 64))
                            .foregroundColor(Color.amiyaPrimary)

                        VStack(spacing: 6) {
                            Text("AI 多模态智能识图导课")
                                .font(.system(size: 18, weight: .bold))
                            Text("选取教务系统课表截图或拍照，阿米娅将自动提取课程、节次、教室与教师全量信息。")
                                .font(.system(size: 14))
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal, 20)
                        }

                        if isAnalyzing {
                            VStack(spacing: 10) {
                                ProgressView()
                                Text("智谱 / DeepSeek 多模态神经元解析中...")
                                    .font(.system(size: 13))
                                    .foregroundColor(.secondary)
                            }
                            .padding(.top, 10)
                        } else {
                            PhotosPicker(selection: $selectedPhotoItem, matching: .images) {
                                HStack {
                                    Image(systemName: "photo.on.rectangle")
                                    Text("从相册选择课表图片")
                                }
                                .font(.system(size: 16, weight: .semibold))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 14)
                                .background(Color.amiyaPrimary)
                                .foregroundColor(.white)
                                .cornerRadius(12)
                                .padding(.horizontal, 32)
                            }
                            .onChange(of: selectedPhotoItem) { newItem in
                                guard let item = newItem else { return }
                                loadAndAnalyze(item: item)
                            }
                        }

                        if let err = errorMessage {
                            Text(err)
                                .font(.system(size: 13))
                                .foregroundColor(.red)
                                .padding(.horizontal)
                        }
                    }
                    .frame(maxHeight: .infinity)
                } else {
                    // 识别结果确认列表
                    VStack(spacing: 12) {
                        HStack {
                            Text("共识别出 \(recognizedCourses.count) 门课程")
                                .font(.system(size: 15, weight: .bold))
                            Spacer()
                            Button("全选") {
                                selectedCourseIds = Set(recognizedCourses.map { $0.id })
                            }
                            .font(.system(size: 13))
                            .foregroundColor(Color.amiyaPrimary)
                        }
                        .padding(.horizontal)

                        List {
                            ForEach(recognizedCourses) { c in
                                HStack {
                                    Image(systemName: selectedCourseIds.contains(c.id) ? "checkmark.circle.fill" : "circle")
                                        .foregroundColor(selectedCourseIds.contains(c.id) ? Color.amiyaPrimary : .secondary)

                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(c.name)
                                            .font(.system(size: 15, weight: .semibold))
                                        HStack(spacing: 8) {
                                            Text(weekdayStr(c.weekday))
                                            Text(c.formattedSectionDisplay())
                                            Text(c.room.isEmpty ? "未指定教室" : c.room)
                                        }
                                        .font(.system(size: 12))
                                        .foregroundColor(.secondary)
                                    }
                                }
                                .contentShape(Rectangle())
                                .onTapGesture {
                                    if selectedCourseIds.contains(c.id) {
                                        selectedCourseIds.remove(c.id)
                                    } else {
                                        selectedCourseIds.insert(c.id)
                                    }
                                }
                            }
                        }
                        .listStyle(PlainListStyle())

                        // 导入选项按钮
                        HStack(spacing: 12) {
                            Button(action: { importSelected(overrideAll: false) }) {
                                Text("增量合并导入")
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 12)
                                    .background(Color.secondary.opacity(0.15))
                                    .foregroundColor(.primary)
                                    .cornerRadius(10)
                            }

                            Button(action: { importSelected(overrideAll: true) }) {
                                Text("覆盖现有课表")
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 12)
                                    .background(Color.amiyaPrimary)
                                    .foregroundColor(.white)
                                    .cornerRadius(10)
                            }
                        }
                        .padding(.horizontal)
                        .padding(.bottom, 12)
                    }
                }
            }
            .navigationTitle("AI 课表识图导入")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("关闭") { dismiss() }
                }
            }
        }
    }

    private func loadAndAnalyze(item: PhotosPickerItem) {
        isAnalyzing = true
        errorMessage = nil
        Task {
            guard let data = try? await item.loadTransferable(type: Data.self),
                  let uiImage = UIImage(data: data) else {
                DispatchQueue.main.async {
                    isAnalyzing = false
                    errorMessage = "未能读取图片数据"
                }
                return
            }
            AmiyaBrain.shared.analyzeScheduleImage(image: uiImage) { result in
                isAnalyzing = false
                switch result {
                case .success(let courses):
                    recognizedCourses = courses
                    selectedCourseIds = Set(courses.map { $0.id })
                case .failure(let error):
                    errorMessage = "AI 识别失败: \(error.localizedDescription)"
                }
            }
        }
    }

    private func importSelected(overrideAll: Bool) {
        let toImport = recognizedCourses.filter { selectedCourseIds.contains($0.id) }
        if overrideAll {
            ScheduleManager.shared.courses = toImport
        } else {
            ScheduleManager.shared.courses.append(contentsOf: toImport)
        }
        ScheduleManager.shared.save()
        dismiss()
    }

    private func weekdayStr(_ w: Int) -> String {
        let arr = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return arr[max(0, min(6, w - 1))]
    }
}
