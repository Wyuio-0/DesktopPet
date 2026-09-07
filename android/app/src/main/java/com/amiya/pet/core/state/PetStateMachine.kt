package com.amiya.pet.core.state

import android.os.Handler
import android.os.Looper
import com.amiya.pet.core.model.Action
import com.amiya.pet.core.model.Character
import kotlin.random.Random

interface PetStateListener {
    fun onActionStarted(action: Action, clipPath: String)
    fun onBubbleMessage(text: String)
    fun onUserInteraction(type: String)
}

class PetStateMachine(
    var character: Character,
    private val listener: PetStateListener
) {
    private val handler = Handler(Looper.getMainLooper())
    private var curAction: Action? = null
    private var loopsLeft = 0

    private val restRunnable = Runnable { advanceRestCycle() }

    fun start() {
        if (character.actions.containsKey("start")) {
            play("start")
        } else {
            play("idle")
        }
    }

    fun play(actionName: String) {
        val action = character.getAction(actionName) ?: character.getAction("idle") ?: return
        curAction = action
        loopsLeft = action.loopCount

        val clip = pickClip(action)
        if (clip != null) {
            listener.onActionStarted(action, clip)
        }

        scheduleRest(action.name)
    }

    /**
     * 视频播放完一次循环或整段结束时由播放器回调。
     */
    fun onClipPlaybackEnded() {
        val action = curAction ?: return
        if (action.loop) {
            // 持续循环动作由播放器自主无缝循环
            return
        }

        if (loopsLeft > 0) {
            loopsLeft--
            val clip = pickClip(action)
            if (clip != null) {
                listener.onActionStarted(action, clip)
            }
        } else {
            val nextAction = action.next ?: "idle"
            play(nextAction)
        }
    }

    fun onUserClick() {
        wake()
        val target = character.getInteraction("on_click") ?: "click"
        if (character.actions.containsKey(target)) {
            play(target)
        }
        listener.onUserInteraction("click")
    }

    fun onUserDoubleClick() {
        wake()
        val target = character.getInteraction("on_double_click") ?: "greet"
        if (character.actions.containsKey(target)) {
            play(target)
            if (character.greetingLines.isNotEmpty()) {
                val line = character.greetingLines.random()
                listener.onBubbleMessage(line)
            }
        }
        listener.onUserInteraction("double_click")
    }

    fun onUserDragStart() {
        wake()
        val target = character.getInteraction("on_drag") ?: "drag"
        if (character.actions.containsKey(target)) {
            play(target)
        }
    }

    fun onUserDragEnd() {
        if (curAction?.name == "drag" || curAction?.name == "move") {
            play("idle")
        }
    }

    fun wake(): Boolean {
        if (curAction?.name == "sleep") {
            if (character.actions.containsKey("sit")) {
                play("sit")
            } else {
                play("idle")
            }
            return true
        }
        return false
    }

    private fun pickClip(action: Action): String? {
        if (action.clips.isEmpty()) return null
        return if (action.random) {
            action.clips.random()
        } else {
            action.clips.first()
        }
    }

    private fun scheduleRest(actionName: String) {
        handler.removeCallbacks(restRunnable)
        when (actionName) {
            "idle" -> {
                val (lo, hi) = character.idleToSitSec
                val delayMs = Random.nextLong(lo.toLong(), (hi + 1).toLong()) * 1000L
                handler.postDelayed(restRunnable, delayMs)
            }
            "sit" -> {
                val (lo, hi) = character.sitToSleepSec
                val delayMs = Random.nextLong(lo.toLong(), (hi + 1).toLong()) * 1000L
                handler.postDelayed(restRunnable, delayMs)
            }
        }
    }

    private fun advanceRestCycle() {
        when (curAction?.name) {
            "idle" -> if (character.actions.containsKey("sit")) play("sit")
            "sit" -> if (character.actions.containsKey("sleep")) play("sleep")
        }
    }

    fun destroy() {
        handler.removeCallbacks(restRunnable)
    }
}
