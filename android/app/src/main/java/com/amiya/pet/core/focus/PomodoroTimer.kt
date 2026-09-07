package com.amiya.pet.core.focus

import android.os.Handler
import android.os.Looper
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

object PomodoroTimer {

    private val handler = Handler(Looper.getMainLooper())
    private val _status = MutableStateFlow(PomodoroStatus())
    val status = _status.asStateFlow()

    var onTimerFinished: ((PomodoroMode) -> Unit)? = null

    private val tickRunnable = object : Runnable {
        override fun run() {
            val cur = _status.value
            if (cur.state == PomodoroState.RUNNING) {
                if (cur.remainingSeconds > 1) {
                    _status.value = cur.copy(remainingSeconds = cur.remainingSeconds - 1)
                    handler.postDelayed(this, 1000L)
                } else {
                    _status.value = cur.copy(
                        remainingSeconds = 0,
                        state = PomodoroState.COMPLETED
                    )
                    onTimerFinished?.invoke(cur.mode)
                }
            }
        }
    }

    fun startFocus(minutes: Int = 25) {
        handler.removeCallbacks(tickRunnable)
        val sec = minutes * 60
        _status.value = PomodoroStatus(
            state = PomodoroState.RUNNING,
            mode = PomodoroMode.WORK,
            remainingSeconds = sec,
            totalSeconds = sec
        )
        handler.postDelayed(tickRunnable, 1000L)
    }

    fun startBreak(minutes: Int = 5) {
        handler.removeCallbacks(tickRunnable)
        val sec = minutes * 60
        _status.value = PomodoroStatus(
            state = PomodoroState.RUNNING,
            mode = PomodoroMode.SHORT_BREAK,
            remainingSeconds = sec,
            totalSeconds = sec
        )
        handler.postDelayed(tickRunnable, 1000L)
    }

    fun pause() {
        if (_status.value.state == PomodoroState.RUNNING) {
            handler.removeCallbacks(tickRunnable)
            _status.value = _status.value.copy(state = PomodoroState.PAUSED)
        }
    }

    fun resume() {
        if (_status.value.state == PomodoroState.PAUSED) {
            _status.value = _status.value.copy(state = PomodoroState.RUNNING)
            handler.postDelayed(tickRunnable, 1000L)
        }
    }

    fun reset() {
        handler.removeCallbacks(tickRunnable)
        _status.value = PomodoroStatus()
    }
}
