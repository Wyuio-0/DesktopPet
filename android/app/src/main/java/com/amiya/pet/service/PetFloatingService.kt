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
import android.graphics.PixelFormat
import android.graphics.Point
import android.os.Build
import android.os.IBinder
import android.util.TypedValue
import android.view.Gravity
import android.view.WindowManager
import android.widget.FrameLayout
import androidx.core.app.NotificationCompat
import com.amiya.pet.R
import com.amiya.pet.core.model.Action
import com.amiya.pet.core.parser.CharacterParser
import com.amiya.pet.core.state.PetStateListener
import com.amiya.pet.core.state.PetStateMachine
import com.amiya.pet.render.PetGlSurfaceView
import com.amiya.pet.ui.MainActivity
import com.amiya.pet.ui.PetBubbleView
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.util.Date
import com.amiya.pet.core.schedule.ScheduleManager

import com.amiya.pet.core.focus.PomodoroMode
import com.amiya.pet.core.focus.PomodoroTimer
import com.amiya.pet.core.voice.VoicePlayer

class PetFloatingService : Service(), PetStateListener {

    companion object {
        const val ACTION_START = "com.amiya.pet.ACTION_START"
        const val ACTION_STOP = "com.amiya.pet.ACTION_STOP"
        const val ACTION_SWITCH_CHARACTER = "com.amiya.pet.ACTION_SWITCH_CHARACTER"
        const val ACTION_SET_SPEED = "com.amiya.pet.ACTION_SET_SPEED"
        const val ACTION_CYCLE_CHARACTER = "com.amiya.pet.ACTION_CYCLE_CHARACTER"
        const val ACTION_SET_VOLUME = "com.amiya.pet.ACTION_SET_VOLUME"
        const val ACTION_SET_MUTE = "com.amiya.pet.ACTION_SET_MUTE"

        const val EXTRA_CHAR_KEY = "extra_char_key"
        const val EXTRA_SPEED = "extra_speed"
        const val EXTRA_VOLUME = "extra_volume"
        const val EXTRA_MUTE = "extra_mute"

        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "pet_floating_channel"

        private val _isRunning = MutableStateFlow(false)
        val isRunning = _isRunning.asStateFlow()

        private val _currentCharKey = MutableStateFlow("amiya")
        val currentCharKey = _currentCharKey.asStateFlow()

        private val _currentSpeed = MutableStateFlow(1.15f)
        val currentSpeed = _currentSpeed.asStateFlow()

        private val _voiceVolume = MutableStateFlow(0.8f)
        val voiceVolume = _voiceVolume.asStateFlow()

        private val _isVoiceMuted = MutableStateFlow(false)
        val isVoiceMuted = _isVoiceMuted.asStateFlow()
    }

    private var windowManager: WindowManager? = null
    private var rootContainer: FrameLayout? = null
    private var glSurfaceView: PetGlSurfaceView? = null
    private var bubbleView: PetBubbleView? = null
    private var stateMachine: PetStateMachine? = null
    private var touchHandler: PetTouchHandler? = null
    private var layoutParams: WindowManager.LayoutParams? = null
    private var voicePlayer: VoicePlayer? = null
    private var reminderJob: Job? = null
    private var lastRemindedClass: String? = null

    private var screenReceiver: BroadcastReceiver? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
        registerScreenReceiver()

        voicePlayer = VoicePlayer(this).apply {
            volume = _voiceVolume.value
            isMuted = _isVoiceMuted.value
        }

        PomodoroTimer.onTimerFinished = { mode ->
            val msg = if (mode == PomodoroMode.WORK) {
                "博士，本次专注时间结束！表现太出色了，请好好休息一下吧！"
            } else {
                "博士，休息时间到了，打起精神准备下一个目标吧！"
            }
            bubbleView?.showBubble(msg, 6000L)
            voicePlayer?.playGreetVoice()
        }

        _isRunning.value = true
        startClassReminderLoop()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent == null) return START_STICKY

        when (intent.action) {
            ACTION_STOP -> {
                stopSelf()
                return START_NOT_STICKY
            }

            ACTION_CYCLE_CHARACTER -> {
                cycleNextCharacter()
            }

            ACTION_SWITCH_CHARACTER -> {
                val newChar = intent.getStringExtra(EXTRA_CHAR_KEY) ?: "amiya"
                switchCharacter(newChar)
            }

            ACTION_SET_SPEED -> {
                val speed = intent.getFloatExtra(EXTRA_SPEED, 1.15f)
                _currentSpeed.value = speed
                glSurfaceView?.setSpeed(speed)
            }

            ACTION_SET_VOLUME -> {
                val vol = intent.getFloatExtra(EXTRA_VOLUME, 0.8f)
                _voiceVolume.value = vol
                voicePlayer?.volume = vol
            }

            ACTION_SET_MUTE -> {
                val mute = intent.getBooleanExtra(EXTRA_MUTE, false)
                _isVoiceMuted.value = mute
                voicePlayer?.isMuted = mute
            }

            ACTION_START, null -> {
                val charKey = intent.getStringExtra(EXTRA_CHAR_KEY) ?: _currentCharKey.value
                val speed = intent.getFloatExtra(EXTRA_SPEED, _currentSpeed.value)
                _currentSpeed.value = speed
                if (rootContainer == null) {
                    initFloatingWindow(charKey)
                } else if (_currentCharKey.value != charKey) {
                    switchCharacter(charKey)
                }
            }
        }

        return START_STICKY
    }

    private fun initFloatingWindow(charKey: String) {
        val character = CharacterParser.loadCharacter(this, charKey)
            ?: CharacterParser.loadCharacter(this, "amiya")
            ?: return

        _currentCharKey.value = character.key

        val density = resources.displayMetrics.density
        // 手机屏幕基准宽度：150dp * 角色特定 scale
        val petWidthPx = (150 * density * character.scale).toInt().coerceIn((100 * density).toInt(), (260 * density).toInt())
        val petHeightPx = (150 * density * character.scale).toInt().coerceIn((100 * density).toInt(), (260 * density).toInt())
        val bubbleSpaceHeightPx = (50 * density).toInt()

        val totalWidthPx = petWidthPx.coerceAtLeast((180 * density).toInt())
        val totalHeightPx = petHeightPx + bubbleSpaceHeightPx

        val wm = windowManager ?: return

        val params = WindowManager.LayoutParams().apply {
            type = WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            flags = WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or
                    WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED
            format = PixelFormat.TRANSLUCENT
            width = totalWidthPx
            height = totalHeightPx
            gravity = Gravity.TOP or Gravity.START

            val screenSize = Point()
            wm.defaultDisplay.getSize(screenSize)
            x = 10
            y = (screenSize.y * 0.45f).toInt()
        }
        layoutParams = params

        rootContainer = FrameLayout(this)

        glSurfaceView = PetGlSurfaceView(this).apply {
            val lp = FrameLayout.LayoutParams(petWidthPx, petHeightPx).apply {
                gravity = Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL
            }
            layoutParams = lp
            onPlaybackEnded = {
                stateMachine?.onClipPlaybackEnded()
            }
        }

        bubbleView = PetBubbleView(this).apply {
            val lp = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL
                topMargin = (4 * density).toInt()
            }
            layoutParams = lp
        }

        rootContainer?.addView(glSurfaceView)
        rootContainer?.addView(bubbleView)

        stateMachine = PetStateMachine(character, this)

        touchHandler = PetTouchHandler(
            context = this,
            windowManager = wm,
            petView = rootContainer!!,
            layoutParams = params,
            stateMachine = stateMachine!!
        )
        rootContainer?.setOnTouchListener(touchHandler)

        wm.addView(rootContainer, params)
        stateMachine?.start()
    }

    private fun switchCharacter(newCharKey: String) {
        val character = CharacterParser.loadCharacter(this, newCharKey) ?: return
        _currentCharKey.value = character.key

        stateMachine?.destroy()
        stateMachine = PetStateMachine(character, this)

        // 重新更新触摸处理器的状态机引用
        rootContainer?.let { root ->
            layoutParams?.let { lp ->
                touchHandler = PetTouchHandler(this, windowManager!!, root, lp, stateMachine!!)
                root.setOnTouchListener(touchHandler)
            }
        }

        // 动态调整 View 尺寸适应不同角色 scale
        val density = resources.displayMetrics.density
        val petWidthPx = (150 * density * character.scale).toInt().coerceIn((100 * density).toInt(), (260 * density).toInt())
        val petHeightPx = (150 * density * character.scale).toInt().coerceIn((100 * density).toInt(), (260 * density).toInt())
        val bubbleSpaceHeightPx = (50 * density).toInt()

        val totalWidthPx = petWidthPx.coerceAtLeast((180 * density).toInt())
        val totalHeightPx = petHeightPx + bubbleSpaceHeightPx

        layoutParams?.let { lp ->
            lp.width = totalWidthPx
            lp.height = totalHeightPx
            windowManager?.updateViewLayout(rootContainer, lp)
        }

        glSurfaceView?.layoutParams = FrameLayout.LayoutParams(petWidthPx, petHeightPx).apply {
            gravity = Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL
        }

        stateMachine?.start()
        voicePlayer?.loadCharacterVoices(character.key)
    }

    private fun cycleNextCharacter() {
        val allChars = CharacterParser.listCharacters(this)
        if (allChars.isEmpty()) return
        val curIndex = allChars.indexOf(_currentCharKey.value)
        val nextIndex = if (curIndex >= 0) (curIndex + 1) % allChars.size else 0
        switchCharacter(allChars[nextIndex])
    }

    override fun onActionStarted(action: Action, clipPath: String) {
        glSurfaceView?.playAsset(clipPath, action.loop, _currentSpeed.value)
    }

    override fun onBubbleMessage(text: String) {
        bubbleView?.showBubble(text)
    }

    override fun onUserInteraction(type: String) {
        when (type) {
            "click" -> voicePlayer?.playClickVoice()
            "double_click" -> voicePlayer?.playGreetVoice()
        }
    }

    private fun registerScreenReceiver() {
        screenReceiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                when (intent?.action) {
                    Intent.ACTION_SCREEN_OFF -> {
                        glSurfaceView?.pauseVideo()
                    }
                    Intent.ACTION_SCREEN_ON, Intent.ACTION_USER_PRESENT -> {
                        glSurfaceView?.resumeVideo()
                    }
                }
            }
        }
        val filter = IntentFilter().apply {
            addAction(Intent.ACTION_SCREEN_OFF)
            addAction(Intent.ACTION_SCREEN_ON)
            addAction(Intent.ACTION_USER_PRESENT)
        }
        registerReceiver(screenReceiver, filter)
    }

    private fun buildNotification(): Notification {
        val openAppIntent = Intent(this, MainActivity::class.java)
        val openAppPendingIntent = PendingIntent.getActivity(
            this, 0, openAppIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val switchIntent = Intent(this, PetFloatingService::class.java).apply {
            action = ACTION_CYCLE_CHARACTER
        }
        val switchPendingIntent = PendingIntent.getService(
            this, 1, switchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val stopIntent = Intent(this, PetFloatingService::class.java).apply {
            action = ACTION_STOP
        }
        val stopPendingIntent = PendingIntent.getService(
            this, 2, stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("阿米娅桌宠")
            .setContentText("正在桌面上陪伴博士...")
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentIntent(openAppPendingIntent)
            .addAction(0, "切换角色", switchPendingIntent)
            .addAction(0, "收回桌宠", stopPendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "桌宠常驻前台服务",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "保持桌面宠物在前台流畅交互与节能渲染"
                setShowBadge(false)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    override fun onDestroy() {
        reminderJob?.cancel()
        super.onDestroy()
        _isRunning.value = false
        stateMachine?.destroy()
        stateMachine = null

        screenReceiver?.let {
            try {
                unregisterReceiver(it)
            } catch (e: Exception) {
                // ignore
            }
        }
        screenReceiver = null

        glSurfaceView?.release()
        glSurfaceView = null

        voicePlayer?.release()
        voicePlayer = null

        rootContainer?.let {
            try {
                windowManager?.removeView(it)
            } catch (e: Exception) {
                // ignore
            }
        }
        rootContainer = null
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
                                bubbleView?.showBubble(msg, 8000L)
                                voicePlayer?.playGreetVoice()
                                
                                val manager = getSystemService(NotificationManager::class.java)
                                val notif = NotificationCompat.Builder(this@PetFloatingService, CHANNEL_ID)
                                    .setContentTitle("上课提醒")
                                    .setContentText(msg)
                                    .setSmallIcon(R.mipmap.ic_launcher)
                                    .setPriority(NotificationCompat.PRIORITY_HIGH)
                                    .setAutoCancel(true)
                                    .build()
                                manager.notify(1002, notif)
                            }
                        }
                    }
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }
        }
    }
}
