import SwiftUI

public struct ThinkingDisclosureView: View {
    let reasoning: String
    @State private var isExpanded: Bool = false

    public var body: some View {
        if !reasoning.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            VStack(alignment: .leading, spacing: 6) {
                Button(action: { withAnimation { isExpanded.toggle() } }) {
                    HStack(spacing: 6) {
                        Image(systemName: "brain.head.profile")
                            .font(.system(size: 12))
                            .foregroundColor(.secondary)
                        Text("阿米娅深度思考过程")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(.secondary)
                        Spacer()
                        Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                            .font(.system(size: 10))
                            .foregroundColor(.secondary)
                    }
                }
                .buttonStyle(PlainButtonStyle())

                if isExpanded {
                    Text(reasoning)
                        .font(.system(size: 12))
                        .foregroundColor(.secondary)
                        .padding(8)
                        .background(Color.secondary.opacity(0.08))
                        .cornerRadius(8)
                }
            }
            .padding(10)
            .background(Color.secondary.opacity(0.05))
            .cornerRadius(10)
        }
    }
}

public struct CourseAddedCardView: View {
    let course: Course
    var onGoToSchedule: (() -> Void)?

    public var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "calendar.badge.plus")
                    .foregroundColor(.green)
                Text("PRTS 战术课表已录入")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(.green)
                Spacer()
            }
            Text("《\(course.name)》")
                .font(.system(size: 15, weight: .bold))
            HStack(spacing: 12) {
                Label(course.formattedSectionDisplay(), systemImage: "clock")
                Label(course.room.isEmpty ? "未指定教室" : course.room, systemImage: "mappin.and.ellipse")
            }
            .font(.system(size: 12))
            .foregroundColor(.secondary)

            Button(action: { onGoToSchedule?() }) {
                HStack {
                    Text("📅 前往课表查看 ➔")
                        .font(.system(size: 12, weight: .semibold))
                    Spacer()
                }
                .foregroundColor(Color.amiyaPrimary)
            }
            .padding(.top, 2)
        }
        .padding(12)
        .background(Color.green.opacity(0.08))
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.green.opacity(0.3), lineWidth: 1))
    }
}

public struct PomodoroStartedCardView: View {
    let minutes: Int
    var onGoToPomodoro: (() -> Void)?

    public var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "timer")
                    .foregroundColor(Color.amiyaAmber)
                Text("战术专注已启动")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(Color.amiyaAmber)
                Spacer()
            }
            Text("阿米娅已为您开启 \(minutes) 分钟专注伴学模式")
                .font(.system(size: 14))

            Button(action: { onGoToPomodoro?() }) {
                HStack {
                    Text("🍅 跳转专注看板 ➔")
                        .font(.system(size: 12, weight: .semibold))
                    Spacer()
                }
                .foregroundColor(Color.amiyaAmber)
            }
            .padding(.top, 2)
        }
        .padding(12)
        .background(Color.amiyaAmber.opacity(0.08))
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.amiyaAmber.opacity(0.3), lineWidth: 1))
    }
}

public struct NoteCreatedCardView: View {
    let note: Note
    var onGoToNotes: (() -> Void)?

    public var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "note.text")
                    .foregroundColor(Color.amiyaPrimary)
                Text("战术备忘已归档")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(Color.amiyaPrimary)
                Spacer()
            }
            Text("「\(note.title)」")
                .font(.system(size: 14, weight: .semibold))
            Text(note.content)
                .font(.system(size: 12))
                .foregroundColor(.secondary)
                .lineLimit(2)

            Button(action: { onGoToNotes?() }) {
                HStack {
                    Text("📝 查看便签本 ➔")
                        .font(.system(size: 12, weight: .semibold))
                    Spacer()
                }
                .foregroundColor(Color.amiyaPrimary)
            }
            .padding(.top, 2)
        }
        .padding(12)
        .background(Color.amiyaPrimary.opacity(0.08))
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.amiyaPrimary.opacity(0.3), lineWidth: 1))
    }
}
