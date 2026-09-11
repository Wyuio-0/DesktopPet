package com.amiya.pet.floating

import android.animation.ValueAnimator
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.util.DisplayMetrics
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.WindowManager
import android.view.animation.DecelerateInterpolator
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import com.amiya.pet.R
import com.amiya.pet.core.schedule.ScheduleManager
import com.amiya.pet.ui.MainActivity
import java.util.Calendar
import java.util.Date
import kotlin.math.hypot

/**
 * 桌面全局悬浮窗桌宠管理器 (Floating Overlay Window)
 *
 * 特性：
 * - 纯净透明立绘（无金色发光外框、无黄色边框干扰）
 * - 标准 64dp 尺寸
 * - 暂时不接入声音（静音陪伴）
 * - 自由全屏拖拽跟手与边缘磁吸半透明避让
 * - 自主随时开启/关闭，状态本地持久化
 * - 轻触展开迷你课表速览卡片与快速关闭
 */
object FloatingPetManager {

    private const val PREFS_NAME = "amiya_pet_prefs"
    private const val KEY_FLOATING_ENABLED = "pref_floating_pet_enabled"
    private const val KEY_LAST_X = "pref_floating_last_x"
    private const val KEY_LAST_Y = "pref_floating_last_y"

    private var windowManager: WindowManager? = null
    private var rootView: FrameLayout? = null
    private var miniCardView: LinearLayout? = null
    private var avatarImageView: ImageView? = null
    private var layoutParams: WindowManager.LayoutParams? = null

    var isShowing: Boolean = false
        private set

    private fun getPrefs(context: Context): SharedPreferences {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    /**
     * 读取用户是否开启了桌面悬浮球
     */
    fun isFloatingPetEnabled(context: Context): Boolean {
        return getPrefs(context).getBoolean(KEY_FLOATING_ENABLED, false)
    }

    /**
     * 设置并持久化悬浮球开关
     */
    fun setFloatingPetEnabled(context: Context, enabled: Boolean) {
        getPrefs(context).edit().putBoolean(KEY_FLOATING_ENABLED, enabled).apply()
        if (enabled) {
            show(context)
        } else {
            hide(context)
        }
    }

    /**
     * 检查系统悬浮窗权限 (Android 6.0+)
     */
    fun canDrawOverlays(context: Context): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            Settings.canDrawOverlays(context)
        } else {
            true
        }
    }

    /**
     * 引导跳转至系统悬浮窗授权设置界面
     */
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
            } catch (e: Exception) {
                val fallbackIntent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(fallbackIntent)
            }
        }
    }

    /**
     * 页面恢复或启动时检查并同步显示状态
     */
    fun checkAndSync(context: Context) {
        if (isFloatingPetEnabled(context) && canDrawOverlays(context)) {
            show(context)
        } else if (!isFloatingPetEnabled(context) || !canDrawOverlays(context)) {
            hide(context)
        }
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

        // 创建根容器
        val root = FrameLayout(appContext).apply {
            clipChildren = false
            clipToPadding = false
        }
        rootView = root

        // 1. 头像容器 (标准 64dp · 纯净透明立绘 · 无金色发光框)
        val avatar = ImageView(appContext).apply {
            layoutParams = FrameLayout.LayoutParams(petSize, petSize).apply {
                gravity = Gravity.TOP or Gravity.START
            }
            setImageResource(R.drawable.avatar_amiya)
            scaleType = ImageView.ScaleType.FIT_CENTER
            // 轻柔环境底影提升立体感，无任何金边
            setPadding((2 * density).toInt(), (2 * density).toInt(), (2 * density).toInt(), (2 * density).toInt())
        }
        avatarImageView = avatar
        root.addView(avatar)

        // 2. 状态小微点 (右下角 6dp 绿色呼吸点)
        val statusDot = View(appContext).apply {
            val dotSize = (8 * density).toInt()
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
        root.addView(statusDot)

        // 3. 展开式战术迷你卡片 (默认隐藏，点击唤出)
        val miniCard = buildMiniCard(appContext, density)
        miniCardView = miniCard
        root.addView(miniCard)

        // 手势拖拽与贴边逻辑
        setupTouchListener(root, avatar, params, petSize, density)

        try {
            wm.addView(root, params)
            isShowing = true
        } catch (e: Exception) {
            android.util.Log.e("FloatingPet", "Failed to add floating window", e)
            isShowing = false
        }
    }

    /**
     * 构建点击弹出的迷你信息卡片 (课表速览 + 快捷操作)
     */
    private fun buildMiniCard(context: Context, density: Float): LinearLayout {
        return LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            visibility = View.GONE
            val cardW = (230 * density).toInt()
            layoutParams = FrameLayout.LayoutParams(cardW, FrameLayout.LayoutParams.WRAP_CONTENT).apply {
                gravity = Gravity.TOP or Gravity.START
                topMargin = (68 * density).toInt()
            }
            background = GradientDrawable().apply {
                shape = GradientDrawable.RECTANGLE
                cornerRadius = 16 * density
                setColor(Color.parseColor("#EE181D28"))
                setStroke((1 * density).toInt(), Color.parseColor("#354056"))
            }
            setPadding((12 * density).toInt(), (10 * density).toInt(), (12 * density).toInt(), (10 * density).toInt())

            // 顶栏：标题与关闭小卡片
            val headerRow = LinearLayout(context).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                )

                val titleTv = TextView(context).apply {
                    text = "🐰 阿米娅桌面桌宠"
                    textSize = 12f
                    setTextColor(Color.parseColor("#FFFFFF"))
                    paint.isFakeBoldText = true
                    layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
                }
                addView(titleTv)

                val closeBtn = TextView(context).apply {
                    text = "✕"
                    textSize = 12f
                    setTextColor(Color.parseColor("#94A3B8"))
                    setPadding((6 * density).toInt(), (2 * density).toInt(), (6 * density).toInt(), (2 * density).toInt())
                    setOnClickListener {
                        visibility = View.GONE
                    }
                }
                addView(closeBtn)
            }
            addView(headerRow)

            // 下一节课卡片
            val classTv = TextView(context).apply {
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply {
                    topMargin = (6 * density).toInt()
                    bottomMargin = (6 * density).toInt()
                }
                textSize = 11f
                setTextColor(Color.parseColor("#CBD5E1"))
                background = GradientDrawable().apply {
                    shape = GradientDrawable.RECTANGLE
                    cornerRadius = 8 * density
                    setColor(Color.parseColor("#26FFFFFF"))
                }
                setPadding((8 * density).toInt(), (6 * density).toInt(), (8 * density).toInt(), (6 * density).toInt())
                text = getNextClassSummary(context)
            }
            addView(classTv)

            // 底部操作区
            val actionRow = LinearLayout(context).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                )

                val openAppBtn = TextView(context).apply {
                    text = "📱 进入课表"
                    textSize = 11f
                    setTextColor(Color.parseColor("#38BDF8"))
                    paint.isFakeBoldText = true
                    setPadding((4 * density).toInt(), (4 * density).toInt(), (8 * density).toInt(), (4 * density).toInt())
                    setOnClickListener {
                        val appIntent = Intent(context, MainActivity::class.java).apply {
                            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                        }
                        context.startActivity(appIntent)
                        visibility = View.GONE
                    }
                }
                addView(openAppBtn)

                val spacer = View(context).apply {
                    layoutParams = LinearLayout.LayoutParams(0, 1, 1f)
                }
                addView(spacer)

                val closePetBtn = TextView(context).apply {
                    text = "关闭悬浮球"
                    textSize = 11f
                    setTextColor(Color.parseColor("#F87171"))
                    setPadding((6 * density).toInt(), (4 * density).toInt(), (4 * density).toInt(), (4 * density).toInt())
                    setOnClickListener {
                        setFloatingPetEnabled(context, false)
                    }
                }
                addView(closePetBtn)
            }
            addView(actionRow)
        }
    }

    /**
     * 获取下一节课速览文本
     */
    private fun getNextClassSummary(context: Context): String {
        return try {
            ScheduleManager.load(context)
            val cal = Calendar.getInstance()
            val dayOfWeek = cal.get(Calendar.DAY_OF_WEEK)
            val todayWeekday = if (dayOfWeek == Calendar.SUNDAY) 7 else dayOfWeek - 1
            val weekNo = ScheduleManager.getWeekNo() ?: 1
            val todayCourses = ScheduleManager.getCoursesOn(todayWeekday, weekNo)

            if (ScheduleManager.courses.isEmpty()) {
                "📚 暂无课表数据，点击进入 App 导入"
            } else if (todayCourses.isEmpty()) {
                "📅 今日全天无排课，好好放松吧~"
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
                    "🎉 今日课程已全部结束，博士辛苦啦！"
                }
            }
        } catch (_: Exception) {
            "🐰 阿米娅正在守护您的日程"
        }
    }

    /**
     * 配置手势监听：自由拖动、点击展开菜单、松手磁吸贴边与半透明避让
     */
    private fun setupTouchListener(
        root: FrameLayout,
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
        var isDragging = false

        avatar.setOnTouchListener { _, event ->
            val wm = windowManager ?: return@setOnTouchListener false
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    initialX = params.x
                    initialY = params.y
                    initialTouchX = event.rawX
                    initialTouchY = event.rawY
                    isDragging = false
                    root.alpha = 1.0f // 触摸时恢复完全清晰
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = (event.rawX - initialTouchX).toInt()
                    val dy = (event.rawY - initialTouchY).toInt()

                    if (hypot(dx.toDouble(), dy.toDouble()) > touchSlop) {
                        if (!isDragging) {
                            isDragging = true
                            miniCardView?.visibility = View.GONE
                        }
                        params.x = initialX + dx
                        params.y = initialY + dy
                        try {
                            wm.updateViewLayout(root, params)
                        } catch (_: Exception) {}
                    }
                    true
                }
                MotionEvent.ACTION_UP -> {
                    if (!isDragging) {
                        // 轻触点击：展开/隐藏卡片（静音，不播放音频）
                        miniCardView?.let { card ->
                            if (card.visibility == View.VISIBLE) {
                                card.visibility = View.GONE
                            } else {
                                // 刷新一次课表文本
                                (card.getChildAt(1) as? TextView)?.text = getNextClassSummary(root.context)
                                card.visibility = View.VISIBLE
                            }
                        }
                    } else {
                        // 拖拽松手：水平磁吸贴边
                        val screenW = root.context.resources.displayMetrics.widthPixels
                        val targetX = if (params.x + petSize / 2 < screenW / 2) {
                            0
                        } else {
                            screenW - petSize
                        }

                        val animator = ValueAnimator.ofInt(params.x, targetX).apply {
                            duration = 260
                            interpolator = DecelerateInterpolator()
                            addUpdateListener { va ->
                                params.x = va.animatedValue as Int
                                try {
                                    wm.updateViewLayout(root, params)
                                } catch (_: Exception) {}
                            }
                        }
                        animator.start()

                        // 贴边后自动降为半透明避让
                        root.postDelayed({
                            if (isShowing && miniCardView?.visibility != View.VISIBLE) {
                                root.alpha = 0.6f
                            }
                        }, 1200)

                        // 记录最终坐标
                        getPrefs(root.context).edit()
                            .putInt(KEY_LAST_X, targetX)
                            .putInt(KEY_LAST_Y, params.y)
                            .apply()
                    }
                    true
                }
                else -> false
            }
        }
    }

    /**
     * 隐藏并释放桌面悬浮窗
     */
    fun hide(context: Context) {
        if (!isShowing) return
        try {
            rootView?.let { windowManager?.removeView(it) }
        } catch (_: Exception) {
        } finally {
            rootView = null
            avatarImageView = null
            miniCardView = null
            layoutParams = null
            isShowing = false
        }
    }
}
