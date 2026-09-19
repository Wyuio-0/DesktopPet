package com.amiya.pet.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.amiya.pet.R
import com.amiya.pet.core.focus.PomodoroMode
import com.amiya.pet.core.focus.PomodoroTimer
import com.amiya.pet.core.schedule.Course
import com.amiya.pet.core.schedule.ScheduleManager
import com.amiya.pet.core.system.AlarmScheduler
import com.amiya.pet.floating.FloatingPetManager
import com.amiya.pet.ui.MainActivity
import com.amiya.pet.widget.ScheduleWidgetProvider
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
        private const val TAG = "AppBackgroundService"

        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "pet_background_channel"
        const val REMINDER_CHANNEL_ID = "amiya_class_reminder_channel"
        const val LIVE_CLASS_CHANNEL_ID = "amiya_live_class_channel"
        const val LIVE_CLASS_NOTIF_ID = 1005
        const val LIVE_CLASS_TEST_NOTIF_ID = 9998

        private val _isRunning = MutableStateFlow(false)
        val isRunning = _isRunning.asStateFlow()

        private val notifiedKeys = mutableSetOf<String>()

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

                val liveClassChannel = NotificationChannel(
                    LIVE_CLASS_CHANNEL_ID,
                    "阿米娅上课实时进度 (灵动微卡片)",
                    NotificationManager.IMPORTANCE_LOW
                ).apply {
                    description = "正在上课时在通知栏与锁屏显示实时倒计时进度条与下课换教室指引"
                    lockscreenVisibility = Notification.VISIBILITY_PUBLIC
                    setShowBadge(false)
                }
                manager.createNotificationChannel(liveClassChannel)
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
                PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
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

        fun sendPomodoroFinishedNotification(context: Context, mode: PomodoroMode) {
            ensureReminderChannel(context)
            val msg = if (mode == PomodoroMode.WORK) {
                "本次专注时间结束！请好好休息一下吧！"
            } else {
                "休息时间到了，准备下一个目标吧！"
            }
            sendClassNotification(context, "🍅 番茄钟提醒", msg, 1002)
        }

        fun sendClassNotification(context: Context, title: String, msg: String, notifId: Int) {
            ensureReminderChannel(context)
            val manager = context.getSystemService(NotificationManager::class.java) ?: return
            val openAppIntent = Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val openAppPendingIntent = PendingIntent.getActivity(
                context, notifId, openAppIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
            )

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
            manager.notify(notifId, notif)
        }

        /**
         * 实时计算并更新锁屏/通知栏「正在上课」动态进度卡片 (Live Activity)
         * 上课期间每分钟推进进度条，展示剩余下课分钟数与后续换教室指引；下课时自动清除
         */
        fun updateLiveClassProgressNotification(context: Context) {
            try {
                ensureReminderChannel(context)
                val manager = context.getSystemService(NotificationManager::class.java) ?: return
                ScheduleManager.load(context)
                if (!ScheduleManager.liveClassEnabled) {
                    manager.cancel(LIVE_CLASS_NOTIF_ID)
                    manager.cancel(LIVE_CLASS_TEST_NOTIF_ID)
                    return
                }

                val now = Date()
                val cal = Calendar.getInstance().apply { time = now }
                val todayCourses = ScheduleManager.getCoursesForDay(now)
                if (todayCourses.isEmpty()) {
                    manager.cancel(LIVE_CLASS_NOTIF_ID)
                    return
                }

                val curHour = cal.get(Calendar.HOUR_OF_DAY)
                val curMin = cal.get(Calendar.MINUTE)
                val curTotalMin = curHour * 60 + curMin

                fun getCourseTimes(c: Course): Pair<Int, Int> {
                    val stStr = ScheduleManager.sections[c.secStart.toString()] ?: "08:00"
                    val etStr = ScheduleManager.sections[c.secEnd.toString()] ?: stStr
                    val stParts = stStr.split(":")
                    val etParts = etStr.split(":")
                    val stMin = (stParts.getOrNull(0)?.toIntOrNull() ?: 8) * 60 + (stParts.getOrNull(1)?.toIntOrNull() ?: 0)
                    val etMin = (etParts.getOrNull(0)?.toIntOrNull() ?: 8) * 60 + (etParts.getOrNull(1)?.toIntOrNull() ?: 0) + 45
                    return Pair(stMin, etMin)
                }

                // 查找当前时刻是否正处于某门课程的上课时间区间
                val ongoingCourse = todayCourses.firstOrNull { c ->
                    val (stMin, etMin) = getCourseTimes(c)
                    curTotalMin in stMin until etMin
                }

                if (ongoingCourse == null) {
                    manager.cancel(LIVE_CLASS_NOTIF_ID)
                    return
                }

                val (stMin, etMin) = getCourseTimes(ongoingCourse)
                val totalDuration = maxOf(1, etMin - stMin)
                val elapsed = (curTotalMin - stMin).coerceIn(0, totalDuration)
                val remaining = (etMin - curTotalMin).coerceAtLeast(0)

                val roomStr = ongoingCourse.room.ifEmpty { "待定教室" }
                val teacherStr = if (ongoingCourse.teacher.isNotEmpty()) " · ${ongoingCourse.teacher}" else ""

                // 查找今日后续第一门课
                val nextCourse = todayCourses.firstOrNull { it.secStart > ongoingCourse.secEnd }
                val nextCourseInfo = if (nextCourse != null) {
                    val nextRoom = nextCourse.room.ifEmpty { "待定教室" }
                    val nextTimeStr = ScheduleManager.sections[nextCourse.secStart.toString()] ?: ""
                    "下一节：$nextTimeStr 第 ${nextCourse.secStart}-${nextCourse.secEnd} 节《${nextCourse.name}》（📍$nextRoom）"
                } else {
                    "今日最后一节排课，上完即可下课休息~"
                }

                val openAppIntent = Intent(context, MainActivity::class.java).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                }
                val openAppPendingIntent = PendingIntent.getActivity(
                    context, 0, openAppIntent,
                    PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
                )

                val notif = NotificationCompat.Builder(context, LIVE_CLASS_CHANNEL_ID)
                    .setContentTitle("🔴 正在上课: 《${ongoingCourse.name}》 (第 ${ongoingCourse.secStart}-${ongoingCourse.secEnd} 节)")
                    .setContentText("⏳ 剩余 $remaining 分钟下课 · 📍 $roomStr")
                    .setSubText("已上 $elapsed / $totalDuration 分钟")
                    .setStyle(
                        NotificationCompat.BigTextStyle().bigText(
                            "【正在上课中】《${ongoingCourse.name}》\n" +
                            "📍 教室：$roomStr$teacherStr\n" +
                            "⏳ 倒计时：已上 $elapsed 分钟，剩余 $remaining 分钟下课\n" +
                            "▷ 后续安排：$nextCourseInfo"
                        )
                    )
                    .setSmallIcon(R.mipmap.ic_launcher)
                    .setProgress(totalDuration, elapsed, false)
                    .setOngoing(true)
                    .setOnlyAlertOnce(true)
                    .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                    .setGroup("com.amiya.pet.LIVE_ACTIVITY")
                    .setCategory(NotificationCompat.CATEGORY_PROGRESS)
                    .setContentIntent(openAppPendingIntent)
                    .build()

                manager.notify(LIVE_CLASS_NOTIF_ID, notif)
            } catch (e: Exception) {
                Log.e(TAG, "Error updating live class notification", e)
            }
        }

        fun sendTestLiveClassNotification(context: Context) {
            ensureReminderChannel(context)
            val manager = context.getSystemService(NotificationManager::class.java) ?: return

            val openAppIntent = Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val openAppPendingIntent = PendingIntent.getActivity(
                context, 0, openAppIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
            )

            val notif = NotificationCompat.Builder(context, LIVE_CLASS_CHANNEL_ID)
                .setContentTitle("🔴 正在上课: 《高等数学》 (第 3-4 节 · 灵动卡片)")
                .setContentText("⏳ 剩余 18 分钟下课 · 📍 主教楼 302")
                .setSubText("已上 77 / 95 分钟")
                .setStyle(
                    NotificationCompat.BigTextStyle().bigText(
                        "【正在上课中】《高等数学》\n" +
                        "📍 教室：主教楼 302 · 王教授\n" +
                        "⏳ 倒计时：已上 77 分钟，剩余 18 分钟下课 (81%)\n" +
                        "▷ 下一节课：14:05 第 6-7 节《大学物理》（📍实验楼 201）"
                    )
                )
                .setSmallIcon(R.mipmap.ic_launcher)
                .setProgress(95, 77, false)
                .setOngoing(false)
                .setAutoCancel(true)
                .setOnlyAlertOnce(true)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .setGroup("com.amiya.pet.LIVE_ACTIVITY")
                .setCategory(NotificationCompat.CATEGORY_PROGRESS)
                .setContentIntent(openAppPendingIntent)
                .build()

            manager.notify(LIVE_CLASS_TEST_NOTIF_ID, notif)
        }

        /**
         * 巡检并即时触发上课与下课关怀通知（可由 AlarmManager 或定时轮询触发）
         */
        fun checkAndTriggerCourseReminder(context: Context) {
            try {
                ScheduleManager.load(context)
                val now = Date()
                val cal = Calendar.getInstance().apply { time = now }
                val todayCourses = ScheduleManager.getCoursesForDay(now)
                if (todayCourses.isEmpty()) return

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
                                sendClassNotification(context, title, msg, (c.name.hashCode() + 1000) % 10000)
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
                                sendClassNotification(context, title, msg, (c.name.hashCode() + 2000) % 10000)
                            }
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error in checkAndTriggerCourseReminder", e)
            }
        }
    }

    private var reminderJob: Job? = null

    // 动态广播接收器：实时监听系统每分钟跳动、时区变更与亮屏
    private val systemTimeReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent?) {
            try {
                // 1. 刷新小组件
                ScheduleWidgetProvider.sendUpdateBroadcast(context)
                // 2. 刷新桌面悬浮桌宠状态与头顶徽章
                FloatingPetManager.evaluateAndApplyState(context)
                // 3. 刷新番茄钟实时剩余秒数
                PomodoroTimer.refreshTime()
                // 4. 课表准点提醒检查
                checkAndTriggerCourseReminder(context)
                // 5. 正在上课实时进度锁屏通知 (Live Activity) 更新
                updateLiveClassProgressNotification(context)
            } catch (e: Exception) {
                Log.e(TAG, "Error handling dynamic system time broadcast", e)
            }
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
        startForeground(NOTIFICATION_ID, buildNotification())

        // 初始化番茄钟上下文与结束回调
        PomodoroTimer.init(applicationContext)
        PomodoroTimer.onTimerFinished = { mode ->
            sendPomodoroFinishedNotification(this, mode)
        }

        // 动态注册系统时间跳动广播 (Android 8.0+ 必须动态注册)
        val filter = IntentFilter().apply {
            addAction(Intent.ACTION_TIME_TICK)
            addAction(Intent.ACTION_TIME_CHANGED)
            addAction(Intent.ACTION_TIMEZONE_CHANGED)
            addAction(Intent.ACTION_SCREEN_ON)
        }
        registerReceiver(systemTimeReceiver, filter)

        _isRunning.value = true

        // 调度下一次精确上课/下课闹钟
        AlarmScheduler.scheduleNextCourseReminder(this)

        // 启动辅助常驻协程轮询 (多重防漏兜底)
        startClassReminderLoop()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        // 每次启动服务时刷新下次闹钟调度
        AlarmScheduler.scheduleNextCourseReminder(this)
        return START_STICKY
    }

    private fun startClassReminderLoop() {
        ScheduleManager.load(this)
        reminderJob = CoroutineScope(Dispatchers.Main + Job()).launch {
            while (true) {
                delay(30_000L) // 每 30 秒巡检一次，精准响应上课与下课时刻
                checkAndTriggerCourseReminder(this@AppBackgroundService)
            }
        }
    }

    private fun buildNotification(): Notification {
        val openAppIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val openAppPendingIntent = PendingIntent.getActivity(
            this, 0, openAppIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
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
        try {
            (getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager)?.apply {
                cancel(LIVE_CLASS_NOTIF_ID)
                cancel(LIVE_CLASS_TEST_NOTIF_ID)
            }
        } catch (_: Exception) {}
        try {
            unregisterReceiver(systemTimeReceiver)
        } catch (_: Exception) {}
    }
}
