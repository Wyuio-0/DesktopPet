package com.amiya.pet.service

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Point
import android.os.Handler
import android.os.Looper
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.view.animation.DecelerateInterpolator
import com.amiya.pet.core.state.PetStateMachine
import kotlin.math.abs

class PetTouchHandler(
    private val context: Context,
    private val windowManager: WindowManager,
    private val petView: View,
    private val layoutParams: WindowManager.LayoutParams,
    private val stateMachine: PetStateMachine
) : View.OnTouchListener {

    private var initialX = 0
    private var initialY = 0
    private var initialTouchX = 0f
    private var initialTouchY = 0f
    private var isDragging = false

    private var lastClickTime = 0L
    private val handler = Handler(Looper.getMainLooper())
    private var pendingSingleClick: Runnable? = null

    private val touchSlop = 16f
    private val screenWidth: Int
        get() {
            val size = Point()
            windowManager.defaultDisplay.getSize(size)
            return size.x
        }

    override fun onTouch(v: View, event: MotionEvent): Boolean {
        when (event.action) {
            MotionEvent.ACTION_DOWN -> {
                initialX = layoutParams.x
                initialY = layoutParams.y
                initialTouchX = event.rawX
                initialTouchY = event.rawY
                isDragging = false
                return true
            }

            MotionEvent.ACTION_MOVE -> {
                val dx = event.rawX - initialTouchX
                val dy = event.rawY - initialTouchY

                if (!isDragging && (abs(dx) > touchSlop || abs(dy) > touchSlop)) {
                    isDragging = true
                    stateMachine.onUserDragStart()
                }

                if (isDragging) {
                    layoutParams.x = initialX + dx.toInt()
                    layoutParams.y = initialY + dy.toInt()
                    windowManager.updateViewLayout(petView, layoutParams)
                }
                return true
            }

            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                if (isDragging) {
                    stateMachine.onUserDragEnd()
                    snapToEdge()
                } else {
                    handleClick()
                }
                isDragging = false
                return true
            }
        }
        return false
    }

    private fun handleClick() {
        val now = System.currentTimeMillis()
        if (now - lastClickTime < 320) {
            // 双击：取消待触发的单击，执行打招呼
            pendingSingleClick?.let { handler.removeCallbacks(it) }
            pendingSingleClick = null
            lastClickTime = 0L
            stateMachine.onUserDoubleClick()
        } else {
            // 单击：延迟 200ms 执行防抖
            lastClickTime = now
            pendingSingleClick?.let { handler.removeCallbacks(it) }
            val singleClickTask = Runnable {
                stateMachine.onUserClick()
                pendingSingleClick = null
            }
            pendingSingleClick = singleClickTask
            handler.postDelayed(singleClickTask, 220)
        }
    }

    /**
     * 智能屏幕边缘磁吸（松手后优雅弹射至左侧或右侧边缘）。
     */
    private fun snapToEdge() {
        val screenW = screenWidth
        val petW = petView.width
        val currentX = layoutParams.x
        val centerX = currentX + petW / 2

        val targetX = if (centerX < screenW / 2) {
            10 // 贴左边缘（保留 10px 边距）
        } else {
            screenW - petW - 10 // 贴右边缘
        }

        val animator = ValueAnimator.ofInt(currentX, targetX).apply {
            duration = 250
            interpolator = DecelerateInterpolator()
            addUpdateListener { anim ->
                layoutParams.x = anim.animatedValue as Int
                try {
                    windowManager.updateViewLayout(petView, layoutParams)
                } catch (e: Exception) {
                    // ignore if detached
                }
            }
        }
        animator.start()
    }
}
