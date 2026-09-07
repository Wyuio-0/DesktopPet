package com.amiya.pet.ui

import android.animation.Animator
import android.animation.AnimatorListenerAdapter
import android.content.Context
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Handler
import android.os.Looper
import android.util.AttributeSet
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.TextView

/**
 * 悬浮宠物的对话气泡 View。
 * 显示角色台词、问候语，支持淡入淡出动画与点击消失。
 */
class PetBubbleView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : TextView(context, attrs, defStyleAttr) {

    private val handler = Handler(Looper.getMainLooper())
    private val dismissRunnable = Runnable { hideBubble() }

    init {
        visibility = View.GONE
        gravity = Gravity.CENTER
        setTextColor(Color.WHITE)
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 12.5f)

        val padH = dpToPx(10f)
        val padV = dpToPx(6f)
        setPadding(padH, padV, padH, padV)

        // 舟味半透明圆角气泡卡片风格
        val bg = GradientDrawable().apply {
            shape = GradientDrawable.RECTANGLE
            cornerRadius = dpToPx(12f).toFloat()
            setColor(Color.parseColor("#CC1E222D"))
            setStroke(dpToPx(1f), Color.parseColor("#403A90FF"))
        }
        background = bg

        setOnClickListener {
            hideBubble()
        }
    }

    fun showBubble(message: String, durationMs: Long = 3500L) {
        handler.removeCallbacks(dismissRunnable)
        text = message
        visibility = View.VISIBLE
        alpha = 0f
        scaleX = 0.85f
        scaleY = 0.85f

        animate()
            .alpha(1f)
            .scaleX(1f)
            .scaleY(1f)
            .setDuration(200)
            .setListener(null)
            .start()

        handler.postDelayed(dismissRunnable, durationMs)
    }

    fun hideBubble() {
        handler.removeCallbacks(dismissRunnable)
        animate()
            .alpha(0f)
            .scaleX(0.85f)
            .scaleY(0.85f)
            .setDuration(180)
            .setListener(object : AnimatorListenerAdapter() {
                override fun onAnimationEnd(animation: Animator) {
                    visibility = View.GONE
                }
            })
            .start()
    }

    private fun dpToPx(dp: Float): Int {
        return TypedValue.applyDimension(
            TypedValue.COMPLEX_UNIT_DIP,
            dp,
            resources.displayMetrics
        ).toInt()
    }
}
