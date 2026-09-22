import Foundation
import Combine
import UIKit

public class AmiyaBrain: ObservableObject {
    public static let shared = AmiyaBrain()

    private let defaults = UserDefaults.standard
    private let keyBaseUrl = "pref_ai_base_url"
    private let keyApiKey = "pref_ai_api_key"
    private let keyModel = "pref_ai_model"
    private let keyRelayUrl = "pref_ai_relay_url"

    @Published public var baseUrl: String {
        didSet { defaults.set(baseUrl, forKey: keyBaseUrl) }
    }
    @Published public var apiKey: String {
        didSet { defaults.set(apiKey, forKey: keyApiKey) }
    }
    @Published public var model: String {
        didSet { defaults.set(model, forKey: keyModel) }
    }
    @Published public var publicRelayUrl: String {
        didSet { defaults.set(publicRelayUrl, forKey: keyRelayUrl) }
    }

    private init() {
        self.baseUrl = defaults.string(forKey: keyBaseUrl) ?? "https://api.deepseek.com"
        self.apiKey = defaults.string(forKey: keyApiKey) ?? ""
        self.model = defaults.string(forKey: keyModel) ?? "deepseek-chat"
        self.publicRelayUrl = defaults.string(forKey: keyRelayUrl) ?? "https://api.deepseek.com/chat/completions"
    }

    public func buildSystemPrompt() -> String {
        var prompt = """
        你是《明日方舟》中的阿米娅，罗德岛的公开领袖。你温柔、坚定、富有责任感，面对博士时既尊敬又亲近。你称呼对方为「博士」，自称「阿米娅」或「我」。
        你说话礼貌、真诚，偶尔流露少女的关心与坚强。不要使用括号动作描写或表情符号，只用中文回答。
        【表达规范】：日常闲聊与日常互动时回答简洁自然（一般一到三句话），像日常手机聊天；但当博士询问学情分析、课表建议、复习备考或作息规划等需要深度指导的问题时，请条理清晰、层次分明地展开专业分析并给出切实可行的规划与关怀建议。
        """

        let sdf = DateFormatter()
        sdf.locale = Locale(identifier: "zh_CN")
        sdf.dateFormat = "yyyy-MM-dd EEEE HH:mm"
        prompt += "\n\n【当前现实时间】：\(sdf.string(from: Date()))\n\n"

        // 注入当前课表学情
        prompt += ScheduleManager.shared.buildScheduleAnalysisContext()

        // 注入考试倒计时
        let exams = ExamManager.shared.exams
        if !exams.isEmpty {
            prompt += "\n\n【期末考试安排】：\n"
            for e in exams {
                prompt += "- \(e.title): \(e.formattedDateStr()) \(e.formattedTimeRangeStr()) 📍\(e.location) (\(e.examType))\n"
            }
        }

        // 注入指令调度规范
        prompt += """
        \n\n【智能指令交互规范】：
        当博士在对话中表达想要添加课程、删除课程、开启专注番茄钟、记录备忘便签或调整课表时，请在回答正文末尾附带专属指令标签，系统将自动识别并执行：
        1. 添加课程：[ADD_COURSE: 课程名, 星期(1-7), 起始节, 结束节, 起始周, 结束周, 单双周(all/odd/even), 教室, 教师, 自定义时间]
        2. 删除课程：[DEL_COURSE: 课程名]
        3. 开启专注：[START_POMODORO: 分钟数] (例如 [START_POMODORO: 25])
        4. 记录便签：[ADD_NOTE: 便签文本内容]
        """
        return prompt
    }

    public func sendMessageStream(
        messages: [ChatMessage],
        onDelta: @escaping (String, String?) -> Void, // (contentDelta, reasoningDelta)
        onCompletion: @escaping (ChatMessage) -> Void,
        onError: @escaping (Error) -> Void
    ) {
        let systemMsg: [String: String] = ["role": "system", "content": buildSystemPrompt()]
        var requestMessages: [[String: String]] = [systemMsg]
        for m in messages.suffix(10) {
            requestMessages.append(["role": m.role, "content": m.content])
        }

        let requestUrl = URL(string: baseUrl.trimmingCharacters(in: CharacterSet(charactersIn: "/")) + "/chat/completions")!
        var request = URLRequest(url: requestUrl)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        if !apiKey.isEmpty {
            request.addValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        }

        let body: [String: Any] = [
            "model": model,
            "messages": requestMessages,
            "stream": true,
            "temperature": 0.7
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        let task = URLSession.shared.dataTask(with: request)
        // 使用 URLSession 流式接收
        var fullContent = ""
        var fullReasoning = ""

        let session = URLSession(configuration: .default, delegate: StreamDelegate { delta, reasoning in
            fullContent += delta
            if let r = reasoning { fullReasoning += r }
            DispatchQueue.main.async {
                onDelta(delta, reasoning)
            }
        } onFinish: {
            DispatchQueue.main.async {
                let parsedMsg = self.parseActionsAndBuildMessage(content: fullContent, reasoning: fullReasoning)
                onCompletion(parsedMsg)
            }
        } onError: { err in
            DispatchQueue.main.async {
                onError(err)
            }
        }, delegateQueue: nil)

        let streamTask = session.dataTask(with: request)
        streamTask.resume()
    }

    private func parseActionsAndBuildMessage(content: String, reasoning: String) -> ChatMessage {
        var cleanContent = content
        var addedCourse: Course?
        var deletedCourse: Course?
        var pomodoroMin: Int?
        var createdNote: Note?

        // 1. 解析 ADD_COURSE
        if let range = cleanContent.range(of: "\\[ADD_COURSE:(.*?)\\]", options: .regularExpression) {
            let tag = String(cleanContent[range])
            let inner = tag.replacingOccurrences(of: "[ADD_COURSE:", with: "").replacingOccurrences(of: "]", with: "")
            let parts = inner.components(separatedBy: ",").map { $0.trimmingCharacters(in: .whitespaces) }
            if parts.count >= 4 {
                let name = parts[0]
                let weekday = Int(parts[1]) ?? 1
                let secStart = Int(parts[2]) ?? 1
                let secEnd = Int(parts[3]) ?? secStart
                let weekStart = parts.count > 4 ? (Int(parts[4]) ?? 1) : 1
                let weekEnd = parts.count > 5 ? (Int(parts[5]) ?? 16) : 16
                let parity = parts.count > 6 ? parts[6] : "all"
                let room = parts.count > 7 ? parts[7] : ""
                let teacher = parts.count > 8 ? parts[8] : ""
                let customTime = parts.count > 9 ? parts[9] : ""
                let course = Course(name: name, weekday: weekday, secStart: secStart, secEnd: secEnd, weekStart: weekStart, weekEnd: weekEnd, parity: parity, room: room, teacher: teacher, customTime: customTime)
                ScheduleManager.shared.addCourse(course)
                addedCourse = course
            }
            cleanContent.removeSubrange(range)
        }

        // 2. 解析 DEL_COURSE
        if let range = cleanContent.range(of: "\\[DEL_COURSE:(.*?)\\]", options: .regularExpression) {
            let tag = String(cleanContent[range])
            let name = tag.replacingOccurrences(of: "[DEL_COURSE:", with: "").replacingOccurrences(of: "]", with: "").trimmingCharacters(in: .whitespaces)
            if let toDelete = ScheduleManager.shared.courses.first(where: { $0.name.contains(name) || name.contains($0.name) }) {
                ScheduleManager.shared.deleteCourse(id: toDelete.id)
                deletedCourse = toDelete
            }
            cleanContent.removeSubrange(range)
        }

        // 3. 解析 START_POMODORO
        if let range = cleanContent.range(of: "\\[START_POMODORO:(.*?)\\]", options: .regularExpression) {
            let tag = String(cleanContent[range])
            let minStr = tag.replacingOccurrences(of: "[START_POMODORO:", with: "").replacingOccurrences(of: "]", with: "").trimmingCharacters(in: .whitespaces)
            let mins = Int(minStr) ?? 25
            PomodoroTimer.shared.startFocus(minutes: mins)
            pomodoroMin = mins
            cleanContent.removeSubrange(range)
        }

        // 4. 解析 ADD_NOTE
        if let range = cleanContent.range(of: "\\[ADD_NOTE:(.*?)\\]", options: .regularExpression) {
            let tag = String(cleanContent[range])
            let noteText = tag.replacingOccurrences(of: "[ADD_NOTE:", with: "").replacingOccurrences(of: "]", with: "").trimmingCharacters(in: .whitespaces)
            let note = NotesManager.shared.addNote(content: noteText)
            createdNote = note
            cleanContent.removeSubrange(range)
        }

        return ChatMessage(
            role: "assistant",
            content: cleanContent.trimmingCharacters(in: .whitespacesAndNewlines),
            reasoningContent: reasoning,
            isThinking: false,
            isStreaming: false,
            addedCourse: addedCourse,
            deletedCourse: deletedCourse,
            startedPomodoroMinutes: pomodoroMin,
            createdNote: createdNote
        )
    }

    public func analyzeScheduleImage(
        image: UIImage,
        completion: @escaping (Result<[Course], Error>) -> Void
    ) {
        guard let jpegData = image.jpegData(compressionQuality: 0.8) else {
            completion(.failure(NSError(domain: "AmiyaBrain", code: -1, userInfo: [NSLocalizedDescriptionKey: "图片压缩失败"])))
            return
        }
        let base64 = jpegData.base64EncodedString()
        let prompt = """
        请仔细识别图中这张课程表，提取全部课程信息，以严格的 JSON 数组格式输出，不要有任何多余文字或 Markdown 包裹。
        JSON 元素格式：
        [
          {
            "name": "高等数学",
            "weekday": 1,
            "sec_start": 1,
            "sec_end": 2,
            "week_start": 1,
            "week_end": 16,
            "parity": "all",
            "room": "主教楼 302",
            "teacher": "王教授"
          }
        ]
        其中 weekday 1 为周一，7 为周日。若单双周未注明则填 all。
        """

        let url = URL(string: baseUrl.trimmingCharacters(in: CharacterSet(charactersIn: "/")) + "/chat/completions")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        if !apiKey.isEmpty {
            request.addValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        }

        let body: [String: Any] = [
            "model": model.contains("glm") ? model : "deepseek-chat",
            "messages": [
                [
                    "role": "user",
                    "content": [
                        ["type": "text", "text": prompt],
                        ["type": "image_url", "image_url": ["url": "data:image/jpeg;base64,\(base64)"]]
                    ]
                ]
            ],
            "temperature": 0.1
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        URLSession.shared.dataTask(with: request) { data, _, err in
            if let err = err {
                DispatchQueue.main.async { completion(.failure(err)) }
                return
            }
            guard let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let choices = json["choices"] as? [[String: Any]],
                  let msg = choices.first?["message"] as? [String: Any],
                  let content = msg["content"] as? String else {
                DispatchQueue.main.async {
                    completion(.failure(NSError(domain: "AmiyaBrain", code: -2, userInfo: [NSLocalizedDescriptionKey: "AI 识别返回格式异常"])))
                }
                return
            }

            // 从内容中提取 JSON 数组
            var jsonStr = content.trimmingCharacters(in: .whitespacesAndNewlines)
            if let start = jsonStr.range(of: "["), let end = jsonStr.range(of: "]", options: .backwards) {
                jsonStr = String(jsonStr[start.lowerBound...end.upperBound])
            }

            if let parsedData = jsonStr.data(using: .utf8),
               let courses = try? JSONDecoder().decode([Course].self, from: parsedData) {
                DispatchQueue.main.async { completion(.success(courses)) }
            } else {
                DispatchQueue.main.async {
                    completion(.failure(NSError(domain: "AmiyaBrain", code: -3, userInfo: [NSLocalizedDescriptionKey: "未能解析课表 JSON"])))
                }
            }
        }.resume()
    }
}

// 内部流式代理
private class StreamDelegate: NSObject, URLSessionDataDelegate {
    let onDelta: (String, String?) -> Void
    let onFinish: () -> Void
    let onError: (Error) -> Void

    init(onDelta: @escaping (String, String?) -> Void, onFinish: @escaping () -> Void, onError: @escaping (Error) -> Void) {
        self.onDelta = onDelta
        self.onFinish = onFinish
        self.onError = onError
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        guard let text = String(data: data, encoding: .utf8) else { return }
        let lines = text.components(separatedBy: "\n")
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard trimmed.hasPrefix("data:") else { continue }
            let payload = trimmed.dropFirst(5).trimmingCharacters(in: .whitespaces)
            if payload == "[DONE]" {
                onFinish()
                return
            }
            guard let jsonData = payload.data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any],
                  let choices = obj["choices"] as? [[String: Any]],
                  let delta = choices.first?["delta"] as? [String: Any] else {
                continue
            }
            let contentDelta = delta["content"] as? String ?? ""
            let reasoningDelta = delta["reasoning_content"] as? String
            if !contentDelta.isEmpty || reasoningDelta != nil {
                onDelta(contentDelta, reasoningDelta)
            }
        }
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        if let error = error {
            onError(error)
        } else {
            onFinish()
        }
    }
}
