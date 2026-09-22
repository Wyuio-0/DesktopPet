import ActivityKit
import WidgetKit
import SwiftUI

public struct AmiyaCourseLiveActivity: Widget {
    public var body: some WidgetConfiguration {
        ActivityConfiguration(for: AmiyaCourseAttributes.self) { context in
            // 锁屏与通知中心卡片视图
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Image("avatar_amiya")
                        .resizable()
                        .scaledToFit()
                        .frame(width: 28, height: 28)
                        .clipShape(Circle())
                    Text("🔴 正在上课: 《\(context.state.courseName)》 (\(context.state.sectionDisplay))")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(.primary)
                    Spacer()
                    Text("剩余 \(context.state.remainingMinutes) 分钟")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(Color.amiyaPrimary)
                }

                // 进度条
                ProgressView(value: context.state.progress)
                    .tint(Color.amiyaPrimary)

                HStack {
                    Text("📍 教室：\(context.state.room)")
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                    Spacer()
                    Text("已上 \(context.state.elapsedMinutes) 分钟 · \(Int(context.state.progress * 100))%")
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                }

                if !context.state.nextCoursePreview.isEmpty {
                    Text(context.state.nextCoursePreview)
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }
            }
            .padding(14)
            .background(Color.amiyaCardBg)
        } dynamicIsland: { context in
            DynamicIsland {
                // 灵动岛长按展开状态
                DynamicIslandExpandedRegion(.leading) {
                    HStack(spacing: 6) {
                        Image("avatar_amiya")
                            .resizable()
                            .scaledToFit()
                            .frame(width: 28, height: 28)
                            .clipShape(Circle())
                        VStack(alignment: .leading, spacing: 2) {
                            Text(context.state.courseName)
                                .font(.system(size: 14, weight: .bold))
                            Text(context.state.sectionDisplay)
                                .font(.system(size: 11))
                                .foregroundColor(.secondary)
                        }
                    }
                }
                DynamicIslandExpandedRegion(.trailing) {
                    VStack(alignment: .trailing, spacing: 2) {
                        Text("还剩 \(context.state.remainingMinutes) 分钟")
                            .font(.system(size: 13, weight: .bold))
                            .foregroundColor(Color.amiyaPrimary)
                        Text("📍 \(context.state.room)")
                            .font(.system(size: 11))
                            .foregroundColor(.secondary)
                    }
                }
                DynamicIslandExpandedRegion(.bottom) {
                    VStack(spacing: 6) {
                        ProgressView(value: context.state.progress)
                            .tint(Color.amiyaPrimary)
                        if !context.state.nextCoursePreview.isEmpty {
                            Text(context.state.nextCoursePreview)
                                .font(.system(size: 11))
                                .foregroundColor(.secondary)
                        }
                    }
                }
            } compactLeading: {
                HStack(spacing: 4) {
                    Image("avatar_amiya")
                        .resizable()
                        .scaledToFit()
                        .frame(width: 16, height: 16)
                        .clipShape(Circle())
                    Text(context.state.courseName)
                        .font(.system(size: 11, weight: .bold))
                }
            } compactTrailing: {
                Text("\(context.state.remainingMinutes)m")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(Color.amiyaPrimary)
            } minimal: {
                Image("avatar_amiya")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 14, height: 14)
                    .clipShape(Circle())
            }
        }
    }
}

public struct AmiyaPomodoroLiveActivity: Widget {
    public var body: some WidgetConfiguration {
        ActivityConfiguration(for: AmiyaPomodoroAttributes.self) { context in
            // 锁屏卡片
            HStack(spacing: 12) {
                Image("avatar_amiya_focus")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 44, height: 44)

                VStack(alignment: .leading, spacing: 4) {
                    Text(context.state.modeTitle)
                        .font(.system(size: 15, weight: .bold))
                    Text(context.state.isPaused ? "已暂停" : "阿米娅正与您共同专注...")
                        .font(.system(size: 12))
                        .foregroundColor(.secondary)
                }

                Spacer()

                let m = context.state.remainingSeconds / 60
                let s = context.state.remainingSeconds % 60
                Text(String(format: "%02d:%02d", m, s))
                    .font(.system(size: 24, weight: .bold, design: .rounded))
                    .foregroundColor(Color.amiyaAmber)
            }
            .padding(14)
            .background(Color.amiyaCardBg)
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    HStack {
                        Image("avatar_amiya_focus")
                            .resizable()
                            .scaledToFit()
                            .frame(width: 24, height: 24)
                        Text(context.state.modeTitle)
                            .font(.system(size: 13, weight: .bold))
                    }
                }
                DynamicIslandExpandedRegion(.trailing) {
                    let m = context.state.remainingSeconds / 60
                    let s = context.state.remainingSeconds % 60
                    Text(String(format: "%02d:%02d", m, s))
                        .font(.system(size: 16, weight: .bold, design: .rounded))
                        .foregroundColor(Color.amiyaAmber)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    Text(context.state.isPaused ? "专注已暂停" : "保持专注，心无旁骛")
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                }
            } compactLeading: {
                Image("avatar_amiya_focus")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 16, height: 16)
            } compactTrailing: {
                let m = context.state.remainingSeconds / 60
                Text("\(m)m")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(Color.amiyaAmber)
            } minimal: {
                Image("avatar_amiya_focus")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 14, height: 14)
            }
        }
    }
}
