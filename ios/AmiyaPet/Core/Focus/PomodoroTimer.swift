import Foundation
import Combine
import AudioToolbox

public enum PomodoroState: String, Codable {
    case idle, running, paused, completed
}

public enum PomodoroMode: String, Codable {
    case work, shortBreak

    public var defaultMinutes: Int {
        switch self {
        case .work: return 25
        case .shortBreak: return 5
        }
    }

    public var title: String {
        switch self {
        case .work: return "专注工作"
        case .shortBreak: return "短暂休息"
        }
    }
}

public class PomodoroTimer: ObservableObject {
    public static let shared = PomodoroTimer()

    @Published public var state: PomodoroState = .idle
    @Published public var mode: PomodoroMode = .work
    @Published public var remainingSeconds: Int = 25 * 60
    @Published public var totalSeconds: Int = 25 * 60

    public var onTimerFinished: ((PomodoroMode) -> Void)?

    private var targetEndTime: Date?
    private var timer: Timer?

    public var progress: Double {
        if totalSeconds > 0 {
            return Double(totalSeconds - remainingSeconds) / Double(totalSeconds)
        }
        return 0.0
    }

    public var formattedTime: String {
        let m = remainingSeconds / 60
        let s = remainingSeconds % 60
        return String(format: "%02d:%02d", m, s)
    }

    private init() {}

    public func startFocus(minutes: Int = 25) {
        mode = .work
        totalSeconds = minutes * 60
        remainingSeconds = totalSeconds
        startCountdown()
    }

    public func startBreak(minutes: Int = 5) {
        mode = .shortBreak
        totalSeconds = minutes * 60
        remainingSeconds = totalSeconds
        startCountdown()
    }

    private func startCountdown() {
        state = .running
        targetEndTime = Date().addingTimeInterval(TimeInterval(remainingSeconds))
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.tick()
        }
        RunLoop.main.add(timer!, forMode: .common)
        LiveActivityManager.shared.startPomodoroActivity(mode: mode, totalSeconds: totalSeconds, remainingSeconds: remainingSeconds)
    }

    public func pause() {
        guard state == .running else { return }
        state = .paused
        timer?.invalidate()
        timer = nil
        LiveActivityManager.shared.updatePomodoroActivity(remainingSeconds: remainingSeconds, isPaused: true)
    }

    public func resume() {
        guard state == .paused else { return }
        startCountdown()
    }

    public func reset() {
        timer?.invalidate()
        timer = nil
        targetEndTime = nil
        state = .idle
        remainingSeconds = totalSeconds
        LiveActivityManager.shared.endPomodoroActivity()
    }

    private func tick() {
        guard state == .running, let target = targetEndTime else { return }
        let diff = Int(ceil(target.timeIntervalSinceNow))
        if diff > 0 {
            remainingSeconds = diff
            LiveActivityManager.shared.updatePomodoroActivity(remainingSeconds: remainingSeconds, isPaused: false)
        } else {
            complete()
        }
    }

    private func complete() {
        timer?.invalidate()
        timer = nil
        state = .completed
        remainingSeconds = 0
        AudioServicesPlaySystemSound(1005) // 系统提示音
        LiveActivityManager.shared.endPomodoroActivity()
        onTimerFinished?(mode)
        NotificationCenter.default.post(name: NSNotification.Name("AmiyaPomodoroCompleted"), object: mode)
    }

    public func refreshTime() {
        guard state == .running, let target = targetEndTime else { return }
        let diff = Int(ceil(target.timeIntervalSinceNow))
        if diff > 0 {
            remainingSeconds = diff
        } else {
            complete()
        }
    }
}
