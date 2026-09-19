package com.amiya.pet.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.PowerManager
import android.util.Log
import androidx.core.content.ContextCompat
import com.amiya.pet.core.focus.PomodoroMode
import com.amiya.pet.core.focus.PomodoroTimer
import com.amiya.pet.core.system.AlarmScheduler
import com.amiya.pet.service.AppBackgroundService
import com.amiya.pet.widget.ScheduleWidgetProvider

/**
 * 精准闹钟与系统唤醒广播接收器 (AlarmReceiver)
 * 接收来自 AlarmManager 的 RTC_WAKEUP / ELAPSED_REALTIME_WAKEUP 闹钟信号，
 * 临时唤醒 CPU 执行课表提醒推送、番茄钟响铃及开机自启恢复。
 */
class AlarmReceiver : BroadcastReceiver() {

    companion object {
        const val ACTION_COURSE_REMINDER = "com.amiya.pet.action.ALARM_COURSE_REMINDER"
        const val ACTION_POMODORO_FINISH = "com.amiya.pet.action.ALARM_POMODORO_FINISH"
        private const val TAG = "AlarmReceiver"
    }

    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action ?: return
        Log.d(TAG, "onReceive triggered with action: $action")

        // 申请 5 秒临时唤醒锁，确保在 CPU 浅睡眠状态下顺利发出通知
        val pm = context.getSystemService(Context.POWER_SERVICE) as? PowerManager
        val wakeLock = pm?.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "amiya:AlarmReceiverWakeLock")
        wakeLock?.acquire(5000L)

        try {
            when (action) {
                ACTION_COURSE_REMINDER -> {
                    // 执行课表提醒检查与下发
                    AppBackgroundService.checkAndTriggerCourseReminder(context)
                    // 链式调度下一个闹钟
                    AlarmScheduler.scheduleNextCourseReminder(context)
                }

                ACTION_POMODORO_FINISH -> {
                    val modeName = intent.getStringExtra("mode") ?: PomodoroMode.WORK.name
                    val mode = try {
                        PomodoroMode.valueOf(modeName)
                    } catch (_: Exception) {
                        PomodoroMode.WORK
                    }

                    PomodoroTimer.completeFromAlarm()
                    AppBackgroundService.sendPomodoroFinishedNotification(context, mode)
                }

                Intent.ACTION_BOOT_COMPLETED -> {
                    Log.d(TAG, "Device rebooted, restarting background guard service and schedule alarms")
                    val serviceIntent = Intent(context, AppBackgroundService::class.java)
                    ContextCompat.startForegroundService(context, serviceIntent)
                    AlarmScheduler.scheduleNextCourseReminder(context)
                    ScheduleWidgetProvider.sendUpdateBroadcast(context)
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error handling alarm broadcast", e)
        } finally {
            try {
                if (wakeLock?.isHeld == true) {
                    wakeLock.release()
                }
            } catch (_: Exception) {}
        }
    }
}
