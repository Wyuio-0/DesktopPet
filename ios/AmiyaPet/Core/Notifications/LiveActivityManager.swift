import Foundation
import ActivityKit
import Combine

// 课程实时活动属性
public struct AmiyaCourseAttributes: ActivityAttributes {
    public struct ContentState: Codable, Hashable {
        public var courseName: String
        public var sectionDisplay: String
        public var room: String
        public var teacher: String
        public var elapsedMinutes: Int
        public var remainingMinutes: Int
        public var progress: Double
        public var nextCoursePreview: String

        public init(
            courseName: String,
            sectionDisplay: String,
            room: String,
            teacher: String,
            elapsedMinutes: Int,
            remainingMinutes: Int,
            progress: Double,
            nextCoursePreview: String
        ) {
            self.courseName = courseName
            self.sectionDisplay = sectionDisplay
            self.room = room
            self.teacher = teacher
            self.elapsedMinutes = elapsedMinutes
            self.remainingMinutes = remainingMinutes
            self.progress = progress
            self.nextCoursePreview = nextCoursePreview
        }
    }

    public var courseId: String
    public init(courseId: String) {
        self.courseId = courseId
    }
}

// 专注实时活动属性
public struct AmiyaPomodoroAttributes: ActivityAttributes {
    public struct ContentState: Codable, Hashable {
        public var modeTitle: String
        public var remainingSeconds: Int
        public var totalSeconds: Int
        public var isPaused: Bool

        public init(modeTitle: String, remainingSeconds: Int, totalSeconds: Int, isPaused: Bool) {
            self.modeTitle = modeTitle
            self.remainingSeconds = remainingSeconds
            self.totalSeconds = totalSeconds
            self.isPaused = isPaused
        }
    }

    public var sessionName: String
    public init(sessionName: String = "阿米娅战术专注") {
        self.sessionName = sessionName
    }
}

public class LiveActivityManager {
    public static let shared = LiveActivityManager()

    private var courseActivity: Activity<AmiyaCourseAttributes>?
    private var pomodoroActivity: Activity<AmiyaPomodoroAttributes>?

    private init() {}

    public func startCourseActivity(
        course: Course,
        elapsedMinutes: Int,
        remainingMinutes: Int,
        progress: Double,
        nextCoursePreview: String
    ) {
        guard ActivityAuthorizationInfo().areActivitiesEnabled else { return }
        endCourseActivity()

        let attributes = AmiyaCourseAttributes(courseId: course.id)
        let state = AmiyaCourseAttributes.ContentState(
            courseName: course.name,
            sectionDisplay: course.formattedSectionDisplay(),
            room: course.room,
            teacher: course.teacher,
            elapsedMinutes: elapsedMinutes,
            remainingMinutes: remainingMinutes,
            progress: progress,
            nextCoursePreview: nextCoursePreview
        )

        do {
            let activity = try Activity.request(
                attributes: attributes,
                content: .init(state: state, staleDate: nil)
            )
            self.courseActivity = activity
        } catch {
            print("Failed to start Course Live Activity: \(error)")
        }
    }

    public func updateCourseActivity(
        elapsedMinutes: Int,
        remainingMinutes: Int,
        progress: Double
    ) {
        guard let activity = courseActivity else { return }
        var state = activity.content.state
        state.elapsedMinutes = elapsedMinutes
        state.remainingMinutes = remainingMinutes
        state.progress = progress

        Task {
            await activity.update(.init(state: state, staleDate: nil))
        }
    }

    public func endCourseActivity() {
        guard let activity = courseActivity else { return }
        Task {
            await activity.end(nil, dismissalPolicy: .immediate)
            self.courseActivity = nil
        }
    }

    public func startPomodoroActivity(mode: PomodoroMode, totalSeconds: Int, remainingSeconds: Int) {
        guard ActivityAuthorizationInfo().areActivitiesEnabled else { return }
        endPomodoroActivity()

        let attributes = AmiyaPomodoroAttributes()
        let state = AmiyaPomodoroAttributes.ContentState(
            modeTitle: mode.title,
            remainingSeconds: remainingSeconds,
            totalSeconds: totalSeconds,
            isPaused: false
        )

        do {
            let activity = try Activity.request(
                attributes: attributes,
                content: .init(state: state, staleDate: nil)
            )
            self.pomodoroActivity = activity
        } catch {
            print("Failed to start Pomodoro Live Activity: \(error)")
        }
    }

    public func updatePomodoroActivity(remainingSeconds: Int, isPaused: Bool) {
        guard let activity = pomodoroActivity else { return }
        var state = activity.content.state
        state.remainingSeconds = remainingSeconds
        state.isPaused = isPaused

        Task {
            await activity.update(.init(state: state, staleDate: nil))
        }
    }

    public func endPomodoroActivity() {
        guard let activity = pomodoroActivity else { return }
        Task {
            await activity.end(nil, dismissalPolicy: .immediate)
            self.pomodoroActivity = nil
        }
    }
}
