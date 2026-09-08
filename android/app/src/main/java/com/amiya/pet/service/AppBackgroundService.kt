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
import com.amiya.pet.core.schedule.ScheduleManager
import com.amiya.pet.ui.MainActivity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.Date

class AppBackgroundService : Service() {

    companion object {
        const val ACTION_START = "com.amiya.pet.ACTION_START"
        const val ACTION_STOP = "com.amiya.pet.ACTION_STOP"

        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "pet_background_channel"

        private val _isRunning = MutableStateFlow(false)
        val isRunning = _isRunning.asStateFlow()
    }

    private var reminderJob: Job? = null
    private var lastRemindedClass: String? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification())

        PomodoroTimer.onTimerFinished = { mode ->
            val msg = if (mode == PomodoroMode.WORK) {
                "本次专注时间结束！请好好休息一下吧！"
            } else {
                "休息时间到了，准备下一个目标吧！"
            }
            sendHighPriorityNotification("番茄钟", msg)
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
                delay(60_000L) // check every minute
                try {
                    val next = ScheduleManager.nextClass(Date())
                    if (next != null) {
                        val diffMillis = next.startTime.time - Date().time
                        val diffMinutes = diffMillis / 60000
                        if (diffMinutes in 0..ScheduleManager.remindMinutes.toLong()) {
                            val classId = "${next.course.name}_${next.startTime.time}"
                            if (lastRemindedClass != classId) {
                                lastRemindedClass = classId
                                val msg = "博士，即将上课：${next.course.name} (在 ${next.course.room})。请做好准备哦！"
                                sendHighPriorityNotification("上课提醒", msg)
                            }
                        }
                    }
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }
        }
    }

    private fun sendHighPriorityNotification(title: String, msg: String) {
        val manager = getSystemService(NotificationManager::class.java)
        val notif = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(msg)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .build()
        manager.notify((System.currentTimeMillis() % 10000).toInt(), notif)
    }

    private fun buildNotification(): Notification {
        val openAppIntent = Intent(this, MainActivity::class.java)
        val openAppPendingIntent = PendingIntent.getActivity(
            this, 0, openAppIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("阿米娅后台服务")
            .setContentText("正在守护博士的课表与番茄钟...")
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentIntent(openAppPendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "后台守护服务",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "保持上课提醒与番茄钟在后台正常运行"
                setShowBadge(false)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        _isRunning.value = false
        reminderJob?.cancel()
    }
}

