package com.amiya.pet.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.amiya.pet.R
import com.amiya.pet.core.focus.PomodoroMode
import com.amiya.pet.core.focus.PomodoroTimer
import com.amiya.pet.core.schedule.Course
import com.amiya.pet.core.schedule.ScheduleManager
import com.amiya.pet.ui.MainActivity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

class AppBackgroundService : Service() {

    companion object {
        const val ACTION_START = "com.amiya.pet.ACTION_START"
        const val ACTION_STOP = "com.amiya.pet.ACTION_STOP"

        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "pet_background_channel"
        const val REMINDER_CHANNEL_ID = "amiya_class_reminder_channel"

        private val _isRunning = MutableStateFlow(false)
        val isRunning = _isRunning.asStateFlow()

        fun ensureReminderChannel(context: Context) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val manager = context.getSystemService(NotificationManager::class.java) ?: return
                val reminderChannel = NotificationChannel(
                    REMINDER_CHANNEL_ID,
                    "阿米娅上课与下课提醒",
                    NotificationManager.IMPORTANCE_HIGH
                ).apply {
                    description = "课前提醒带好书本水杯、下课换教室与作息关怀"
                    enableLights(true)
                    enableVibration(true)
                    setShowBadge(true)
                }
                manager.createNotificationChannel(reminderChannel)
            }
        }

        fun sendTestReminder(context: Context, isDismissal: Boolean = false) {
            ensureReminderChannel(context)
            val manager = context.getSystemService(NotificationManager::class.java) ?: return
            val openAppIntent = Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val openAppPendingIntent = PendingIntent.getActivity(
                context, 0, openAppIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            val (title, msg) = if (isDismissal) {
                Pair(
                    "🚶 下课换教室提醒 (测试)",
                    "博士，《高等数学》下课啦！下一节是第 6-7 节《大学物理》（📍实验楼 201），请留意换教室别跑错教学楼哦~"
                )
            } else {
                Pair(
                    "🔔 阿米娅上课提醒 (测试)",
                    "博士，距离《高等数学》上课还有 20 分钟（📍主教楼 302 · 王教授），请记得带好水杯与课本哦。"
                )
            }
            val notif = NotificationCompat.Builder(context, REMINDER_CHANNEL_ID)
                .setContentTitle(title)
                .setContentText(msg)
                .setStyle(NotificationCompat.BigTextStyle().bigText(msg))
                .setSmallIcon(R.mipmap.ic_launcher)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setDefaults(NotificationCompat.DEFAULT_ALL)
                .setContentIntent(openAppPendingIntent)
                .setAutoCancel(true)
                .build()
            manager.notify(9999, notif)
        }
    }

    private var reminderJob: Job? = null
    private val notifiedKeys = mutableSetOf<String>()

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
        startForeground(NOTIFICATION_ID, buildNotification())

        PomodoroTimer.onTimerFinished = { mode ->
            val msg = if (mode == PomodoroMode.WORK) {
                "本次专注时间结束！请好好休息一下吧！"
            } else {
                "休息时间到了，准备下一个目标吧！"
            }
            sendClassNotification("番茄钟", msg, 1002)
        }

        _isRunning.value = true
        startClassReminderLoop()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        return START_STICKY
    }

    private fun startClassReminderLoop() {
        ScheduleManager.load(this)
        reminderJob = CoroutineScope(Dispatchers.Main + Job()).launch {
            while (true) {
                delay(30_000L) // 每 30 秒巡检一次，精准响应上课与下课时刻
                try {
                    val now = Date()
                    val cal = Calendar.getInstance().apply { time = now }
                    val weekNo = ScheduleManager.getWeekNo(now) ?: 1
                    val dayOfWeek = cal.get(Calendar.DAY_OF_WEEK)
                    val todayWeekday = if (dayOfWeek == Calendar.SUNDAY) 7 else dayOfWeek - 1
                    val todayCourses = ScheduleManager.getCoursesOn(todayWeekday, weekNo)

                    if (todayCourses.isNotEmpty()) {
                        val curHour = cal.get(Calendar.HOUR_OF_DAY)
                        val curMin = cal.get(Calendar.MINUTE)
                        val curTotalMin = curHour * 60 + curMin
                        val todayDateStr = SimpleDateFormat("yyyyMMdd", Locale.getDefault()).format(now)

                        fun getCourseTimes(c: Course): Pair<Int, Int> {
                            val stStr = ScheduleManager.sections[c.secStart.toString()] ?: "08:00"
                            val etStr = ScheduleManager.sections[c.secEnd.toString()] ?: stStr
                            val stParts = stStr.split(":")
                            val etParts = etStr.split(":")
                            val stMin = (stParts.getOrNull(0)?.toIntOrNull() ?: 8) * 60 + (stParts.getOrNull(1)?.toIntOrNull() ?: 0)
                            val etMin = (etParts.getOrNull(0)?.toIntOrNull() ?: 8) * 60 + (etParts.getOrNull(1)?.toIntOrNull() ?: 0) + 45
                            return Pair(stMin, etMin)
                        }

                        // 1. 上课前提醒
                        if (ScheduleManager.remindEnabled) {
                            for (c in todayCourses) {
                                val (stMin, _) = getCourseTimes(c)
                                val diffMin = stMin - curTotalMin
                                if (diffMin in 0..ScheduleManager.remindMinutes.toLong()) {
                                    val key = "before_${c.name}_${todayDateStr}_${c.secStart}"
                                    if (!notifiedKeys.contains(key)) {
                                        notifiedKeys.add(key)
                                        val roomStr = c.room.ifEmpty { "待定教室" }
                                        val teacherStr = if (c.teacher.isNotEmpty()) " · 授课教师：${c.teacher}" else ""
                                        val title = "🔔 阿米娅上课提醒 (还有 $diffMin 分钟)"
                                        val msg = "博士，距离《${c.name}》上课还有 $diffMin 分钟（📍$roomStr$teacherStr），请记得带好水杯与课本哦。"
                                        sendClassNotification(title, msg, (c.name.hashCode() + 1000) % 10000)
                                    }
                                }
                            }
                        }

                        // 2. 下课后关怀与换教室提醒 (下课后 5 分钟检测窗口)
                        if (ScheduleManager.dismissRemindEnabled) {
                            for (c in todayCourses) {
                                val (_, etMin) = getCourseTimes(c)
                                if (curTotalMin in etMin..(etMin + 4)) {
                                    val key = "after_${c.name}_${todayDateStr}_${c.secEnd}"
                                    if (!notifiedKeys.contains(key)) {
                                        notifiedKeys.add(key)
                                        // 查找今日后续课程
                                        val nextCourse = todayCourses.firstOrNull { it.secStart > c.secEnd }
                                        val (title, msg) = if (nextCourse != null) {
                                            val nextRoom = nextCourse.room.ifEmpty { "待定教室" }
                                            val nextTimeStr = ScheduleManager.sections[nextCourse.secStart.toString()] ?: ""
                                            Pair(
                                                "🚶 下课换教室提醒",
                                                "博士，《${c.name}》下课啦！下一节是 $nextTimeStr 第 ${nextCourse.secStart}-${nextCourse.secEnd} 节《${nextCourse.name}》（📍$nextRoom），请留意换教室别跑错教学楼哦~"
                                            )
                                        } else {
                                            if (curHour in 11..13) {
                                                Pair(
                                                    "🍱 午餐关怀提醒",
                                                    "博士，上午的课程全部结束啦！记得按时吃顿丰盛午餐犒劳自己，中午稍微小憩一下补充精力吧~"
                                                )
                                            } else if (curHour in 16..19) {
                                                Pair(
                                                    "🍲 傍晚放学提醒",
                                                    "博士，下午的课全部上完啦！今晚没有排课，可以去吃顿美味晚餐，或者去自习室整理下今天的笔记呢~"
                                                )
                                            } else {
                                                Pair(
                                                    "✨ 自习与休息建议",
                                                    "博士，《${c.name}》下课啦！接下来是整块自主掌控时间，可以自由安排自习或好好放松一下~"
                                                )
                                            }
                                        }
                                        sendClassNotification(title, msg, (c.name.hashCode() + 2000) % 10000)
                                    }
                                }
                            }
                        }
                    }
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }
        }
    }

    private fun sendClassNotification(title: String, msg: String, notifId: Int) {
        val manager = getSystemService(NotificationManager::class.java) ?: return
        val openAppIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val openAppPendingIntent = PendingIntent.getActivity(
            this, notifId, openAppIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notif = NotificationCompat.Builder(this, REMINDER_CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(msg)
            .setStyle(NotificationCompat.BigTextStyle().bigText(msg))
            .setSmallIcon(R.mipmap.ic_launcher)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setDefaults(NotificationCompat.DEFAULT_ALL)
            .setContentIntent(openAppPendingIntent)
            .setAutoCancel(true)
            .build()
        manager.notify(notifId, notif)
    }

    private fun buildNotification(): Notification {
        val openAppIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val openAppPendingIntent = PendingIntent.getActivity(
            this, 0, openAppIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("阿米娅后台守护服务")
            .setContentText("正在守护博士的课表、上下课提醒与番茄钟...")
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentIntent(openAppPendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(NotificationManager::class.java) ?: return

            // 1. 静默常驻服务渠道
            val serviceChannel = NotificationChannel(
                CHANNEL_ID,
                "后台守护服务",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "保持上课提醒与番茄钟在后台正常运行"
                setShowBadge(false)
            }
            manager.createNotificationChannel(serviceChannel)

            // 2. 高优先级上课与下课提醒渠道（支持横幅与震动）
            ensureReminderChannel(this)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        _isRunning.value = false
        reminderJob?.cancel()
    }
}
