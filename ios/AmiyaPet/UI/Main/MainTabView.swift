import SwiftUI

public struct MainTabView: View {
    @State private var selectedTab: Int = 1 // 默认进入课表 Tab，与移动端习惯保持一致

    public init() {}

    public var body: some View {
        TabView(selection: $selectedTab) {
            ChatView { targetTab in
                selectedTab = targetTab
            }
            .tabItem {
                Label("指挥室", systemImage: "bubble.left.and.bubble.right.fill")
            }
            .tag(0)

            ScheduleView { course in
                selectedTab = 0 // 切换到指挥室询问阿米娅
            }
            .tabItem {
                Label("课表", systemImage: "calendar")
            }
            .tag(1)

            PomodoroView()
                .tabItem {
                    Label("专注", systemImage: "timer")
                }
                .tag(2)

            NotesView()
                .tabItem {
                    Label("备忘", systemImage: "note.text")
                }
                .tag(3)

            ExamScheduleView()
                .tabItem {
                    Label("期末考", systemImage: "target")
                }
                .tag(4)

            SettingsView()
                .tabItem {
                    Label("设置", systemImage: "gearshape.fill")
                }
                .tag(5)
        }
        .accentColor(Color.amiyaPrimary)
    }
}
