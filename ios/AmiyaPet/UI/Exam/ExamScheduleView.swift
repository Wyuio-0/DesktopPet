import SwiftUI

public struct ExamScheduleView: View {
    @ObservedObject var manager = ExamManager.shared
    @State private var editingExam: ExamItem?
    @State private var isCreatingExam: Bool = false

    public init() {}

    public var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    // 头部阿米娅备考看板
                    HStack(spacing: 14) {
                        let hasUrgent = manager.hasUrgentExam()
                        let assetName = PetSkinRepository.shared.currentSkin.assetName(for: hasUrgent ? .urgent : .normal)
                        Image(assetName)
                            .resizable()
                            .scaledToFit()
                            .frame(width: 56, height: 56)
                            .shadow(radius: 3)

                        VStack(alignment: .leading, spacing: 4) {
                            Text(hasUrgent ? "博士，有考试即将开考！" : "期末统考进度看板")
                                .font(.system(size: 15, weight: .bold))
                            Text(hasUrgent ? "请核对准考证、文具与考场路线，保持充足睡眠！" : "提前规划复习节奏，罗德岛为博士保驾护航。")
                                .font(.system(size: 12))
                                .foregroundColor(.secondary)
                        }
                        Spacer()
                    }
                    .padding()
                    .amiyaCardStyle()
                    .padding(.horizontal)

                    // 考试卡片列表
                    if manager.exams.isEmpty {
                        VStack(spacing: 12) {
                            Image(systemName: "checkmark.seal")
                                .font(.system(size: 48))
                                .foregroundColor(.secondary.opacity(0.4))
                            Text("暂无考试安排，学业轻松无压力！")
                                .font(.system(size: 14))
                                .foregroundColor(.secondary)
                        }
                        .padding(.top, 40)
                    } else {
                        VStack(spacing: 12) {
                            ForEach(manager.exams) { exam in
                                examCard(for: exam)
                                    .contentShape(Rectangle())
                                    .onTapGesture { editingExam = exam }
                            }
                        }
                        .padding(.horizontal)
                    }
                }
                .padding(.top, 8)
                .padding(.bottom, 24)
            }
            .navigationTitle("期末考看板")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { isCreatingExam = true }) {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(item: $editingExam) { exam in
                ExamEditModal(existingExam: exam) { _ in }
            }
            .sheet(isPresented: $isCreatingExam) {
                ExamEditModal { _ in }
            }
        }
    }

    private func examCard(for exam: ExamItem) -> some View {
        let isOngoing = exam.isOngoing()
        let isFinished = exam.isFinished()
        let days = exam.remainingDays()

        return VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(exam.title)
                    .font(.system(size: 16, weight: .bold))
                Spacer()

                // D-Day 胶囊
                if isOngoing {
                    Text("🔴 正在考试")
                        .font(.system(size: 12, weight: .bold))
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Color.red)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                } else if isFinished {
                    Text("已结束")
                        .font(.system(size: 12))
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Color.secondary.opacity(0.15))
                        .foregroundColor(.secondary)
                        .cornerRadius(8)
                } else {
                    Text(days == 0 ? "今天开考" : "还有 \(days) 天")
                        .font(.system(size: 12, weight: .bold))
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(days <= 1 ? Color.orange : Color.amiyaPrimary)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }
            }

            HStack(spacing: 12) {
                Label(exam.formattedDateStr(), systemImage: "calendar")
                Label(exam.formattedTimeRangeStr(), systemImage: "clock")
            }
            .font(.system(size: 13))
            .foregroundColor(.secondary)

            HStack(spacing: 16) {
                if !exam.location.isEmpty {
                    Label(exam.location, systemImage: "mappin.and.ellipse")
                }
                if !exam.seatNumber.isEmpty {
                    Label("座位: \(exam.seatNumber)", systemImage: "chair.lounge")
                }
                Text("[\(exam.examType)]")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(Color.amiyaPrimary)
            }
            .font(.system(size: 12))
            .foregroundColor(.secondary)

            if !exam.note.isEmpty {
                Text("📌 \(exam.note)")
                    .font(.system(size: 12))
                    .foregroundColor(.secondary)
            }
        }
        .padding()
        .amiyaCardStyle()
    }
}
