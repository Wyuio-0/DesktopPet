package com.amiya.pet.core.system

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import com.amiya.pet.core.focus.PomodoroMode
import com.amiya.pet.core.schedule.Course
import com.amiya.pet.core.schedule.ScheduleManager
import com.amiya.pet.receiver.AlarmReceiver
import java.util.Calendar
import java.util.Date

/**
 * 精准闹钟调度器 (AlarmScheduler)
 * 使用系统底层 AlarmManager.setExactAndAllowWhileIdle 突破 Android Doze 深度休眠，
 * 实现息屏休眠状态下课表提醒与番茄钟倒计时的秒级精准唤醒。
 */
object AlarmScheduler {

    private const val TAG = "AlarmScheduler"
    private const val REQ_CODE_COURSE_REMINDER = 2001
    private const val REQ_CODE_POMODORO = 2002

    /**
     * 调度下一次最近的上课或下课提醒
     */
    fun scheduleNextCourseReminder(context: Context) {
        try {
            val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as? AlarmManager ?: return
            ScheduleManager.load(context)

            if (!ScheduleManager.remindEnabled && !ScheduleManager.dismissRemindEnabled) {
                cancelCourseReminderAlarm(context)
                return
            }

            val nowMillis = System.currentTimeMillis()
            val upcomingTimestamps = mutableListOf<Long>()

            fun collectReminderTimesForDay(date: Date, baseCal: Calendar) {
                val courses = ScheduleManager.getCoursesForDay(date)
                for (c in courses) {
                    val stStr = ScheduleManager.sections[c.secStart.toString()] ?: "08:00"
                    val etStr = ScheduleManager.sections[c.secEnd.toString()] ?: stStr
                    val stParts = stStr.split(":")
                    val etParts = etStr.split(":")
                    val stHour = stParts.getOrNull(0)?.toIntOrNull() ?: 8
                    val stMin = stParts.getOrNull(1)?.toIntOrNull() ?: 0
                    val etHour = etParts.getOrNull(0)?.toIntOrNull() ?: 8
                    val etMin = etParts.getOrNull(1)?.toIntOrNull() ?: 0

                    // 1. 上课前提醒时间点
                    if (ScheduleManager.remindEnabled) {
                        val classStartCal = (baseCal.clone() as Calendar).apply {
                            set(Calendar.HOUR_OF_DAY, stHour)
                            set(Calendar.MINUTE, stMin)
                            set(Calendar.SECOND, 0)
                            set(Calendar.MILLISECOND, 0)
                        }
                        val remindTime = classStartCal.timeInMillis - (ScheduleManager.remindMinutes * 60 * 1000L)
                        if (remindTime > nowMillis + 2000L) {
                            upcomingTimestamps.add(remindTime)
                        }
                    }

                    // 2. 下课关怀提醒时间点 (单节课 45 分钟)
                    if (ScheduleManager.dismissRemindEnabled) {
                        val classEndCal = (baseCal.clone() as Calendar).apply {
                            set(Calendar.HOUR_OF_DAY, etHour)
                            set(Calendar.MINUTE, etMin + 45)
                            set(Calendar.SECOND, 0)
                            set(Calendar.MILLISECOND, 0)
                        }
                        val dismissTime = classEndCal.timeInMillis
                        if (dismissTime > nowMillis + 2000L) {
                            upcomingTimestamps.add(dismissTime)
                        }
                    }
                }
            }

            // 收集今天与明天的提醒候选
            val todayCal = Calendar.getInstance()
            collectReminderTimesForDay(todayCal.time, todayCal)

            val tomorrowCal = (todayCal.clone() as Calendar).apply { add(Calendar.DAY_OF_YEAR, 1) }
            collectReminderTimesForDay(tomorrowCal.time, tomorrowCal)

            val earliestNextReminder = upcomingTimestamps.minOrNull()
            if (earliestNextReminder != null) {
                val intent = Intent(context, AlarmReceiver::class.java).apply {
                    action = AlarmReceiver.ACTION_COURSE_REMINDER
                }
                val pIntent = PendingIntent.getBroadcast(
                    context,
                    REQ_CODE_COURSE_REMINDER,
                    intent,
                    PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
                )

                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    alarmManager.setExactAndAllowWhileIdle(
                        AlarmManager.RTC_WAKEUP,
                        earliestNextReminder,
                        pIntent
                    )
                } else {
                    alarmManager.setExact(
                        AlarmManager.RTC_WAKEUP,
                        earliestNextReminder,
                        pIntent
                    )
                }
                Log.d(TAG, "Successfully scheduled next course reminder at $earliestNextReminder")
            } else {
                cancelCourseReminderAlarm(context)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to schedule next course reminder", e)
        }
    }

    /**
     * 取消课表提醒闹钟
     */
    fun cancelCourseReminderAlarm(context: Context) {
        try {
            val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as? AlarmManager ?: return
            val intent = Intent(context, AlarmReceiver::class.java).apply {
                action = AlarmReceiver.ACTION_COURSE_REMINDER
            }
            val pIntent = PendingIntent.getBroadcast(
                context,
                REQ_CODE_COURSE_REMINDER,
                intent,
                PendingIntent.FLAG_NO_CREATE or (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
            )
            if (pIntent != null) {
                alarmManager.cancel(pIntent)
                pIntent.cancel()
            }
        } catch (_: Exception) {}
    }

    /**
     * 调度番茄钟结束精准唤醒闹钟 (基于 ELAPSED_REALTIME_WAKEUP)
     */
    fun schedulePomodoroAlarm(context: Context, triggerAtRealtime: Long, mode: PomodoroMode) {
        try {
            val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as? AlarmManager ?: return
            val intent = Intent(context, AlarmReceiver::class.java).apply {
                action = AlarmReceiver.ACTION_POMODORO_FINISH
                putExtra("mode", mode.name)
            }
            val pIntent = PendingIntent.getBroadcast(
                context,
                REQ_CODE_POMODORO,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
            )

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                alarmManager.setExactAndAllowWhileIdle(
                    AlarmManager.ELAPSED_REALTIME_WAKEUP,
                    triggerAtRealtime,
                    pIntent
                )
            } else {
                alarmManager.setExact(
                    AlarmManager.ELAPSED_REALTIME_WAKEUP,
                    triggerAtRealtime,
                    pIntent
                )
            }
            Log.d(TAG, "Successfully scheduled Pomodoro alarm at realtime $triggerAtRealtime")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to schedule Pomodoro alarm", e)
        }
    }

    /**
     * 取消番茄钟闹钟
     */
    fun cancelPomodoroAlarm(context: Context) {
        try {
            val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as? AlarmManager ?: return
            val intent = Intent(context, AlarmReceiver::class.java).apply {
                action = AlarmReceiver.ACTION_POMODORO_FINISH
            }
            val pIntent = PendingIntent.getBroadcast(
                context,
                REQ_CODE_POMODORO,
                intent,
                PendingIntent.FLAG_NO_CREATE or (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
            )
            if (pIntent != null) {
                alarmManager.cancel(pIntent)
                pIntent.cancel()
            }
        } catch (_: Exception) {}
    }
}
