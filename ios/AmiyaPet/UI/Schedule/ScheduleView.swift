import SwiftUI

public struct ScheduleView: View {
    @ObservedObject var manager = ScheduleManager.shared
    @State private var currentWeek: Int = 1
    @State private var selectedCourse: Course?
    @State private var editingCourse: Course?
    @State private var isCreatingCourse: Bool = false
    @State private var newCourseWeekday: Int = 1
    @State private var newCourseSecStart: Int = 1

    @State private var showSettingsModal: Bool = false
    @State private var showImportModal: Bool = false
    @State private var showExportModal: Bool = false

    var onAskAmiyaAboutCourse: ((Course) -> Void)?

    private let colors: [Color] = [
        Color(hex: "#38BDF8"), Color(hex: "#818CF8"), Color(hex: "#34D399"),
        Color(hex: "#F472B6"), Color(hex: "#FBBF24"), Color(hex: "#A78BFA"),
        Color(hex: "#2DD4BF"), Color(hex: "#FB923C")
    ]

    public init(onAskAmiyaAboutCourse: ((Course) -> Void)? = nil) {
        self.onAskAmiyaAboutCourse = onAskAmiyaAboutCourse
    }

    public var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // 顶栏周次切换器
                weekSelectorBar

                Divider()

                // 表头 (7天星期与公历日期)
                dayHeaderView

                Divider()

                // 13 节排课网格
                timetableGridView
            }
            .navigationTitle("学期课表")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button(action: { showSettingsModal = true }) {
                        Image(systemName: "gearshape")
                    }
                }
                ToolbarItemGroup(placement: .navigationBarTrailing) {
                    Button(action: { showImportModal = true }) {
                        Image(systemName: "camera.badge.ellipsis")
                    }
                    Button(action: { showExportModal = true }) {
                        Image(systemName: "square.and.arrow.up")
                    }
                    Button(action: {
                        newCourseWeekday = 1
                        newCourseSecStart = 1
                        isCreatingCourse = true
                    }) {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(item: $selectedCourse) { course in
                CourseDetailModal(
                    course: course,
                    onEdit: { editingCourse = course },
                    onDelete: { selectedCourse = nil },
                    onAnalyze: { onAskAmiyaAboutCourse?(course) }
                )
            }
            .sheet(item: $editingCourse) { course in
                CourseEditModal(existingCourse: course) { _ in }
            }
            .sheet(isPresented: $isCreatingCourse) {
                CourseEditModal(defaultWeekday: newCourseWeekday, defaultSecStart: newCourseSecStart) { _ in }
            }
            .sheet(isPresented: $showSettingsModal) {
                ScheduleSettingsModal()
            }
            .sheet(isPresented: $showImportModal) {
                ScheduleImportModal()
            }
            .sheet(isPresented: $showExportModal) {
                IcsExportModal()
            }
            .onAppear {
                currentWeek = manager.getWeekNo()
            }
        }
    }

    private var weekSelectorBar: some View {
        HStack {
            Button(action: { if currentWeek > 1 { currentWeek -= 1 } }) {
                Image(systemName: "chevron.left")
                    .font(.system(size: 14, weight: .bold))
            }
            .disabled(currentWeek <= 1)

            Spacer()

            HStack(spacing: 6) {
                Text("第 \(currentWeek) 周")
                    .font(.system(size: 16, weight: .bold))
                let realWeek = manager.getWeekNo()
                if currentWeek == realWeek {
                    Text("本周")
                        .font(.system(size: 11, weight: .bold))
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.amiyaPrimary)
                        .foregroundColor(.white)
                        .cornerRadius(6)
                }
            }

            Spacer()

            Button(action: { if currentWeek < 30 { currentWeek += 1 } }) {
                Image(systemName: "chevron.right")
                    .font(.system(size: 14, weight: .bold))
            }
            .disabled(currentWeek >= 30)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(Color.amiyaCardBg)
    }

    private var dayHeaderView: some View {
        let dates = manager.getDatesForWeek(weekNo: currentWeek)
        let isSundayStart = manager.weekStartDay == "sunday"
        let weekdays = isSundayStart ? ["日", "一", "二", "三", "四", "五", "六"] : ["一", "二", "三", "四", "五", "六", "日"]
        let calendar = Calendar.current
        let today = Date()

        return HStack(spacing: 0) {
            // 左上角占位（节次列）
            Text("节\\周")
                .font(.system(size: 10))
                .foregroundColor(.secondary)
                .frame(width: 32)

            ForEach(0..<7, id: \.self) { idx in
                let date = idx < dates.count ? dates[idx] : Date()
                let isToday = calendar.isDate(date, inSameDayAs: today)
                let adj = manager.getAdjustment(for: date)

                VStack(spacing: 2) {
                    HStack(spacing: 2) {
                        Text(weekdays[idx])
                            .font(.system(size: 12, weight: isToday ? .bold : .medium))
                        if let a = adj {
                            Text(a.isSubstitute ? "调" : "休")
                                .font(.system(size: 9, weight: .bold))
                                .padding(.horizontal, 3)
                                .background(a.isSubstitute ? Color.cyan : Color.orange)
                                .foregroundColor(.white)
                                .cornerRadius(4)
                        }
                    }

                    Text(formatDate(date))
                        .font(.system(size: 10))
                        .foregroundColor(isToday ? Color.white : .secondary)
                        .padding(.horizontal, 4)
                        .padding(.vertical, 1)
                        .background(isToday ? Color.amiyaPrimary : Color.clear)
                        .cornerRadius(6)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 4)
            }
        }
        .background(Color.amiyaCardBg)
    }

    private var timetableGridView: some View {
        GeometryReader { geo in
            let colWidth = (geo.size.width - 32) / 7
            let totalHeight = geo.size.height
            let rowHeight = max(40.0, totalHeight / 13.0)

            ScrollView(.vertical, showsIndicators: false) {
                ZStack(alignment: .topLeading) {
                    // 背景网格刻度线与点击新建课
                    VStack(spacing: 0) {
                        ForEach(1...13, id: \.self) { sec in
                            HStack(spacing: 0) {
                                // 左侧时间与节次轴
                                VStack(spacing: 1) {
                                    Text("\(sec)")
                                        .font(.system(size: 11, weight: .bold))
                                    if let timeStr = manager.sections[String(sec)] {
                                        Text(timeStr)
                                            .font(.system(size: 8))
                                            .foregroundColor(.secondary)
                                    }
                                }
                                .frame(width: 32, height: rowHeight)
                                .background(Color.secondary.opacity(0.04))

                                ForEach(1...7, id: \.self) { dayCol in
                                    let weekday = manager.weekStartDay == "sunday" ? (dayCol == 1 ? 7 : dayCol - 1) : dayCol
                                    Rectangle()
                                        .fill(Color.clear)
                                        .frame(width: colWidth, height: rowHeight)
                                        .border(Color.secondary.opacity(0.08), width: 0.5)
                                        .contentShape(Rectangle())
                                        .onTapGesture {
                                            newCourseWeekday = weekday
                                            newCourseSecStart = sec
                                            isCreatingCourse = true
                                        }
                                }
                            }
                        }
                    }

                    // 课程卡片渲染层
                    let weekDates = manager.getDatesForWeek(weekNo: currentWeek)
                    ForEach(1...7, id: \.self) { dayCol in
                        let weekday = manager.weekStartDay == "sunday" ? (dayCol == 1 ? 7 : dayCol - 1) : dayCol
                        let dayDate = (dayCol - 1) < weekDates.count ? weekDates[dayCol - 1] : nil
                        let dayCourses = manager.getCoursesForDay(weekNo: currentWeek, weekday: weekday, date: dayDate)

                        ForEach(dayCourses) { course in
                            let topY = CGFloat(course.secStart - 1) * rowHeight
                            let cardH = CGFloat(course.secEnd - course.secStart + 1) * rowHeight - 3
                            let leftX = 32 + CGFloat(dayCol - 1) * colWidth + 1.5
                            let cardColor = colorForCourse(course.name)

                            VStack(alignment: .leading, spacing: 2) {
                                Text(course.name)
                                    .font(.system(size: 11, weight: .bold))
                                    .lineLimit(2)
                                if !course.room.isEmpty {
                                    Text(course.room)
                                        .font(.system(size: 9))
                                        .lineLimit(1)
                                }
                                if course.isActivity {
                                    Text(course.customTime)
                                        .font(.system(size: 8))
                                        .foregroundColor(.white.opacity(0.9))
                                }
                            }
                            .padding(4)
                            .frame(width: colWidth - 3, height: cardH, alignment: .topLeading)
                            .background(cardColor)
                            .foregroundColor(.white)
                            .cornerRadius(6)
                            .shadow(color: cardColor.opacity(0.3), radius: 2, x: 0, y: 1)
                            .offset(x: leftX, y: topY + 1.5)
                            .onTapGesture {
                                selectedCourse = course
                            }
                        }
                    }
                }
            }
        }
    }

    private func colorForCourse(_ name: String) -> Color {
        let hash = abs(name.hashValue)
        return colors[hash % colors.count]
    }

    private func formatDate(_ date: Date) -> String {
        let sdf = DateFormatter()
        sdf.dateFormat = "M.d"
        return sdf.string(from: date)
    }
}
