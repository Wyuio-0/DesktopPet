package com.amiya.pet.core.model

data class Action(
    val name: String,
    val folder: String,
    val interval: Int = 18,
    val loop: Boolean = false,
    val random: Boolean = false,
    val loopCount: Int = 0,
    val next: String? = null,
    val clips: List<String> = emptyList()
)

data class Character(
    val key: String,
    val name: String,
    val displayName: String,
    val scale: Float = 1.0f,
    val actions: Map<String, Action> = emptyMap(),
    val interactions: Map<String, String> = emptyMap(),
    val idleToSitSec: Pair<Int, Int> = 300 to 600,
    val sitToSleepSec: Pair<Int, Int> = 3600 to 7200,
    val greetingLines: List<String> = emptyList()
) {
    fun getAction(name: String): Action? = actions[name]
    fun getInteraction(event: String): String? = interactions[event]
}
