import WidgetKit
import SwiftUI

public struct ScheduleTimelineEntry: TimelineEntry {
    public let date: Date
    public let todayCourses: [Course]
    public let nextCourse: Course?
}

public struct ScheduleTimelineProvider: TimelineProvider {
    public func placeholder(in context: Context) -> ScheduleTimelineEntry {
        ScheduleTimelineEntry(date: Date(), todayCourses: [], nextCourse: nil)
    }

    public func getSnapshot(in context: Context, completion: @escaping (ScheduleTimelineEntry) -> Void) {
        let courses = ScheduleManager.shared.getTodayCourses()
        let next = ScheduleManager.shared.getNextUpcomingCourse()?.course
        completion(ScheduleTimelineEntry(date: Date(), todayCourses: courses, nextCourse: next))
    }

    public func getTimeline(in context: Context, completion: @escaping (Timeline<ScheduleTimelineEntry>) -> Void) {
        let courses = ScheduleManager.shared.getTodayCourses()
        let next = ScheduleManager.shared.getNextUpcomingCourse()?.course
        let entry = ScheduleTimelineEntry(date: Date(), todayCourses: courses, nextCourse: next)

        // 每半小时刷新一次或在下一个整点刷新
        let nextUpdate = Calendar.current.date(byAdding: .minute, value: 30, to: Date()) ?? Date()
        let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))
        completion(timeline)
    }
}

public struct AmiyaScheduleWidgetEntryView: View {
    var entry: ScheduleTimelineEntry
    @Environment(\.widgetFamily) var family

    public var body: some View {
        switch family {
        case .systemSmall:
            smallWidgetView
        case .systemMedium:
            mediumWidgetView
        default:
            mediumWidgetView
        }
    }

    private var smallWidgetView: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image("avatar_amiya")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 24, height: 24)
                    .clipShape(Circle())
                Text("今日排课")
                    .font(.system(size: 13, weight: .bold))
                Spacer()
            }

            if let next = entry.nextCourse {
                Text("下一节课")
                    .font(.system(size: 10))
                    .foregroundColor(.secondary)
                Text(next.name)
                    .font(.system(size: 14, weight: .bold))
                    .lineLimit(1)
                Text("📍 \(next.room.isEmpty ? "待定" : next.room)")
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
            } else {
                Spacer()
                Text("今日无更多课~")
                    .font(.system(size: 12))
                    .foregroundColor(.secondary)
                Spacer()
            }
        }
        .padding(12)
        .background(Color.amiyaCardBg)
    }

    private var mediumWidgetView: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    Image("avatar_amiya")
                        .resizable()
                        .scaledToFit()
                        .frame(width: 26, height: 26)
                        .clipShape(Circle())
                    Text("阿米娅今日课表")
                        .font(.system(size: 14, weight: .bold))
                }

                if let next = entry.nextCourse {
                    Text("▷ 下一节课：\(next.formattedSectionDisplay())")
                        .font(.system(size: 11))
                        .foregroundColor(Color.amiyaPrimary)
                    Text("《\(next.name)》")
                        .font(.system(size: 14, weight: .bold))
                    Text("📍 \(next.room)")
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                } else {
                    Text("今天所有课程均已结束")
                        .font(.system(size: 12))
                        .foregroundColor(.secondary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            Divider()

            VStack(alignment: .leading, spacing: 4) {
                Text("今日总计 \(entry.todayCourses.count) 节课")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundColor(.secondary)

                ForEach(entry.todayCourses.prefix(3)) { c in
                    HStack(spacing: 4) {
                        Circle()
                            .fill(Color.amiyaPrimary)
                            .frame(width: 5, height: 5)
                        Text(c.name)
                            .font(.system(size: 11, weight: .medium))
                            .lineLimit(1)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(14)
        .background(Color.amiyaCardBg)
    }
}

public struct AmiyaScheduleWidget: Widget {
    let kind: String = "AmiyaScheduleWidget"

    public var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: ScheduleTimelineProvider()) { entry in
            AmiyaScheduleWidgetEntryView(entry: entry)
        }
        .configurationDisplayName("阿米娅今日课表")
        .description("在手机桌面随时查看今日排课、节次时间与下一节教室。")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}
