package com.amiya.pet.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.view.View
import android.widget.RemoteViews
import com.amiya.pet.R
import com.amiya.pet.core.schedule.Course
import com.amiya.pet.core.schedule.ScheduleManager
import com.amiya.pet.ui.MainActivity
import java.util.Calendar
import java.util.Date

/**
 * 阿米娅今日课表桌面小组件 (Android AppWidget Provider)
 * 支持桌面实时查看今日排课、当前周次、下一节课时间与教室地点。
 */
class ScheduleWidgetProvider : AppWidgetProvider() {

    override fun onUpdate(context: Context, appWidgetManager: AppWidgetManager, appWidgetIds: IntArray) {
        for (appWidgetId in appWidgetIds) {
            updateAppWidget(context, appWidgetManager, appWidgetId)
        }
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        if (intent.action == ACTION_REFRESH_WIDGET || intent.action == Intent.ACTION_TIME_TICK || intent.action == Intent.ACTION_TIME_CHANGED) {
            val appWidgetManager = AppWidgetManager.getInstance(context)
            val thisWidget = ComponentName(context, ScheduleWidgetProvider::class.java)
            val appWidgetIds = appWidgetManager.getAppWidgetIds(thisWidget)
            for (appWidgetId in appWidgetIds) {
                updateAppWidget(context, appWidgetManager, appWidgetId)
            }
        }
    }

    companion object {
        const val ACTION_REFRESH_WIDGET = "com.amiya.pet.action.REFRESH_WIDGET"

        fun sendUpdateBroadcast(context: Context) {
            try {
                val intent = Intent(context, ScheduleWidgetProvider::class.java).apply {
                    action = ACTION_REFRESH_WIDGET
                }
                context.sendBroadcast(intent)
            } catch (_: Exception) {
            }
        }

        fun updateAppWidget(context: Context, appWidgetManager: AppWidgetManager, appWidgetId: Int) {
            val views = RemoteViews(context.packageName, R.layout.widget_schedule_layout)

            // 1. 加载课表数据
            ScheduleManager.load(context)

            val now = Date()
            val cal = Calendar.getInstance().apply { time = now }
            val weekNo = ScheduleManager.getWeekNo(now) ?: 1

            val dayOfWeek = cal.get(Calendar.DAY_OF_WEEK)
            val todayWeekday = if (dayOfWeek == Calendar.SUNDAY) 7 else dayOfWeek - 1
            val weekdayNames = arrayOf("", "周一", "周二", "周三", "周四", "周五", "周六", "周日")
            val weekdayName = weekdayNames.getOrElse(todayWeekday) { "周一" }

            // 2. 顶栏学期与周次
            views.setTextViewText(R.id.widget_week_badge, "第 $weekNo 周 · $weekdayName")

            // 3. 检查是否有课表数据
            if (ScheduleManager.courses.isEmpty()) {
                views.setViewVisibility(R.id.widget_has_courses_container, View.GONE)
                views.setViewVisibility(R.id.widget_empty_container, View.VISIBLE)
                views.setTextViewText(R.id.widget_empty_title, "📚 暂无课表数据")
                views.setTextViewText(R.id.widget_empty_desc, "点击进入阿米娅导入教务课表")
            } else {
                val todayCourses = ScheduleManager.getCoursesOn(todayWeekday, weekNo)
                if (todayCourses.isEmpty()) {
                    views.setViewVisibility(R.id.widget_has_courses_container, View.GONE)
                    views.setViewVisibility(R.id.widget_empty_container, View.VISIBLE)
                    views.setTextViewText(R.id.widget_empty_title, "📅 今日全天无排课")
                    views.setTextViewText(R.id.widget_empty_desc, "今天没有课程，好好放松或自主复习吧，博士~")
                } else {
                    // 计算当前分钟数判断待上课程
                    val curHour = cal.get(Calendar.HOUR_OF_DAY)
                    val curMin = cal.get(Calendar.MINUTE)
                    val curTotalMin = curHour * 60 + curMin

                    fun getCourseTimes(c: Course): Pair<Int, Int> {
                        val stStr = ScheduleManager.sections[c.secStart.toString()] ?: "08:00"
                        val etStr = ScheduleManager.sections[c.secEnd.toString()] ?: stStr
                        val stParts = stStr.split(":")
                        val etParts = etStr.split(":")
                        val stMin = (stParts.getOrNull(0)?.toIntOrNull() ?: 8) * 60 + (stParts.getOrNull(1)?.toIntOrNull() ?: 0)
                        // 每节课默认 45 分钟
                        val etMin = (etParts.getOrNull(0)?.toIntOrNull() ?: 8) * 60 + (etParts.getOrNull(1)?.toIntOrNull() ?: 0) + 45
                        return Pair(stMin, etMin)
                    }

                    // 找出还未上完的第一门课程
                    val nextCourse = todayCourses.firstOrNull { c ->
                        val (_, etMin) = getCourseTimes(c)
                        etMin > curTotalMin
                    }

                    if (nextCourse == null) {
                        // 今日所有课程已经结束
                        views.setViewVisibility(R.id.widget_has_courses_container, View.GONE)
                        views.setViewVisibility(R.id.widget_empty_container, View.VISIBLE)
                        views.setTextViewText(R.id.widget_empty_title, "🎉 今日所有课程已结束")
                        views.setTextViewText(R.id.widget_empty_desc, "博士辛苦了，早点休息准备明天吧！")
                    } else {
                        // 展示下一节课卡片
                        views.setViewVisibility(R.id.widget_has_courses_container, View.VISIBLE)
                        views.setViewVisibility(R.id.widget_empty_container, View.GONE)

                        val (stMin, etMin) = getCourseTimes(nextCourse)
                        val startTimeStr = ScheduleManager.sections[nextCourse.secStart.toString()] ?: "%02d:%02d".format(stMin / 60, stMin % 60)

                        val statusTag = when {
                            curTotalMin in stMin until etMin -> "🔴 正在上课 · 第 ${nextCourse.secStart}-${nextCourse.secEnd} 节"
                            stMin - curTotalMin in 1..60 -> "⚡ 即将开始 (${stMin - curTotalMin}分钟后 · $startTimeStr)"
                            else -> "▶ 下一节 $startTimeStr"
                        }

                        views.setTextViewText(R.id.widget_next_tag, statusTag)
                        views.setTextViewText(R.id.widget_next_section, "(第 ${nextCourse.secStart}-${nextCourse.secEnd} 节)")
                        views.setTextViewText(R.id.widget_next_name, "《${nextCourse.name}》")

                        val roomStr = nextCourse.room.ifEmpty { "待定地点" }
                        val teacherStr = if (nextCourse.teacher.isNotEmpty()) " · ${nextCourse.teacher}" else ""
                        views.setTextViewText(R.id.widget_next_location, "📍 $roomStr$teacherStr")

                        // 后续课程预览
                        val remaining = todayCourses.filter { it.secStart > nextCourse.secStart }
                        if (remaining.isNotEmpty()) {
                            val upcomingStr = remaining.take(2).joinToString(" | ") { c ->
                                val st = ScheduleManager.sections[c.secStart.toString()] ?: ""
                                "$st 《${c.name}》@${c.room.ifEmpty { "待定" }}"
                            }
                            views.setTextViewText(R.id.widget_upcoming_text, "▷ 后续: $upcomingStr")
                        } else {
                            views.setTextViewText(R.id.widget_upcoming_text, "▷ 今日最后一门课程，上完即可下课~")
                        }
                    }
                }
            }

            // 4. 点击打开 App (进入主页课表)
            val appIntent = Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val appPendingIntent = PendingIntent.getActivity(
                context,
                0,
                appIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            views.setOnClickPendingIntent(R.id.widget_root, appPendingIntent)

            // 5. 点击右上角刷新小组件
            val refreshIntent = Intent(context, ScheduleWidgetProvider::class.java).apply {
                action = ACTION_REFRESH_WIDGET
            }
            val refreshPendingIntent = PendingIntent.getBroadcast(
                context,
                appWidgetId,
                refreshIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            views.setOnClickPendingIntent(R.id.widget_btn_refresh, refreshPendingIntent)

            appWidgetManager.updateAppWidget(appWidgetId, views)
        }
    }
}
