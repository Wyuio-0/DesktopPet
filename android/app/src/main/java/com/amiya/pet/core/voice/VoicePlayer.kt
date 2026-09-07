package com.amiya.pet.core.voice

import android.content.Context
import android.media.MediaPlayer
import android.util.Log

class VoicePlayer(private val context: Context) {

    private val TAG = "VoicePlayer"
    private var mediaPlayer: MediaPlayer? = null
    private var currentVoiceFiles: List<String> = emptyList()
    private var currentCharKey: String = ""

    var volume: Float = 0.8f
        set(value) {
            field = value.coerceIn(0f, 1f)
            if (!isMuted) {
                mediaPlayer?.setVolume(field, field)
            }
        }

    var isMuted: Boolean = false
        set(value) {
            field = value
            val vol = if (field) 0f else volume
            mediaPlayer?.setVolume(vol, vol)
        }

    fun loadCharacterVoices(charKey: String) {
        currentCharKey = charKey
        val voiceDir = "characters/$charKey/voice"
        currentVoiceFiles = try {
            context.assets.list(voiceDir)?.filter { it.endsWith(".wav", ignoreCase = true) }
                ?.map { "$voiceDir/$it" } ?: emptyList()
        } catch (e: Exception) {
            Log.w(TAG, "No voice assets found for $charKey", e)
            emptyList()
        }
    }

    fun playClickVoice() {
        playByKeyword(listOf("戳一下", "交谈", "Interact"))
    }

    fun playGreetVoice() {
        playByKeyword(listOf("问候", "助理", "队长", "Start", "Hello"))
    }

    fun playIdleVoice() {
        playByKeyword(listOf("闲置", "Relax", "Idle"))
    }

    fun playRandomVoice() {
        if (currentVoiceFiles.isNotEmpty()) {
            playAsset(currentVoiceFiles.random())
        }
    }

    private fun playByKeyword(keywords: List<String>) {
        if (currentVoiceFiles.isEmpty()) return

        val matched = currentVoiceFiles.filter { path ->
            keywords.any { kw -> path.contains(kw, ignoreCase = true) }
        }

        val clip = if (matched.isNotEmpty()) matched.random() else currentVoiceFiles.random()
        playAsset(clip)
    }

    private fun playAsset(assetPath: String) {
        if (isMuted || volume <= 0.01f) return

        try {
            mediaPlayer?.stop()
            mediaPlayer?.release()
            mediaPlayer = null

            val afd = context.assets.openFd(assetPath)
            mediaPlayer = MediaPlayer().apply {
                setDataSource(afd.fileDescriptor, afd.startOffset, afd.length)
                afd.close()
                setVolume(volume, volume)
                setOnCompletionListener {
                    it.release()
                    if (mediaPlayer == it) {
                        mediaPlayer = null
                    }
                }
                prepare()
                start()
            }
        } catch (e: Exception) {
            Log.w(TAG, "Failed to play voice clip: $assetPath", e)
        }
    }

    fun stop() {
        try {
            mediaPlayer?.stop()
            mediaPlayer?.release()
        } catch (e: Exception) {
            // ignore
        }
        mediaPlayer = null
    }

    fun release() {
        stop()
    }
}
