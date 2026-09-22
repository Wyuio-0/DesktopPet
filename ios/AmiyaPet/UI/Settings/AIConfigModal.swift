import SwiftUI

public struct AIConfigModal: View {
    @ObservedObject var brain = AmiyaBrain.shared
    @Environment(\.dismiss) var dismiss

    @State private var baseUrl: String = ""
    @State private var apiKey: String = ""
    @State private var model: String = ""
    @State private var testStatus: String?
    @State private var isTesting: Bool = false

    public init() {}

    public var body: some View {
        NavigationStack {
            Form {
                Section(header: Text("API 端点设定"), footer: Text("支持 DeepSeek、OpenAI、智谱清言等多模态大模型兼容接口。")) {
                    TextField("Base URL (如 https://api.deepseek.com)", text: $baseUrl)
                    SecureField("API Key (sk-...)", text: $apiKey)
                    TextField("Model (如 deepseek-chat, glm-4v)", text: $model)
                }

                Section(header: Text("预设快捷填入")) {
                    Button("填入 DeepSeek 官方端点") {
                        baseUrl = "https://api.deepseek.com"
                        model = "deepseek-chat"
                    }
                    Button("填入 DeepSeek-R1 (深度推理)") {
                        baseUrl = "https://api.deepseek.com"
                        model = "deepseek-reasoner"
                    }
                    Button("填入智谱 GLM-4V (多模态识图最佳)") {
                        baseUrl = "https://open.bigmodel.cn/api/paas/v4"
                        model = "glm-4v"
                    }
                }

                Section {
                    Button(action: testConnection) {
                        HStack {
                            if isTesting {
                                ProgressView()
                                    .padding(.trailing, 4)
                            }
                            Text("测试大模型链路连通性")
                        }
                    }
                    .disabled(isTesting || baseUrl.isEmpty)

                    if let status = testStatus {
                        Text(status)
                            .font(.system(size: 13))
                            .foregroundColor(status.contains("成功") ? .green : .red)
                    }
                }
            }
            .navigationTitle("AI 神经元设置")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("保存") {
                        brain.baseUrl = baseUrl
                        brain.apiKey = apiKey
                        brain.model = model
                        dismiss()
                    }
                }
            }
            .onAppear {
                baseUrl = brain.baseUrl
                apiKey = brain.apiKey
                model = brain.model
            }
        }
    }

    private func testConnection() {
        isTesting = true
        testStatus = "正在建立通信握手..."
        let testMsg = [ChatMessage(role: "user", content: "你好，请用五个字以内打个招呼。")]
        brain.sendMessageStream(messages: testMsg) { _, _ in
        } onCompletion: { reply in
            isTesting = false
            testStatus = "✅ 连通成功！阿米娅回答: \(reply.content)"
        } onError: { err in
            isTesting = false
            testStatus = "❌ 连接失败: \(err.localizedDescription)"
        }
    }
}
