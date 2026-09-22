import WidgetKit
import SwiftUI

@main
public struct AmiyaWidgetBundle: WidgetBundle {
    public init() {}

    public var body: some Widget {
        AmiyaScheduleWidget()
        AmiyaCourseLiveActivity()
        AmiyaPomodoroLiveActivity()
    }
}
