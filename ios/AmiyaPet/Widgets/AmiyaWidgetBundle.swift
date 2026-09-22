import WidgetKit
import SwiftUI

public struct AmiyaWidgetBundle: WidgetBundle {
    public var body: some Widget {
        AmiyaScheduleWidget()
        AmiyaCourseLiveActivity()
        AmiyaPomodoroLiveActivity()
    }
}
