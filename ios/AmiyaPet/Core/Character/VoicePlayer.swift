import Foundation
import AVFoundation
import Combine

public struct VoiceLine: Identifiable, Hashable {
    public let id: String
    public let title: String
    public let fileName: String
    public let subtitle: String

    public init(id: String, title: String, fileName: String, subtitle: String) {
        self.id = id
        self.title = title
        self.fileName = fileName
        self.subtitle = subtitle
    }
}

public class VoicePlayer: NSObject, ObservableObject, AVAudioPlayerDelegate {
    public static let shared = VoicePlayer()

    public static let VOICE_LINES: [VoiceLine] = [
        VoiceLine(id: "greet", title: "问候", fileName: "问候", subtitle: "早安，博士！今天也要精神饱满地努力哦！"),
        VoiceLine(id: "poke", title: "戳一下", fileName: "戳一下", subtitle: "哇？！博士，请、请不要突然戳我啦……"),
        VoiceLine(id: "talk1", title: "交谈 1", fileName: "交谈1", subtitle: "博士，还有很多事情在等着我们去完成呢，稍微休息一下就继续出发吧。"),
        VoiceLine(id: "talk2", title: "交谈 2", fileName: "交谈2", subtitle: "罗德岛的大家都在为了共同的理想而奋斗，阿米娅也会一直陪在博士身边。"),
        VoiceLine(id: "talk3", title: "交谈 3", fileName: "交谈3", subtitle: "无论遇到多大的困难，只要和博士在一起，我就充满了勇气。"),
        VoiceLine(id: "trust_touch", title: "信赖触摸", fileName: "信赖触摸", subtitle: "博士的手好温暖……有博士在身边，真的很让人安心。"),
        VoiceLine(id: "idle", title: "闲置", fileName: "闲置", subtitle: "博士？博士在想什么呢？要是累了的话，阿米娅给您泡一杯红茶吧。"),
        VoiceLine(id: "appoint_assistant", title: "任命助理", fileName: "任命助理", subtitle: "阿米娅会全力协助博士处理罗德岛的日常事务，请尽管交给我吧！"),
        VoiceLine(id: "mission_start", title: "行动开始", fileName: "行动开始", subtitle: "各干员就位，罗德岛行动准备完成，全员出发！"),
        VoiceLine(id: "mission_success", title: "完成高难行动", fileName: "完成高难行动", subtitle: "太好了！博士的指挥一如既往地令人安心！")
    ]

    @Published public var currentSubtitle: String?
    @Published public var isPlaying: Bool = false

    private var audioPlayer: AVAudioPlayer?

    private override init() {
        super.init()
        setupAudioSession()
    }

    private func setupAudioSession() {
        do {
            try AVAudioSession.sharedInstance().setCategory(.ambient, mode: .default, options: [.mixWithOthers])
            try AVAudioSession.sharedInstance().setActive(true)
        } catch {
            print("Failed to set audio session category: \(error)")
        }
    }

    public func playRandomInteractionVoice() {
        let interactionLines = VoicePlayer.VOICE_LINES.filter { ["poke", "talk1", "talk2", "talk3", "trust_touch", "idle"].contains($0.id) }
        guard let line = interactionLines.randomElement() else { return }
        play(voiceLine: line)
    }

    public func play(voiceLine: VoiceLine) {
        stop()

        guard let path = Bundle.main.path(forResource: voiceLine.fileName, ofType: "wav") else {
            // 如果在 Bundle 内部未找到对应 wav，仅展示字幕并记录日志
            print("Voice file not found: \(voiceLine.fileName).wav")
            currentSubtitle = voiceLine.subtitle
            isPlaying = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 3.5) { [weak self] in
                if self?.currentSubtitle == voiceLine.subtitle {
                    self?.currentSubtitle = nil
                    self?.isPlaying = false
                }
            }
            return
        }

        let url = URL(fileURLWithPath: path)
        do {
            audioPlayer = try AVAudioPlayer(contentsOf: url)
            audioPlayer?.delegate = self
            audioPlayer?.prepareToPlay()
            audioPlayer?.play()
            currentSubtitle = voiceLine.subtitle
            isPlaying = true
        } catch {
            print("AVAudioPlayer error: \(error)")
            currentSubtitle = voiceLine.subtitle
            isPlaying = false
        }
    }

    public func stop() {
        audioPlayer?.stop()
        audioPlayer = nil
        isPlaying = false
    }

    public func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        isPlaying = false
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [weak self] in
            self?.currentSubtitle = nil
        }
    }
}
