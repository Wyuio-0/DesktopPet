package com.amiya.pet.floating

import android.animation.Animator
import android.animation.AnimatorListenerAdapter
import android.animation.ValueAnimator
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.ComponentCallbacks
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.res.Configuration
import androidx.core.app.NotificationCompat
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.DisplayMetrics
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.WindowManager
import android.view.animation.AccelerateDecelerateInterpolator
import android.view.animation.BounceInterpolator
import android.view.animation.DecelerateInterpolator
import android.view.animation.OvershootInterpolator
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import com.amiya.pet.R
import com.amiya.pet.model.Operator
import com.amiya.pet.model.PetSkin
import com.amiya.pet.model.PetSkinRepository
import android.widget.HorizontalScrollView
import com.amiya.pet.core.focus.PomodoroMode
import com.amiya.pet.core.focus.PomodoroState
import com.amiya.pet.core.focus.PomodoroTimer
import com.amiya.pet.core.schedule.Course
import com.amiya.pet.core.schedule.ScheduleManager
import com.amiya.pet.core.schedule.ExamManager
import com.amiya.pet.ui.MainActivity
import java.util.Calendar
import java.util.Date
import kotlin.math.hypot

/**
 * 桌面全局悬浮窗桌宠管理器 (Floating Overlay Window)
 *
 * 核心升级（子类一）：
 * 1. 状态机响应系统：
 *    - NORMAL（日常待机）：自然呼吸起伏、周期自然眨眼。
 *    - DRAGGING（提拉悬空）：拖拽放大 1.18x、随手势水平速度摆动、呆萌惊慌差分、松手弹性回弹。
 *    - FOCUSING（专注计时陪伴）：专注星芒眼神、头顶倒计时微徽章（⏳ 24:18）、琥珀金状态指示。
 *    - URGENT（临近排课提醒）：15分钟内上课急迫冷汗差分、头顶弹跳提醒微徽章、烈红警示。
 *    - SLEEPY（深夜打瞌睡）：深夜时段（23:00~06:00）安睡差分、呼吸放缓、微缩 Zzz、轻触揉眼惊醒。
 * 2. 纯净透明 64dp 无金色发光框，支持水平边缘磁吸与半透明避让。
 * 3. 迷你课表速览卡片与支持随时快捷状态测试体验。
 */
object FloatingPetManager {

    private const val PREFS_NAME = "amiya_pet_prefs"
    private const val KEY_FLOATING_ENABLED = "pref_floating_pet_enabled"
    private const val KEY_LAST_X = "pref_floating_last_x"
    private const val KEY_LAST_Y = "pref_floating_last_y"

    enum class PetState(val displayTitle: String) {
        NORMAL("日常陪伴"),
        DRAGGING("提拉悬空"),
        FOCUSING("专注伴学"),
        URGENT("课前提醒"),
        SLEEPY("打盹安睡")
    }

    private var windowManager: WindowManager? = null
    private var rootView: FrameLayout? = null
    private var petContainer: FrameLayout? = null
    private var avatarImageView: ImageView? = null
    private var statusDotView: View? = null
    private var bubbleBadgeView: TextView? = null
    private var miniCardView: LinearLayout? = null
    private var cardTitleView: TextView? = null
    private var wardrobeScrollView: HorizontalScrollView? = null
    private var wardrobeChipsLayout: LinearLayout? = null
    private var isDockedOnRight = false
    private var layoutParams: WindowManager.LayoutParams? = null

    var isShowing: Boolean = false
        private set

    var currentState: PetState = PetState.NORMAL
        private set

    var isCollapsed: Boolean = false
        private set

    var isHiddenForLandscape: Boolean = false
        private set

    var isResting: Boolean = false
        private set

    private var componentCallbacks: ComponentCallbacks? = null
    private const val NOTIFICATION_CHANNEL_REST = "amiya_pet_rest"
    private const val NOTIFICATION_ID_REST = 10099

    private var isDragging = false
    private var isTemporarilyAwake = false
    private var manualTestState: PetState? = null

    private val mainHandler = Handler(Looper.getMainLooper())
    private var breathingAnimator: ValueAnimator? = null
    private var wakeResetRunnable: Runnable? = null

    // 贴边闲置自动半隐藏收纳定时任务 (静止 3 秒后触发)
    private val collapseRunnable = Runnable {
        if (isShowing && !isDragging && miniCardView?.visibility != View.VISIBLE && !isCollapsed) {
            collapseToEdge(animated = true)
        }
    }

    private fun scheduleAutoCollapse(delayMs: Long = 3000L) {
        cancelAutoCollapse()
        if (isShowing && !isDragging && miniCardView?.visibility != View.VISIBLE && !isCollapsed) {
            mainHandler.postDelayed(collapseRunnable, delayMs)
        }
    }

    private fun cancelAutoCollapse() {
        mainHandler.removeCallbacks(collapseRunnable)
    }

    // 自然眨眼定时器
    private val blinkRunnable = object : Runnable {
        override fun run() {
            if (isShowing && currentState == PetState.NORMAL && !isDragging) {
                val ctx = avatarImageView?.context
                if (ctx != null) {
                    val skin = PetSkinRepository.getCurrentSkin(ctx)
                    val blinkRes = skin.blinkResId ?: skin.defaultResId
                    avatarImageView?.setImageResource(blinkRes)
                    mainHandler.postDelayed({
                        if (isShowing && currentState == PetState.NORMAL && !isDragging) {
                            avatarImageView?.setImageResource(skin.defaultResId)
                        }
                    }, 130L)
                }
            }
            val nextDelay = 3500L + (Math.random() * 3500L).toLong()
            mainHandler.postDelayed(this, nextDelay)
        }
    }

    // 状态机实时自适应心跳检测 (1秒间隔)
    private val stateSyncRunnable = object : Runnable {
        override fun run() {
            val ctx = rootView?.context
            if (isShowing && ctx != null && !isDragging) {
                evaluateAndApplyState(ctx)
            }
            mainHandler.postDelayed(this, 1000L)
        }
    }

    private fun getPrefs(context: Context): SharedPreferences {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    fun isFloatingPetEnabled(context: Context): Boolean {
        return getPrefs(context).getBoolean(KEY_FLOATING_ENABLED, false)
    }

    fun setFloatingPetEnabled(context: Context, enabled: Boolean) {
        getPrefs(context).edit().putBoolean(KEY_FLOATING_ENABLED, enabled).apply()
        if (enabled) {
            show(context)
        } else {
            hide(context)
        }
    }

    fun canDrawOverlays(context: Context): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            Settings.canDrawOverlays(context)
        } else {
            true
        }
    }

    fun requestOverlayPermission(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            try {
                val intent = Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:${context.packageName}")
                ).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(intent)
            } catch (_: Exception) {
                val fallbackIntent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(fallbackIntent)
            }
        }
    }

    fun checkAndSync(context: Context) {
        if (isFloatingPetEnabled(context) && canDrawOverlays(context)) {
            show(context)
        } else if (!isFloatingPetEnabled(context) || !canDrawOverlays(context)) {
            hide(context)
        }
    }

    private fun updateWindowLayout() {
        val wm = windowManager ?: return
        val root = rootView ?: return
        val p = layoutParams ?: return
        try {
            wm.updateViewLayout(root, p)
        } catch (_: Exception) {}
    }

    /**
     * 根据悬浮窗吸附屏幕左侧或右侧，动态更新立绘容器、气泡与卡片的重力方向与边距
     */
    private fun updateDockingAlignment(onRight: Boolean) {
        isDockedOnRight = onRight
        val density = rootView?.context?.resources?.displayMetrics?.density ?: 2f
        val petBox = petContainer ?: return
        val card = miniCardView ?: return
        val bubble = bubbleBadgeView ?: return

        val petLp = petBox.layoutParams as? FrameLayout.LayoutParams ?: return
        val cardLp = card.layoutParams as? FrameLayout.LayoutParams ?: return
        val bubbleLp = bubble.layoutParams as? FrameLayout.LayoutParams ?: return

        if (onRight) {
            petLp.gravity = Gravity.TOP or Gravity.END
            petLp.leftMargin = 0
            petLp.rightMargin = 0

            cardLp.gravity = Gravity.TOP or Gravity.END
            cardLp.leftMargin = 0
            cardLp.rightMargin = 0

            bubbleLp.gravity = Gravity.TOP or Gravity.END
            bubbleLp.rightMargin = (6 * density).toInt()
            bubbleLp.leftMargin = 0
        } else {
            petLp.gravity = Gravity.TOP or Gravity.START
            petLp.leftMargin = 0
            petLp.rightMargin = 0

            cardLp.gravity = Gravity.TOP or Gravity.START
            cardLp.leftMargin = 0
            cardLp.rightMargin = 0

            bubbleLp.gravity = Gravity.TOP or Gravity.START
            bubbleLp.leftMargin = (6 * density).toInt()
            bubbleLp.rightMargin = 0
        }
        petBox.layoutParams = petLp
        card.layoutParams = cardLp
        bubble.layoutParams = bubbleLp
    }

    /**
     * 展开/收起迷你卡片，若靠右吸附则智能补偿 WindowManager 的 x 坐标，彻底杜绝出界与立绘跳变
     */
    private fun setCardVisible(visible: Boolean) {
        val wm = windowManager ?: return
        val root = rootView ?: return
        val params = layoutParams ?: return
        val card = miniCardView ?: return
        val density = root.context.resources.displayMetrics.density
        val screenW = root.context.resources.displayMetrics.widthPixels
        val petSize = (64 * density).toInt()
        val cardWidth = (185 * density).toInt()

        if (visible) {
            cancelAutoCollapse()
            (card.getChildAt(1) as? TextView)?.text = getNextClassSummary(root.context)
            card.visibility = View.VISIBLE
            bubbleBadgeView?.visibility = View.GONE
            if (isDockedOnRight) {
                params.x = screenW - cardWidth
            }
        } else {
            card.visibility = View.GONE
            if (isDockedOnRight) {
                params.x = screenW - petSize
            }
            if (currentState != PetState.NORMAL && !isCollapsed) {
                bubbleBadgeView?.visibility = View.VISIBLE
            }
            scheduleAutoCollapse()
        }
        try {
            wm.updateViewLayout(root, params)
        } catch (_: Exception) {}
    }

    /**
     * 边缘贴边半隐藏收纳（防遮挡）：
     * 将悬浮球平滑缩入屏幕边缘，仅露出长兔耳与小半边脸探头守候（约 26dp），透明度降为 0.75f
     */
    fun collapseToEdge(animated: Boolean = true) {
        val root = rootView ?: return
        val wm = windowManager ?: return
        val params = layoutParams ?: return
        if (isCollapsed || isDragging || miniCardView?.visibility == View.VISIBLE) return

        cancelAutoCollapse()
        isCollapsed = true
        val density = root.context.resources.displayMetrics.density
        val screenW = root.context.resources.displayMetrics.widthPixels
        val petSize = (64 * density).toInt()
        val visibleWidth = (26 * density).toInt()

        // 临时隐藏头顶气泡
        bubbleBadgeView?.let { badge ->
            if (badge.visibility == View.VISIBLE) {
                badge.animate().alpha(0f).setDuration(120).withEndAction {
                    badge.visibility = View.GONE
                }.start()
            }
        }

        val targetX = if (isDockedOnRight) {
            screenW - visibleWidth
        } else {
            -(petSize - visibleWidth)
        }

        if (!animated) {
            params.x = targetX
            root.alpha = 0.75f
            try { wm.updateViewLayout(root, params) } catch (_: Exception) {}
            return
        }

        root.animate().alpha(0.75f).setDuration(240).start()
        val anim = ValueAnimator.ofInt(params.x, targetX).apply {
            duration = 260
            interpolator = DecelerateInterpolator()
            addUpdateListener { va ->
                params.x = va.animatedValue as Int
                try { wm.updateViewLayout(root, params) } catch (_: Exception) {}
            }
        }
        anim.start()
    }

    /**
     * 从边缘半隐藏收纳平滑滑出全显（伴随探头小跳跃，恢复 100% 透明度）
     */
    fun expandFromEdge(animated: Boolean = true, onExpanded: (() -> Unit)? = null) {
        val root = rootView ?: return
        val wm = windowManager ?: return
        val params = layoutParams ?: return
        if (!isCollapsed) {
            scheduleAutoCollapse()
            onExpanded?.invoke()
            return
        }

        cancelAutoCollapse()
        isCollapsed = false
        val density = root.context.resources.displayMetrics.density
        val screenW = root.context.resources.displayMetrics.widthPixels
        val petSize = (64 * density).toInt()

        val targetX = if (isDockedOnRight) {
            screenW - petSize
        } else {
            0
        }

        root.animate().alpha(1.0f).setDuration(200).start()

        if (!animated) {
            params.x = targetX
            try { wm.updateViewLayout(root, params) } catch (_: Exception) {}
            evaluateAndApplyState(root.context)
            scheduleAutoCollapse()
            onExpanded?.invoke()
            return
        }

        val anim = ValueAnimator.ofInt(params.x, targetX).apply {
            duration = 260
            interpolator = OvershootInterpolator(1.4f)
            addUpdateListener { va ->
                params.x = va.animatedValue as Int
                try { wm.updateViewLayout(root, params) } catch (_: Exception) {}
            }
            addListener(object : AnimatorListenerAdapter() {
                override fun onAnimationEnd(animation: Animator) {
                    // 探头欢快小跳跃
                    avatarImageView?.let { avatar ->
                        avatar.animate()
                            .translationY(-10f * density)
                            .setDuration(120)
                            .withEndAction {
                                avatar.animate()
                                    .translationY(0f)
                                    .setInterpolator(BounceInterpolator())
                                    .setDuration(240)
                                    .start()
                            }.start()
                    }
                    evaluateAndApplyState(root.context)
                    scheduleAutoCollapse()
                    onExpanded?.invoke()
                }
            })
        }
        anim.start()
    }

    /**
     * 横屏自动淡出避让（玩游戏、全屏看视频免打扰）
     */
    fun hideForLandscape(animated: Boolean = true) {
        val root = rootView ?: return
        if (isHiddenForLandscape || isResting) return
        isHiddenForLandscape = true

        cancelAutoCollapse()
        breathingAnimator?.pause()
        mainHandler.removeCallbacks(blinkRunnable)

        if (miniCardView?.visibility == View.VISIBLE) {
            setCardVisible(false)
        }

        if (!animated) {
            root.visibility = View.GONE
            return
        }

        root.animate()
            .alpha(0f)
            .setDuration(200)
            .withEndAction {
                if (isHiddenForLandscape) {
                    root.visibility = View.GONE
                }
            }.start()
    }

    /**
     * 竖屏自动淡入恢复常驻
     */
    fun restoreFromLandscape(animated: Boolean = true) {
        val root = rootView ?: return
        val wm = windowManager ?: return
        val params = layoutParams ?: return
        if (!isHiddenForLandscape || isResting) return
        isHiddenForLandscape = false

        root.visibility = View.VISIBLE
        val density = root.context.resources.displayMetrics.density
        val screenW = root.context.resources.displayMetrics.widthPixels
        val petSize = (64 * density).toInt()
        val targetX = if (isDockedOnRight) screenW - petSize else 0
        params.x = targetX
        isCollapsed = false
        updateDockingAlignment(isDockedOnRight)
        try { wm.updateViewLayout(root, params) } catch (_: Exception) {}

        breathingAnimator?.resume()
        mainHandler.post(blinkRunnable)
        evaluateAndApplyState(root.context)

        if (!animated) {
            root.alpha = 1.0f
            scheduleAutoCollapse()
            return
        }

        root.alpha = 0f
        root.animate()
            .alpha(1.0f)
            .setDuration(240)
            .withEndAction {
                scheduleAutoCollapse()
            }.start()
    }

    private fun handleOrientationChanged(isLandscape: Boolean) {
        mainHandler.post {
            if (!isShowing || isResting) return@post
            if (isLandscape) {
                hideForLandscape(animated = true)
            } else {
                restoreFromLandscape(animated = true)
            }
        }
    }

    /**
     * 进入免打扰休息模式（阿米娅返回罗德岛休息，并在通知栏提供一键唤醒）
     */
    fun enterRestMode(context: Context) {
        val root = rootView ?: return
        if (isResting) return
        isResting = true

        cancelAutoCollapse()
        breathingAnimator?.pause()
        mainHandler.removeCallbacks(blinkRunnable)

        if (miniCardView?.visibility == View.VISIBLE) {
            setCardVisible(false)
        }

        root.animate()
            .alpha(0f)
            .scaleX(0.7f)
            .scaleY(0.7f)
            .setDuration(250)
            .withEndAction {
                root.visibility = View.GONE
                showRestNotification(context)
            }.start()
    }

    /**
     * 从免打扰休息模式唤醒（恢复桌面常驻，并清除通知）
     */
    fun restoreFromRest(context: Context) {
        val root = rootView ?: return
        if (!isResting) return
        isResting = false

        cancelRestNotification(context)

        root.visibility = View.VISIBLE
        root.alpha = 0f
        root.scaleX = 0.8f
        root.scaleY = 0.8f

        root.animate()
            .alpha(if (isCollapsed) 0.75f else 1.0f)
            .scaleX(1.0f)
            .scaleY(1.0f)
            .setInterpolator(OvershootInterpolator(1.5f))
            .setDuration(280)
            .withEndAction {
                breathingAnimator?.resume()
                mainHandler.post(blinkRunnable)
                evaluateAndApplyState(context)
                scheduleAutoCollapse()
            }.start()
    }

    private fun showRestNotification(context: Context) {
        try {
            val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager ?: return
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val channel = NotificationChannel(
                    NOTIFICATION_CHANNEL_REST,
                    "桌宠状态与关怀",
                    NotificationManager.IMPORTANCE_LOW
                ).apply {
                    description = "阿米娅桌宠休息与唤回通道"
                    setShowBadge(false)
                }
                nm.createNotificationChannel(channel)
            }

            val restoreIntent = Intent(context, PetDebugReceiver::class.java).apply {
                action = "com.amiya.pet.ACTION_RESTORE_PET"
            }
            val pIntent = PendingIntent.getBroadcast(
                context,
                10099,
                restoreIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
            )

            val notif = NotificationCompat.Builder(context, NOTIFICATION_CHANNEL_REST)
                .setSmallIcon(PetSkinRepository.getCurrentSkin(context).defaultResId)
                .setContentTitle("${PetSkinRepository.getCurrentOperator(context).emojiPrefix} ${PetSkinRepository.getCurrentOperator(context).displayName}正在休息中")
                .setContentText("点击此处，立刻让阿米娅返回桌面陪伴您~")
                .setContentIntent(pIntent)
                .setAutoCancel(true)
                .setOngoing(true)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .build()

            nm.notify(NOTIFICATION_ID_REST, notif)
        } catch (e: Exception) {
            android.util.Log.e("FloatingPet", "Failed to show rest notification", e)
        }
    }

    private fun cancelRestNotification(context: Context) {
        try {
            val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager ?: return
            nm.cancel(NOTIFICATION_ID_REST)
        } catch (_: Exception) {}
    }

    /**
     * 显示桌面悬浮窗桌宠
     */
    fun show(context: Context) {
        if (isShowing || !canDrawOverlays(context)) return

        val appContext = context.applicationContext
        val wm = appContext.getSystemService(Context.WINDOW_SERVICE) as? WindowManager ?: return
        windowManager = wm

        val density = appContext.resources.displayMetrics.density
        val petSize = (64 * density).toInt() // 标准 64dp
        val badgeHeight = (22 * density).toInt()
        val screenWidth = appContext.resources.displayMetrics.widthPixels
        val screenHeight = appContext.resources.displayMetrics.heightPixels

        val prefs = getPrefs(appContext)
        val initialX = prefs.getInt(KEY_LAST_X, screenWidth - petSize - (10 * density).toInt())
        val initialY = prefs.getInt(KEY_LAST_Y, (screenHeight * 0.35f).toInt())

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            } else {
                @Suppress("DEPRECATION")
                WindowManager.LayoutParams.TYPE_PHONE
            },
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = initialX
            y = initialY
        }
        layoutParams = params

        // 根容器 (FrameLayout，clipChildren = false 保证头顶气泡与卡片不被截断)
        val root = FrameLayout(appContext).apply {
            clipChildren = false
            clipToPadding = false
        }
        rootView = root

        // 1. 头顶胶囊微气泡 (位于 petContainer 正上方，默认隐藏，有状态时优雅展开)
        val bubbleBadge = TextView(appContext).apply {
            visibility = View.GONE
            textSize = 10f
            paint.isFakeBoldText = true
            setPadding((8 * density).toInt(), (2 * density).toInt(), (8 * density).toInt(), (2 * density).toInt())
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                badgeHeight
            ).apply {
                gravity = Gravity.TOP or Gravity.START
                leftMargin = (6 * density).toInt()
                topMargin = 0
            }
        }
        bubbleBadgeView = bubbleBadge
        root.addView(bubbleBadge)

        // 2. 桌宠实体容器 (固定在 START，零抖动位移)
        val petBox = FrameLayout(appContext).apply {
            clipChildren = false
            clipToPadding = false
            layoutParams = FrameLayout.LayoutParams(petSize, petSize).apply {
                gravity = Gravity.TOP or Gravity.START
                leftMargin = 0
                topMargin = (24 * density).toInt()
            }
        }
        petContainer = petBox

        // 2.1 头像立绘 (标准 64dp · 纯净透明)
        val avatar = ImageView(appContext).apply {
            layoutParams = FrameLayout.LayoutParams(petSize, petSize).apply {
                gravity = Gravity.CENTER
            }
            val initSkin = PetSkinRepository.getCurrentSkin(appContext)
            setImageResource(initSkin.defaultResId)
            scaleType = ImageView.ScaleType.FIT_CENTER
            setPadding((2 * density).toInt(), (2 * density).toInt(), (2 * density).toInt(), (2 * density).toInt())
        }
        avatarImageView = avatar
        petBox.addView(avatar)

        // 2.2 状态呼吸微点 (右下角 8dp)
        val dotSize = (8 * density).toInt()
        val statusDot = View(appContext).apply {
            layoutParams = FrameLayout.LayoutParams(dotSize, dotSize).apply {
                gravity = Gravity.TOP or Gravity.START
                leftMargin = petSize - dotSize - (2 * density).toInt()
                topMargin = petSize - dotSize - (2 * density).toInt()
            }
            background = GradientDrawable().apply {
                shape = GradientDrawable.OVAL
                setColor(Color.parseColor("#4CAF50"))
                setStroke((1.5f * density).toInt(), Color.parseColor("#181D28"))
            }
        }
        statusDotView = statusDot
        petBox.addView(statusDot)

        root.addView(petBox)

        // 3. 展开式战术迷你卡片 (默认隐藏，点击立绘唤出)
        val miniCard = buildMiniCard(appContext, density)
        miniCardView = miniCard
        root.addView(miniCard)

        val initialRight = (initialX + petSize / 2 > screenWidth / 2)
        updateDockingAlignment(initialRight)

        // 手势拖拽、物理反馈与贴边逻辑
        setupTouchListener(root, petBox, avatar, params, petSize, density)

        try {
            wm.addView(root, params)
            isShowing = true

            // 注册横竖屏监听
            if (componentCallbacks == null) {
                val cb = object : ComponentCallbacks {
                    override fun onConfigurationChanged(newConfig: Configuration) {
                        val isLandscape = newConfig.orientation == Configuration.ORIENTATION_LANDSCAPE
                        handleOrientationChanged(isLandscape)
                    }
                    override fun onLowMemory() {}
                }
                appContext.registerComponentCallbacks(cb)
                componentCallbacks = cb
            }

            val curOrientation = appContext.resources.configuration.orientation
            if (curOrientation == Configuration.ORIENTATION_LANDSCAPE) {
                hideForLandscape(animated = false)
            } else {
                // 启动呼吸动画与状态检测
                startBreathingAnimation(false)
                mainHandler.post(blinkRunnable)
                mainHandler.post(stateSyncRunnable)
                evaluateAndApplyState(appContext)
                scheduleAutoCollapse()
            }
        } catch (e: Exception) {
            android.util.Log.e("FloatingPet", "Failed to add floating window", e)
            isShowing = false
        }
    }

    /**
     * 启动闲置自然呼吸微起伏动画
     */
    private fun startBreathingAnimation(isSleepy: Boolean) {
        breathingAnimator?.cancel()
        val avatar = avatarImageView ?: return
        val range = if (isSleepy) 2f else 3.5f
        val duration = if (isSleepy) 3800L else 2400L

        breathingAnimator = ValueAnimator.ofFloat(0f, -range, 0f).apply {
            this.duration = duration
            repeatCount = ValueAnimator.INFINITE
            interpolator = AccelerateDecelerateInterpolator()
            addUpdateListener { va ->
                if (!isDragging) {
                    avatar.translationY = va.animatedValue as Float
                }
            }
        }
        breathingAnimator?.start()
    }

    /**
     * 状态机自适应评估逻辑
     */
    fun evaluateAndApplyState(context: Context) {
        if (isDragging) return

        // 手动测试模式优先 (供用户点选体验所有 5 个表情差分)
        manualTestState?.let { manualState ->
            val (badgeText, badgeColor, badgeBg) = when (manualState) {
                PetState.NORMAL -> Triple("✨ 闲置陪伴", Color.parseColor("#4CAF50"), Color.parseColor("#EE181D28"))
                PetState.DRAGGING -> Triple("💦 别拽我 > <", Color.parseColor("#38BDF8"), Color.parseColor("#E60B2536"))
                PetState.FOCUSING -> Triple("⏳ 专注伴学", Color.parseColor("#F59E0B"), Color.parseColor("#E6291C0E"))
                PetState.URGENT -> Triple("🔔 临近上课", Color.parseColor("#EF4444"), Color.parseColor("#E62B1414"))
                PetState.SLEEPY -> Triple("💤 打盹安睡", Color.parseColor("#8B5CF6"), Color.parseColor("#E6201633"))
            }
            applyState(manualState, badgeText, badgeColor, badgeBg)
            return
        }

        // 1. 检测番茄钟专注状态
        val pomodoroStatus = PomodoroTimer.status.value
        val isPomodoroRunning = pomodoroStatus.state == PomodoroState.RUNNING

        val newState: PetState
        var badgeText: String? = null
        var badgeColor = Color.parseColor("#4CAF50")
        var badgeBg = Color.parseColor("#EE181D28")

        if (isPomodoroRunning) {
            newState = PetState.FOCUSING
            badgeText = "⏳ ${pomodoroStatus.formattedTime}"
            badgeColor = Color.parseColor("#F59E0B")
            badgeBg = Color.parseColor("#E6291C0E")
        } else {
            // 2. 检测排课是否临近 (<= 15 分钟)
            val upcoming = getUpcomingCourseInMinutes(context, 15)
            if (upcoming != null) {
                val (course, minutesLeft) = upcoming
                newState = PetState.URGENT
                val timeStr = if (minutesLeft <= 0) "即将开始" else "${minutesLeft}m后"
                badgeText = "🔔 $timeStr《${course.name.take(4)}》"
                badgeColor = Color.parseColor("#EF4444")
                badgeBg = Color.parseColor("#E62B1414")
            } else {
                // 3. 检测是否为深夜打瞌睡 (23:00~06:00)
                val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
                val isLateNight = (hour >= 23 || hour < 6)
                if (isLateNight && !isTemporarilyAwake) {
                    newState = PetState.SLEEPY
                    badgeText = "Zzz..."
                    badgeColor = Color.parseColor("#8B5CF6")
                    badgeBg = Color.parseColor("#E6201633")
                } else {
                    // 4. 日常状态
                    newState = PetState.NORMAL
                    badgeText = if (isTemporarilyAwake) "博士我醒着呢~" else null
                    badgeColor = Color.parseColor("#4CAF50")
                    badgeBg = Color.parseColor("#EE181D28")
                }
            }
        }

        applyState(newState, badgeText, badgeColor, badgeBg)
    }

    /**
     * 将状态应用到立绘、指示灯、气泡和呼吸频率
     */
    private fun applyState(
        state: PetState,
        badgeText: String?,
        badgeColor: Int,
        badgeBg: Int
    ) {
        val stateChanged = (currentState != state)
        currentState = state

        // 1. 更新立绘资源 (自适应当前皮肤与干员)
        avatarImageView?.let { iv ->
            val skin = PetSkinRepository.getCurrentSkin(iv.context)
            iv.setImageResource(skin.getDrawableForState(state))
        }

        // 2. 更新状态小微点
        statusDotView?.let { dot ->
            val dotColor = when (state) {
                PetState.NORMAL -> Color.parseColor("#4CAF50")
                PetState.DRAGGING -> Color.parseColor("#38BDF8")
                PetState.FOCUSING -> Color.parseColor("#F59E0B")
                PetState.URGENT -> Color.parseColor("#EF4444")
                PetState.SLEEPY -> Color.parseColor("#8B5CF6")
            }
            val density = dot.resources.displayMetrics.density
            dot.background = GradientDrawable().apply {
                shape = GradientDrawable.OVAL
                setColor(dotColor)
                setStroke((1.5f * density).toInt(), Color.parseColor("#181D28"))
            }
        }

        // 3. 更新头顶微气泡徽章
        bubbleBadgeView?.let { badge ->
            if (badgeText != null && miniCardView?.visibility != View.VISIBLE && !isDragging && !isCollapsed) {
                badge.text = badgeText
                badge.setTextColor(badgeColor)
                val density = badge.resources.displayMetrics.density
                badge.background = GradientDrawable().apply {
                    shape = GradientDrawable.RECTANGLE
                    cornerRadius = 10 * density
                    setColor(badgeBg)
                    setStroke((1 * density).toInt(), badgeColor)
                }
                if (badge.visibility != View.VISIBLE) {
                    badge.visibility = View.VISIBLE
                    badge.alpha = 0f
                    badge.scaleX = 0.8f
                    badge.scaleY = 0.8f
                    badge.animate().alpha(1f).scaleX(1f).scaleY(1f).setDuration(200).start()
                    updateWindowLayout()
                }
            } else {
                if (badge.visibility == View.VISIBLE) {
                    badge.animate().alpha(0f).scaleX(0.8f).scaleY(0.8f).setDuration(150)
                        .withEndAction {
                            badge.visibility = View.GONE
                            updateWindowLayout()
                        }
                        .start()
                }
            }
        }

        // 4. 更新迷你卡片标题
        rootView?.context?.let { rootCtx ->
            val curOp = PetSkinRepository.getCurrentOperator(rootCtx)
            val curSkin = PetSkinRepository.getCurrentSkin(rootCtx)
            cardTitleView?.text = "${curOp.emojiPrefix} ${curOp.displayName} (${curSkin.shortName}) · ${state.displayTitle}"
        }

        // 5. 若状态变更，自适应更新呼吸周期
        if (stateChanged) {
            startBreathingAnimation(state == PetState.SLEEPY)
        }
    }

    /**
     * 戳醒安睡状态的阿米娅
     */
    private fun wakeUpPet() {
        val avatar = avatarImageView ?: return
        val density = avatar.resources.displayMetrics.density

        isTemporarilyAwake = true
        wakeResetRunnable?.let { mainHandler.removeCallbacks(it) }
        val runnable = Runnable {
            isTemporarilyAwake = false
            if (isShowing && !isDragging) {
                evaluateAndApplyState(avatar.context)
            }
        }
        wakeResetRunnable = runnable
        mainHandler.postDelayed(runnable, 30_000L) // 唤醒保持 30 秒

        // 惊醒小弹跳
        avatar.animate()
            .translationY(-16f * density)
            .setDuration(140)
            .withEndAction {
                avatar.animate()
                    .translationY(0f)
                    .setInterpolator(BounceInterpolator())
                    .setDuration(320)
                    .start()
            }.start()

        evaluateAndApplyState(avatar.context)
    }

    /**
     * 检查并返回 15 分钟内是否有即将开始的课程
     */
    private fun getUpcomingCourseInMinutes(context: Context, withinMinutes: Int): Pair<Course, Int>? {
        return try {
            ScheduleManager.load(context)
            val cal = Calendar.getInstance()
            val todayCourses = ScheduleManager.getCoursesForDay(cal.time)
            val curTotalMin = cal.get(Calendar.HOUR_OF_DAY) * 60 + cal.get(Calendar.MINUTE)

            for (c in todayCourses) {
                val stStr = ScheduleManager.sections[c.secStart.toString()] ?: continue
                val parts = stStr.split(":")
                val startMin = (parts.getOrNull(0)?.toIntOrNull() ?: continue) * 60 + (parts.getOrNull(1)?.toIntOrNull() ?: 0)
                val diff = startMin - curTotalMin
                if (diff in 0..withinMinutes) {
                    return Pair(c, diff)
                }
            }
            null
        } catch (_: Exception) {
            null
        }
    }

    /**
     * 实时应用新皮肤与新干员形象，更新立绘、状态指示点与卡片标题
     */
    fun applySkin(context: Context, skin: PetSkin) {
        val avatar = avatarImageView ?: return
        avatar.setImageResource(skin.getDrawableForState(currentState))

        val op = PetSkinRepository.getCurrentOperator(context)
        cardTitleView?.text = "${op.emojiPrefix} ${op.displayName} (${skin.shortName}) · ${currentState.displayTitle}"

        statusDotView?.let { dot ->
            val density = context.resources.displayMetrics.density
            val dotColor = when (currentState) {
                PetState.NORMAL -> Color.parseColor(skin.themeColor)
                PetState.DRAGGING -> Color.parseColor("#38BDF8")
                PetState.FOCUSING -> Color.parseColor("#F59E0B")
                PetState.URGENT -> Color.parseColor("#EF4444")
                PetState.SLEEPY -> Color.parseColor("#8B5CF6")
            }
            dot.background = GradientDrawable().apply {
                shape = GradientDrawable.OVAL
                setColor(dotColor)
                setStroke((1.5f * density).toInt(), Color.parseColor("#181D28"))
            }
        }

        refreshWardrobeChips(context)
        updateWindowLayout()
        com.amiya.pet.widget.ScheduleWidgetProvider.sendUpdateBroadcast(context)
    }

    /**
     * 播放换装成功的欢快轻盈小跳跃动效
     */
    fun playSkinBounceAnimation() {
        val avatar = avatarImageView ?: return
        val density = avatar.resources.displayMetrics.density
        avatar.animate()
            .scaleX(1.18f)
            .scaleY(1.18f)
            .translationY(-14f * density)
            .setDuration(130)
            .withEndAction {
                avatar.animate()
                    .scaleX(1.0f)
                    .scaleY(1.0f)
                    .translationY(0f)
                    .setInterpolator(BounceInterpolator())
                    .setDuration(280)
                    .start()
            }.start()
    }

    private fun toggleWardrobe() {
        val scroll = wardrobeScrollView ?: return
        val ctx = scroll.context
        if (scroll.visibility == View.VISIBLE) {
            scroll.visibility = View.GONE
        } else {
            wardrobeChipsLayout?.let { populateWardrobeChips(ctx, it, ctx.resources.displayMetrics.density) }
            scroll.visibility = View.VISIBLE
        }
        updateWindowLayout()
    }

    private fun populateWardrobeChips(context: Context, container: LinearLayout, density: Float) {
        container.removeAllViews()
        val allSkins = PetSkinRepository.getAllSkins()
        val currentSkin = PetSkinRepository.getCurrentSkin(context)

        for ((op, skin) in allSkins) {
            val isSelected = (skin.id == currentSkin.id)
            val chip = TextView(context).apply {
                text = "${op.emojiPrefix} ${skin.shortName}"
                textSize = 9.5f
                paint.isFakeBoldText = isSelected
                setTextColor(if (isSelected) Color.parseColor("#FFFFFF") else Color.parseColor("#94A3B8"))
                setPadding((6 * density).toInt(), (3 * density).toInt(), (6 * density).toInt(), (3 * density).toInt())
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply {
                    rightMargin = (5 * density).toInt()
                }
                background = GradientDrawable().apply {
                    shape = GradientDrawable.RECTANGLE
                    cornerRadius = 6 * density
                    if (isSelected) {
                        setColor(Color.parseColor(skin.themeColor))
                        setStroke((1 * density).toInt(), Color.parseColor("#FFFFFF"))
                    } else {
                        setColor(Color.parseColor("#262E3F"))
                        setStroke((0.8f * density).toInt(), Color.parseColor("#3B455B"))
                    }
                }
                setOnClickListener {
                    val switched = PetSkinRepository.switchSkin(context, skin.id)
                    applySkin(context, switched)
                    playSkinBounceAnimation()
                }
            }
            container.addView(chip)
        }
    }

    private fun refreshWardrobeChips(context: Context) {
        wardrobeChipsLayout?.let { populateWardrobeChips(context, it, context.resources.displayMetrics.density) }
    }


    /**
     * 构建点击弹出的极简紧凑迷你卡片 (课表速览 + 快捷操作，已剔除冗余测试控件)
     */
    private fun buildMiniCard(context: Context, density: Float): LinearLayout {
        val cardW = (185 * density).toInt()
        val cardLayout = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            visibility = View.GONE
            layoutParams = FrameLayout.LayoutParams(cardW, FrameLayout.LayoutParams.WRAP_CONTENT).apply {
                gravity = Gravity.TOP or Gravity.START
                topMargin = (90 * density).toInt()
            }
            background = GradientDrawable().apply {
                shape = GradientDrawable.RECTANGLE
                cornerRadius = 14 * density
                setColor(Color.parseColor("#F2141822"))
                setStroke((0.8f * density).toInt(), Color.parseColor("#354056"))
            }
            setPadding((10 * density).toInt(), (8 * density).toInt(), (10 * density).toInt(), (8 * density).toInt())
        }

        // 顶栏：状态标题 + 极简关闭叉号
        val headerRow = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )

            val titleTv = TextView(context).apply {
                text = "🐰 阿米娅 · ${currentState.displayTitle}"
                textSize = 11.5f
                setTextColor(Color.parseColor("#FFFFFF"))
                paint.isFakeBoldText = true
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            }
            cardTitleView = titleTv
            addView(titleTv)

            val closeBtn = TextView(context).apply {
                text = "✕"
                textSize = 12f
                setTextColor(Color.parseColor("#94A3B8"))
                setPadding((6 * density).toInt(), (2 * density).toInt(), (4 * density).toInt(), (2 * density).toInt())
                setOnClickListener {
                    setCardVisible(false)
                }
            }
            addView(closeBtn)
        }
        cardLayout.addView(headerRow)

        // 下一节课卡片 / 状态信息 (紧凑圆角气泡，点击可直接直达课表)
        val classTv = TextView(context).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                topMargin = (5 * density).toInt()
                bottomMargin = (6 * density).toInt()
            }
            textSize = 10.5f
            setTextColor(Color.parseColor("#CBD5E1"))
            background = GradientDrawable().apply {
                shape = GradientDrawable.RECTANGLE
                cornerRadius = 7 * density
                setColor(Color.parseColor("#1AFFFFFF"))
            }
            setPadding((7 * density).toInt(), (5 * density).toInt(), (7 * density).toInt(), (5 * density).toInt())
            text = getNextClassSummary(context)
            setOnClickListener {
                val appIntent = Intent(context, MainActivity::class.java).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                }
                context.startActivity(appIntent)
                setCardVisible(false)
            }
        }
        cardLayout.addView(classTv)

        // 展开式微型衣橱换装面板 (HorizontalScrollView，点击底栏换装展开)
        val wardrobeScroll = HorizontalScrollView(context).apply {
            visibility = View.GONE
            overScrollMode = View.OVER_SCROLL_NEVER
            isHorizontalScrollBarEnabled = false
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                topMargin = (2 * density).toInt()
                bottomMargin = (5 * density).toInt()
            }
        }
        val wardrobeLayout = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(0, (2 * density).toInt(), 0, (2 * density).toInt())
        }
        wardrobeScroll.addView(wardrobeLayout)
        wardrobeScrollView = wardrobeScroll
        wardrobeChipsLayout = wardrobeLayout
        populateWardrobeChips(context, wardrobeLayout, density)
        cardLayout.addView(wardrobeScroll)

        // 底部极简操作：进入课表、休息与关闭桌宠
        val actionRow = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )

            val openAppBtn = TextView(context).apply {
                text = "进入课表 ➔"
                textSize = 10f
                setTextColor(Color.parseColor("#38BDF8"))
                paint.isFakeBoldText = true
                setPadding((2 * density).toInt(), (2 * density).toInt(), (4 * density).toInt(), (2 * density).toInt())
                setOnClickListener {
                    val appIntent = Intent(context, MainActivity::class.java).apply {
                        flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                    }
                    context.startActivity(appIntent)
                    setCardVisible(false)
                }
            }
            addView(openAppBtn)

            val spacer = View(context).apply {
                layoutParams = LinearLayout.LayoutParams(0, 1, 1f)
            }
            addView(spacer)

            val dressBtn = TextView(context).apply {
                text = "换装 👗"
                textSize = 10f
                setTextColor(Color.parseColor("#EC4899"))
                setPadding((3 * density).toInt(), (2 * density).toInt(), (3 * density).toInt(), (2 * density).toInt())
                setOnClickListener {
                    toggleWardrobe()
                }
            }
            addView(dressBtn)

            val restBtn = TextView(context).apply {
                text = "休息 💤"
                textSize = 10f
                setTextColor(Color.parseColor("#A78BFA"))
                setPadding((4 * density).toInt(), (2 * density).toInt(), (4 * density).toInt(), (2 * density).toInt())
                setOnClickListener {
                    enterRestMode(context)
                }
            }
            addView(restBtn)

            val closePetBtn = TextView(context).apply {
                text = "关闭"
                textSize = 10f
                setTextColor(Color.parseColor("#94A3B8"))
                setPadding((4 * density).toInt(), (2 * density).toInt(), (2 * density).toInt(), (2 * density).toInt())
                setOnClickListener {
                    setFloatingPetEnabled(context, false)
                }
            }
            addView(closePetBtn)
        }
        cardLayout.addView(actionRow)

        return cardLayout
    }

    /**
     * 获取下一节课速览文本
     */
    private fun getNextClassSummary(context: Context): String {
        return try {
            ScheduleManager.load(context)
            val cal = Calendar.getInstance()
            val todayCourses = ScheduleManager.getCoursesForDay(cal.time)

            ExamManager.load(context)
            val nextExam = ExamManager.getNextUpcomingExam()

            if (ScheduleManager.courses.isEmpty()) {
                if (nextExam != null) {
                    val (days, hours, _) = ExamManager.getCountdownParts(nextExam.examTimeMillis)
                    val timeTip = if (days > 0) "剩 $days 天 $hours 小时" else "仅剩 $hours 小时"
                    val locStr = if (nextExam.location.isNotEmpty()) "📍${nextExam.location}" else ""
                    val seatStr = if (nextExam.seatNumber.isNotEmpty()) " (座号 ${nextExam.seatNumber})" else ""
                    "🎯 备战期末 · $timeTip\n《${nextExam.title}》$locStr$seatStr"
                } else {
                    "📚 暂无课表数据，点击进入 App 导入"
                }
            } else if (todayCourses.isEmpty()) {
                if (nextExam != null) {
                    val (days, hours, _) = ExamManager.getCountdownParts(nextExam.examTimeMillis)
                    val timeTip = if (days > 0) "剩 $days 天 $hours 小时" else "仅剩 $hours 小时"
                    val locStr = if (nextExam.location.isNotEmpty()) "📍${nextExam.location}" else ""
                    val seatStr = if (nextExam.seatNumber.isNotEmpty()) " (座号 ${nextExam.seatNumber})" else ""
                    "🎯 今日无课 · 备战期末 $timeTip\n《${nextExam.title}》$locStr$seatStr"
                } else {
                    "📅 今日全天无排课，好好放松吧~"
                }
            } else {
                val curTotalMin = cal.get(Calendar.HOUR_OF_DAY) * 60 + cal.get(Calendar.MINUTE)
                val next = todayCourses.firstOrNull { c ->
                    val stStr = ScheduleManager.sections[c.secEnd.toString()] ?: "08:00"
                    val parts = stStr.split(":")
                    val etMin = (parts.getOrNull(0)?.toIntOrNull() ?: 8) * 60 + (parts.getOrNull(1)?.toIntOrNull() ?: 0) + 45
                    etMin > curTotalMin
                }
                if (next != null) {
                    val st = ScheduleManager.sections[next.secStart.toString()] ?: ""
                    val room = next.room.ifEmpty { "待定教室" }
                    "🔔 下一节 $st\n《${next.name}》📍$room"
                } else {
                    if (nextExam != null) {
                        val (days, hours, _) = ExamManager.getCountdownParts(nextExam.examTimeMillis)
                        val timeTip = if (days > 0) "剩 $days 天" else "仅剩 $hours 小时"
                        "🎉 今日结课 · 备战期末 ($timeTip)\n《${nextExam.title}》📍${nextExam.location}"
                    } else {
                        "🎉 今日课程已全部结束，博士辛苦啦！"
                    }
                }
            }
        } catch (_: Exception) {
            "🐰 阿米娅正在守护您的日程"
        }
    }

    /**
     * 配置手势监听：自由拖动提拉悬空、点击展开菜单与唤醒、松手磁吸贴边与弹性 Overshoot
     */
    private fun setupTouchListener(
        root: FrameLayout,
        petBox: FrameLayout,
        avatar: ImageView,
        params: WindowManager.LayoutParams,
        petSize: Int,
        density: Float
    ) {
        val touchSlop = ViewConfiguration.get(root.context).scaledTouchSlop
        var initialX = 0
        var initialY = 0
        var initialTouchX = 0f
        var initialTouchY = 0f
        var lastRawX = 0f
        var wasCollapsed = false

        petBox.setOnTouchListener { _, event ->
            val wm = windowManager ?: return@setOnTouchListener false
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    cancelAutoCollapse()
                    wasCollapsed = isCollapsed
                    initialX = params.x
                    initialY = params.y
                    initialTouchX = event.rawX
                    initialTouchY = event.rawY
                    lastRawX = event.rawX
                    isDragging = false
                    root.alpha = 1.0f

                    if (currentState == PetState.SLEEPY) {
                        wakeUpPet()
                    }
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    val dxTotal = (event.rawX - initialTouchX).toInt()
                    val dyTotal = (event.rawY - initialTouchY).toInt()

                    if (hypot(dxTotal.toDouble(), dyTotal.toDouble()) > touchSlop) {
                        if (!isDragging) {
                            isDragging = true
                            isCollapsed = false
                            cancelAutoCollapse()
                            setCardVisible(false)
                            updateDockingAlignment(false)
                            breathingAnimator?.pause()

                            // 切换为被提拉悬空表情
                            val dragSkin = PetSkinRepository.getCurrentSkin(root.context)
                            avatar.setImageResource(dragSkin.getDrawableForState(PetState.DRAGGING))
                            // 悬空提拉放大 1.18x
                            avatar.animate().scaleX(1.18f).scaleY(1.18f).setDuration(120).start()
                            statusDotView?.background = GradientDrawable().apply {
                                shape = GradientDrawable.OVAL
                                setColor(Color.parseColor("#38BDF8"))
                                setStroke((1.5f * density).toInt(), Color.parseColor("#181D28"))
                            }
                            updateWindowLayout()
                        }

                        // 水平拖动摇摆物理反馈
                        val dxStep = event.rawX - lastRawX
                        lastRawX = event.rawX
                        val targetRot = (-dxStep * 0.22f).coerceIn(-20f, 20f)
                        avatar.rotation = targetRot

                        val screenH = root.context.resources.displayMetrics.heightPixels
                        val minY = (20 * density).toInt()
                        val maxY = screenH - petSize - (50 * density).toInt()

                        params.x = initialX + dxTotal
                        params.y = (initialY + dyTotal).coerceIn(minY, maxY)
                        try {
                            wm.updateViewLayout(root, params)
                        } catch (_: Exception) {}
                    }
                    true
                }
                MotionEvent.ACTION_UP -> {
                    if (!isDragging) {
                        if (wasCollapsed) {
                            // 若之前处于贴边收纳状态，轻触第一下为唤醒滑出探头，不立刻糊卡片
                            expandFromEdge(animated = true)
                        } else {
                            // 正常全显状态下的轻触
                            if (currentState == PetState.SLEEPY) {
                                wakeUpPet()
                            } else {
                                // 欢快小弹跳
                                avatar.animate()
                                    .translationY(-12f * density)
                                    .setDuration(120)
                                    .withEndAction {
                                        avatar.animate()
                                            .translationY(0f)
                                            .setInterpolator(BounceInterpolator())
                                            .setDuration(260)
                                            .start()
                                    }.start()
                            }

                            // 展开/隐藏迷你卡片
                            val willShow = (miniCardView?.visibility != View.VISIBLE)
                            setCardVisible(willShow)
                        }
                    } else {
                        // 拖拽松手：弹性 Overshoot 弹簧回正
                        isDragging = false
                        avatar.animate()
                            .scaleX(1.0f)
                            .scaleY(1.0f)
                            .rotation(0f)
                            .setInterpolator(OvershootInterpolator(2.2f))
                            .setDuration(320)
                            .start()

                        breathingAnimator?.resume()

                        // 水平磁吸贴边
                        val screenW = root.context.resources.displayMetrics.widthPixels
                        val targetX = if (params.x + petSize / 2 < screenW / 2) {
                            0
                        } else {
                            screenW - petSize
                        }
                        val dockRight = (targetX > 0)

                        val animator = ValueAnimator.ofInt(params.x, targetX).apply {
                            duration = 260
                            interpolator = DecelerateInterpolator()
                            addUpdateListener { va ->
                                params.x = va.animatedValue as Int
                                try {
                                    wm.updateViewLayout(root, params)
                                } catch (_: Exception) {}
                            }
                            addListener(object : AnimatorListenerAdapter() {
                                override fun onAnimationEnd(animation: Animator) {
                                    updateDockingAlignment(dockRight)
                                    evaluateAndApplyState(root.context)
                                    scheduleAutoCollapse()
                                }
                            })
                        }
                        animator.start()

                        getPrefs(root.context).edit()
                            .putInt(KEY_LAST_X, targetX)
                            .putInt(KEY_LAST_Y, params.y)
                            .apply()
                    }
                    true
                }
                MotionEvent.ACTION_CANCEL -> {
                    if (isDragging) {
                        isDragging = false
                        avatar.animate().scaleX(1.0f).scaleY(1.0f).rotation(0f).start()
                        breathingAnimator?.resume()
                        scheduleAutoCollapse()
                    }
                    false
                }
                else -> false
            }
        }
    }

    /**
     * 隐藏并彻底释放桌面悬浮窗与定时器
     */
    /**
     * 处理来自 ADB 调试广播 (com.amiya.pet.TEST_ACTION) 的毫秒级指令注入
     */
    fun handleDebugCommand(context: Context, intent: Intent) {
        val cmd = intent.getStringExtra("cmd")?.lowercase() ?: ""
        val stateStr = (intent.getStringExtra("state") ?: intent.getStringExtra("status"))?.uppercase()
        val pos = intent.getStringExtra("pos")?.lowercase()

        mainHandler.post {
            // 1. 显隐控制
            if (cmd == "show") {
                setFloatingPetEnabled(context, true)
                return@post
            }
            if (cmd == "hide") {
                setFloatingPetEnabled(context, false)
                return@post
            }

            if (!isShowing) {
                setFloatingPetEnabled(context, true)
            }

            // 2. 状态切换
            if (!stateStr.isNullOrEmpty() || cmd == "state") {
                when (stateStr) {
                    "NORMAL" -> manualTestState = PetState.NORMAL
                    "DRAGGING" -> manualTestState = PetState.DRAGGING
                    "FOCUSING" -> manualTestState = PetState.FOCUSING
                    "URGENT" -> manualTestState = PetState.URGENT
                    "SLEEPY" -> manualTestState = PetState.SLEEPY
                    "AUTO", "RESET", "CLEAR" -> manualTestState = null
                    else -> manualTestState = null
                }
                evaluateAndApplyState(context)
            }

            // 2.5 换装与多干员支持
            val skinArg = intent.getStringExtra("skin")?.trim()
            if (!skinArg.isNullOrBlank()) {
                val newSkin = PetSkinRepository.switchSkin(context, skinArg)
                applySkin(context, newSkin)
                playSkinBounceAnimation()
            }

            val opArg = intent.getStringExtra("operator")?.trim()
            if (!opArg.isNullOrBlank()) {
                val newSkin = PetSkinRepository.switchOperator(context, opArg)
                applySkin(context, newSkin)
                playSkinBounceAnimation()
            }

            // 3. 卡片、收纳与避让控制
            when (cmd) {
                "wardrobe", "dress" -> toggleWardrobe()
                "open_card", "card_open" -> setCardVisible(true)
                "close_card", "card_close" -> setCardVisible(false)
                "toggle_card", "card_toggle" -> setCardVisible(miniCardView?.visibility != View.VISIBLE)
                "collapse", "dock" -> collapseToEdge(animated = true)
                "expand", "undock" -> expandFromEdge(animated = true)
                "toggle_collapse" -> if (isCollapsed) expandFromEdge(animated = true) else collapseToEdge(animated = true)
                "landscape", "orient_landscape" -> hideForLandscape(animated = true)
                "portrait", "orient_portrait" -> restoreFromLandscape(animated = true)
                "rest", "snooze" -> enterRestMode(context)
                "wake", "restore" -> {
                    if (isResting) restoreFromRest(context)
                    else if (isHiddenForLandscape) restoreFromLandscape(animated = true)
                    else wakeUpPet()
                }
                "bounce" -> {
                    avatarImageView?.let { avatar ->
                        val density = avatar.resources.displayMetrics.density
                        avatar.animate()
                            .translationY(-16f * density)
                            .setDuration(130)
                            .withEndAction {
                                avatar.animate()
                                    .translationY(0f)
                                    .setInterpolator(BounceInterpolator())
                                    .setDuration(300)
                                    .start()
                            }.start()
                    }
                }
            }

            // 4. 坐标与边缘吸附控制
            val root = rootView
            val params = layoutParams
            val wm = windowManager
            if (root != null && params != null && wm != null) {
                val density = root.context.resources.displayMetrics.density
                val screenW = root.context.resources.displayMetrics.widthPixels
                val petSize = (64 * density).toInt()

                if (pos == "left") {
                    params.x = 0
                    isCollapsed = false
                    updateDockingAlignment(false)
                    try { wm.updateViewLayout(root, params) } catch (_: Exception) {}
                    scheduleAutoCollapse()
                } else if (pos == "right") {
                    params.x = screenW - petSize
                    isCollapsed = false
                    updateDockingAlignment(true)
                    try { wm.updateViewLayout(root, params) } catch (_: Exception) {}
                    scheduleAutoCollapse()
                } else {
                    val customX = intent.getIntExtra("x", -1)
                    val customY = intent.getIntExtra("y", -1)
                    var changed = false
                    if (customX >= 0) {
                        params.x = customX
                        changed = true
                    }
                    if (customY >= 0) {
                        params.y = customY
                        changed = true
                    }
                    if (changed) {
                        try { wm.updateViewLayout(root, params) } catch (_: Exception) {}
                    }
                }
            }
            android.util.Log.i("PetDebug", "Handled cmd=$cmd, state=$stateStr, pos=$pos, isCollapsed=$isCollapsed, isHiddenForLandscape=$isHiddenForLandscape, isResting=$isResting")
        }
    }

    fun hide(context: Context) {
        if (!isShowing) return
        try {
            cancelAutoCollapse()
            isCollapsed = false
            isHiddenForLandscape = false
            isResting = false
            cancelRestNotification(context)
            componentCallbacks?.let { cb ->
                try { context.applicationContext.unregisterComponentCallbacks(cb) } catch (_: Exception) {}
                componentCallbacks = null
            }
            breathingAnimator?.cancel()
            breathingAnimator = null
            mainHandler.removeCallbacks(blinkRunnable)
            mainHandler.removeCallbacks(stateSyncRunnable)
            wakeResetRunnable?.let { mainHandler.removeCallbacks(it) }

            rootView?.let { windowManager?.removeView(it) }
        } catch (_: Exception) {
        } finally {
            rootView = null
            petContainer = null
            avatarImageView = null
            statusDotView = null
            bubbleBadgeView = null
            miniCardView = null
            cardTitleView = null
            wardrobeScrollView = null
            wardrobeChipsLayout = null
            layoutParams = null
            isShowing = false
            manualTestState = null
            isTemporarilyAwake = false
        }
    }

    /**
     * 收到来自电脑端的跨端快传投递时，桌宠欢快跳动并提示气泡
     */
    fun showTacticalMessage(context: Context, text: String) {
        mainHandler.post {
            if (isCollapsed) {
                expandFromEdge(animated = true)
            }
            petContainer?.animate()
                ?.translationY(-24f)
                ?.setDuration(160)
                ?.withEndAction {
                    petContainer?.animate()?.translationY(0f)?.setDuration(160)?.start()
                }?.start()
            val preview = if (text.length > 30) text.substring(0, 30) + "…" else text
            Toast.makeText(context, "📥 收到来自电脑的快传：\n「$preview」\n已存入剪贴板！", Toast.LENGTH_LONG).show()
        }
    }
}
