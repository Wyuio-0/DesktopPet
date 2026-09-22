import SwiftUI

public struct ChatView: View {
    @ObservedObject var brain = AmiyaBrain.shared
    @State private var messages: [ChatMessage] = []
    @State private var inputText: String = ""
    @State private var isSending: Bool = false
    @State private var streamContent: String = ""
    @State private var streamReasoning: String = ""

    var onSwitchTab: ((Int) -> Void)?

    private let quickPrompts = [
        "总结一下我本周的课表",
        "开启 25 分钟番茄钟专注",
        "记一下：明天下午组会汇报",
        "阿米娅，帮我做个学情分析",
        "周四下午第 7-8 节加一门《线性代数》在教二 101"
    ]

    public init(onSwitchTab: ((Int) -> Void)? = nil) {
        self.onSwitchTab = onSwitchTab
    }

    public var body: some View {
        VStack(spacing: 0) {
            // 顶栏互动桌宠
            AmiyaPetDockView()
                .padding(.horizontal)

            Divider()

            // 聊天消息流
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 12) {
                        if messages.isEmpty {
                            welcomeCard
                        }

                        ForEach(messages) { msg in
                            messageRow(for: msg)
                        }

                        if isSending {
                            streamingRow
                        }
                    }
                    .padding()
                }
                .onChange(of: messages.count) { _ in
                    if let last = messages.last {
                        withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                    }
                }
                .onChange(of: streamContent) { _ in
                    withAnimation { proxy.scrollTo("streaming_row", anchor: .bottom) }
                }
            }

            // 快捷指令胶囊
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(quickPrompts, id: \.self) { prompt in
                        Button(action: {
                            inputText = prompt
                            sendMessage()
                        }) {
                            Text(prompt)
                                .font(.system(size: 12))
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(Color.amiyaPrimary.opacity(0.1))
                                .foregroundColor(Color.amiyaPrimary)
                                .cornerRadius(14)
                        }
                    }
                }
                .padding(.horizontal)
                .padding(.vertical, 6)
            }

            Divider()

            // 底部输入框
            HStack(spacing: 10) {
                TextField("与阿米娅对话、输入课表指令...", text: $inputText)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .submitLabel(.send)
                    .onSubmit { sendMessage() }

                Button(action: sendMessage) {
                    Image(systemName: isSending ? "ellipsis.circle" : "arrow.up.circle.fill")
                        .font(.system(size: 28))
                        .foregroundColor(inputText.trimmingCharacters(in: .whitespaces).isEmpty ? .secondary : Color.amiyaPrimary)
                }
                .disabled(inputText.trimmingCharacters(in: .whitespaces).isEmpty || isSending)
            }
            .padding(.horizontal)
            .padding(.vertical, 8)
            .background(Color.amiyaCardBg)
        }
        .onAppear {
            if messages.isEmpty {
                messages.append(ChatMessage(
                    role: "assistant",
                    content: "博士，您好！我是罗德岛公开领袖阿米娅。无论是查询课表、开启专注，还是备忘记录，我都会全力协助您！"
                ))
            }
        }
    }

    private var welcomeCard: some View {
        VStack(spacing: 8) {
            Image(systemName: "sparkles")
                .font(.system(size: 24))
                .foregroundColor(Color.amiyaPrimary)
            Text("罗德岛指挥终端已连接")
                .font(.system(size: 15, weight: .bold))
            Text("您可以随时对我说：“周三加一节线代”、“开启25分钟专注”或“这周课多吗”。")
                .font(.system(size: 13))
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(Color.amiyaPrimary.opacity(0.06))
        .cornerRadius(12)
    }

    private func messageRow(for msg: ChatMessage) -> some View {
        HStack(alignment: .top, spacing: 8) {
            if msg.isUser {
                Spacer()
                Text(msg.content)
                    .font(.system(size: 15))
                    .padding(12)
                    .background(Color.amiyaPrimary)
                    .foregroundColor(.white)
                    .cornerRadius(16, corners: [.topLeft, .topRight, .bottomLeft])
            } else {
                Image("avatar_amiya")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 34, height: 34)
                    .clipShape(Circle())
                    .shadow(radius: 2)

                VStack(alignment: .leading, spacing: 6) {
                    ThinkingDisclosureView(reasoning: msg.reasoningContent)

                    if !msg.content.isEmpty {
                        Text(msg.content)
                            .font(.system(size: 15))
                            .padding(12)
                            .background(Color.amiyaCardBg)
                            .foregroundColor(.primary)
                            .cornerRadius(16, corners: [.topLeft, .topRight, .bottomRight])
                            .shadow(color: Color.black.opacity(0.04), radius: 4, x: 0, y: 2)
                    }

                    // 战术交互卡片
                    if let course = msg.addedCourse {
                        CourseAddedCardView(course: course) {
                            onSwitchTab?(1) // 切换到课表 Tab
                        }
                    }
                    if let mins = msg.startedPomodoroMinutes {
                        PomodoroStartedCardView(minutes: mins) {
                            onSwitchTab?(2) // 切换到专注 Tab
                        }
                    }
                    if let note = msg.createdNote {
                        NoteCreatedCardView(note: note) {
                            onSwitchTab?(3) // 切换到便签 Tab
                        }
                    }
                }
                Spacer()
            }
        }
        .id(msg.id)
    }

    private var streamingRow: some View {
        HStack(alignment: .top, spacing: 8) {
            Image("avatar_amiya")
                .resizable()
                .scaledToFit()
                .frame(width: 34, height: 34)
                .clipShape(Circle())

            VStack(alignment: .leading, spacing: 6) {
                if !streamReasoning.isEmpty {
                    ThinkingDisclosureView(reasoning: streamReasoning)
                }
                HStack(spacing: 4) {
                    Text(streamContent.isEmpty ? "阿米娅正在组织语言..." : streamContent)
                        .font(.system(size: 15))
                    if streamContent.isEmpty {
                        ProgressView()
                            .scaleEffect(0.8)
                    }
                }
                .padding(12)
                .background(Color.amiyaCardBg)
                .cornerRadius(16)
            }
            Spacer()
        }
        .id("streaming_row")
    }

    private func sendMessage() {
        let text = inputText.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty, !isSending else { return }

        inputText = ""
        let userMsg = ChatMessage(role: "user", content: text)
        messages.append(userMsg)

        isSending = true
        streamContent = ""
        streamReasoning = ""

        brain.sendMessageStream(messages: messages) { delta, reasoning in
            streamContent += delta
            if let r = reasoning { streamReasoning += r }
        } onCompletion: { replyMsg in
            isSending = false
            messages.append(replyMsg)
            streamContent = ""
            streamReasoning = ""
        } onError: { error in
            isSending = false
            let errReply = ChatMessage(
                role: "assistant",
                content: "博士，通信链路暂时受阻：\(error.localizedDescription)。请检查「设置」中的 API 线路配置哦。"
            )
            messages.append(errReply)
            streamContent = ""
            streamReasoning = ""
        }
    }
}

// 辅助角圆角
public struct RoundedCorner: Shape {
    var radius: CGFloat = .infinity
    var corners: UIRectCorner = .allCorners

    public func path(in rect: CGRect) -> Path {
        let path = UIBezierPath(roundedRect: rect, byRoundingCorners: corners, cornerRadii: CGSize(width: radius, height: radius))
        return Path(path.cgPath)
    }
}

public extension View {
    func cornerRadius(_ radius: CGFloat, corners: UIRectCorner) -> some View {
        clipShape(RoundedCorner(radius: radius, corners: corners))
    }
}
