package com.amiya.pet.core.focus

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import com.amiya.pet.core.system.AlarmScheduler
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

enum class PomodoroState {
    IDLE, RUNNING, PAUSED, COMPLETED
}

enum class PomodoroMode(val defaultMinutes: Int, val title: String) {
    WORK(25, "专注工作"),
    SHORT_BREAK(5, "短暂休息")
}

data class PomodoroStatus(
    val state: PomodoroState = PomodoroState.IDLE,
    val mode: PomodoroMode = PomodoroMode.WORK,
    val remainingSeconds: Int = 25 * 60,
    val totalSeconds: Int = 25 * 60
) {
    val progress: Float
        get() = if (totalSeconds > 0) (totalSeconds - remainingSeconds).toFloat() / totalSeconds else 0f

    val formattedTime: String
        get() {
            val m = remainingSeconds / 60
            val s = remainingSeconds % 60
            return "%02d:%02d".format(m, s)
        }
}

/**
 * 番茄钟核心计时器
 *
 * 采用绝对墙上时钟 SystemClock.elapsedRealtime() 计算剩余时间，
 * 彻底解决锁屏休眠、切后台时 Handler 降频累减导致倒计时停滞或变慢的系统通病；
 * 同时联动 AlarmScheduler 精准闹钟，在 CPU 深度休眠时分秒不差准时唤醒响铃。
 */
object PomodoroTimer {

    private var appContext: Context? = null
    private val handler = Handler(Looper.getMainLooper())
    private val _status = MutableStateFlow(PomodoroStatus())
    val status = _status.asStateFlow()

    var onTimerFinished: ((PomodoroMode) -> Unit)? = null

    // 绝对终点时间戳 (基于系统开机不睡眠时钟 SystemClock.elapsedRealtime())
    private var targetEndTimeRealtime: Long = 0L

    fun init(context: Context) {
        if (appContext == null) {
            appContext = context.applicationContext
        }
    }

    private val tickRunnable = object : Runnable {
        override fun run() {
            val cur = _status.value
            if (cur.state == PomodoroState.RUNNING) {
                val now = SystemClock.elapsedRealtime()
                val diffMs = targetEndTimeRealtime - now
                if (diffMs > 0) {
                    val remainingSec = ((diffMs + 999) / 1000).toInt()
                    _status.value = cur.copy(remainingSeconds = remainingSec)
                    handler.postDelayed(this, 1000L)
                } else {
                    complete()
                }
            }
        }
    }

    fun startFocus(minutes: Int = 25) {
        handler.removeCallbacks(tickRunnable)
        val sec = minutes * 60
        targetEndTimeRealtime = SystemClock.elapsedRealtime() + (sec * 1000L)
        _status.value = PomodoroStatus(
            state = PomodoroState.RUNNING,
            mode = PomodoroMode.WORK,
            remainingSeconds = sec,
            totalSeconds = sec
        )
        appContext?.let { AlarmScheduler.schedulePomodoroAlarm(it, targetEndTimeRealtime, PomodoroMode.WORK) }
        handler.postDelayed(tickRunnable, 1000L)
    }

    fun startBreak(minutes: Int = 5) {
        handler.removeCallbacks(tickRunnable)
        val sec = minutes * 60
        targetEndTimeRealtime = SystemClock.elapsedRealtime() + (sec * 1000L)
        _status.value = PomodoroStatus(
            state = PomodoroState.RUNNING,
            mode = PomodoroMode.SHORT_BREAK,
            remainingSeconds = sec,
            totalSeconds = sec
        )
        appContext?.let { AlarmScheduler.schedulePomodoroAlarm(it, targetEndTimeRealtime, PomodoroMode.SHORT_BREAK) }
        handler.postDelayed(tickRunnable, 1000L)
    }

    fun pause() {
        if (_status.value.state == PomodoroState.RUNNING) {
            handler.removeCallbacks(tickRunnable)
            appContext?.let { AlarmScheduler.cancelPomodoroAlarm(it) }

            val now = SystemClock.elapsedRealtime()
            val diffMs = targetEndTimeRealtime - now
            val remainingSec = maxOf(0, if (diffMs > 0) ((diffMs + 999) / 1000).toInt() else 0)

            _status.value = _status.value.copy(
                state = PomodoroState.PAUSED,
                remainingSeconds = remainingSec
            )
        }
    }

    fun resume() {
        if (_status.value.state == PomodoroState.PAUSED) {
            val sec = _status.value.remainingSeconds
            if (sec <= 0) {
                complete()
                return
            }
            targetEndTimeRealtime = SystemClock.elapsedRealtime() + (sec * 1000L)
            _status.value = _status.value.copy(state = PomodoroState.RUNNING)
            appContext?.let { AlarmScheduler.schedulePomodoroAlarm(it, targetEndTimeRealtime, _status.value.mode) }
            handler.postDelayed(tickRunnable, 1000L)
        }
    }

    /**
     * 来自精确闹钟唤醒的结束触发
     */
    fun completeFromAlarm() {
        handler.post {
            if (_status.value.state == PomodoroState.RUNNING) {
                complete()
            }
        }
    }

    private fun complete() {
        handler.removeCallbacks(tickRunnable)
        appContext?.let { AlarmScheduler.cancelPomodoroAlarm(it) }
        val curMode = _status.value.mode
        _status.value = _status.value.copy(
            remainingSeconds = 0,
            state = PomodoroState.COMPLETED
        )
        onTimerFinished?.invoke(curMode)
    }

    /**
     * 在界面可见、亮屏或时钟广播到来时，立即同步真实剩余秒数
     */
    fun refreshTime() {
        if (_status.value.state == PomodoroState.RUNNING) {
            val now = SystemClock.elapsedRealtime()
            val diffMs = targetEndTimeRealtime - now
            if (diffMs > 0) {
                val remainingSec = ((diffMs + 999) / 1000).toInt()
                _status.value = _status.value.copy(remainingSeconds = remainingSec)
            } else {
                complete()
            }
        }
    }

    fun setDuration(mode: PomodoroMode, minutes: Int) {
        if (_status.value.state == PomodoroState.RUNNING) return
        handler.removeCallbacks(tickRunnable)
        appContext?.let { AlarmScheduler.cancelPomodoroAlarm(it) }
        val sec = minutes * 60
        _status.value = PomodoroStatus(
            state = PomodoroState.IDLE,
            mode = mode,
            remainingSeconds = sec,
            totalSeconds = sec
        )
    }

    fun reset(customMinutes: Int? = null) {
        handler.removeCallbacks(tickRunnable)
        appContext?.let { AlarmScheduler.cancelPomodoroAlarm(it) }
        val currentMode = _status.value.mode
        val mins = customMinutes ?: if (currentMode == PomodoroMode.WORK) 25 else 5
        val sec = mins * 60
        _status.value = PomodoroStatus(
            state = PomodoroState.IDLE,
            mode = currentMode,
            remainingSeconds = sec,
            totalSeconds = sec
        )
    }
}
