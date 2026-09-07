package com.amiya.pet.render

import android.content.Context
import android.graphics.PixelFormat
import android.graphics.SurfaceTexture
import android.media.MediaPlayer
import android.media.PlaybackParams
import android.opengl.GLES11Ext
import android.opengl.GLES20
import android.opengl.GLSurfaceView
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.view.Surface
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import javax.microedition.khronos.egl.EGLConfig
import javax.microedition.khronos.opengles.GL10

/**
 * 带有实时 GPU Chroma-Key 绿幕/黑底抠图着色器的透明 GLSurfaceView。
 * 使用 Android 系统原生硬件加速 MediaPlayer 播放 WebM，在 SurfaceTexture 上由 OpenGL ES 进行
 * 零拷贝片元着色处理，保证超低 CPU 与电池消耗。
 */
class PetGlSurfaceView(context: Context) : GLSurfaceView(context),
    GLSurfaceView.Renderer, SurfaceTexture.OnFrameAvailableListener {

    private val mainHandler = Handler(Looper.getMainLooper())
    private var mediaPlayer: MediaPlayer? = null
    private var surfaceTexture: SurfaceTexture? = null
    private var videoSurface: Surface? = null
    private var textureId = 0
    private var program = 0

    private var aPositionHandle = 0
    private var aTextureCoordHandle = 0
    private var updateSurface = false

    private val vertexBuffer: FloatBuffer
    private val textureBuffer: FloatBuffer

    var onPlaybackEnded: (() -> Unit)? = null

    // 全屏四边形顶点映射
    private val squareCoords = floatArrayOf(
        -1.0f, -1.0f,
         1.0f, -1.0f,
        -1.0f,  1.0f,
         1.0f,  1.0f
    )

    // OES 纹理映射（Y 轴反转对齐）
    private val textureCoords = floatArrayOf(
        0.0f, 1.0f,
        1.0f, 1.0f,
        0.0f, 0.0f,
        1.0f, 0.0f
    )

    init {
        // 关键设置：使 GLSurfaceView 背景透明，支持悬浮窗透色
        setEGLContextClientVersion(2)
        setEGLConfigChooser(8, 8, 8, 8, 16, 0)
        holder.setFormat(PixelFormat.TRANSLUCENT)
        setZOrderOnTop(true)

        vertexBuffer = ByteBuffer.allocateDirect(squareCoords.size * 4)
            .order(ByteOrder.nativeOrder()).asFloatBuffer().apply {
                put(squareCoords)
                position(0)
            }

        textureBuffer = ByteBuffer.allocateDirect(textureCoords.size * 4)
            .order(ByteOrder.nativeOrder()).asFloatBuffer().apply {
                put(textureCoords)
                position(0)
            }

        setRenderer(this)
        renderMode = RENDERMODE_WHEN_DIRTY

        initPlayer()
    }

    private fun initPlayer() {
        mediaPlayer = MediaPlayer().apply {
            setVolume(0f, 0f)
        }
    }

    override fun onSurfaceCreated(gl: GL10?, config: EGLConfig?) {
        program = ChromaKeyShader.createProgram()
        if (program != 0) {
            aPositionHandle = GLES20.glGetAttribLocation(program, "aPosition")
            aTextureCoordHandle = GLES20.glGetAttribLocation(program, "aTextureCoord")
        }

        val textures = IntArray(1)
        GLES20.glGenTextures(1, textures, 0)
        textureId = textures[0]
        GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, textureId)
        GLES20.glTexParameterf(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_MIN_FILTER, GLES20.GL_LINEAR.toFloat())
        GLES20.glTexParameterf(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_MAG_FILTER, GLES20.GL_LINEAR.toFloat())
        GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_WRAP_S, GLES20.GL_CLAMP_TO_EDGE)
        GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_WRAP_T, GLES20.GL_CLAMP_TO_EDGE)

        surfaceTexture = SurfaceTexture(textureId).apply {
            setOnFrameAvailableListener(this@PetGlSurfaceView)
            videoSurface = Surface(this)
            mainHandler.post {
                mediaPlayer?.setSurface(videoSurface)
            }
        }
    }

    override fun onSurfaceChanged(gl: GL10?, width: Int, height: Int) {
        GLES20.glViewport(0, 0, width, height)
    }

    override fun onDrawFrame(gl: GL10?) {
        synchronized(this) {
            if (updateSurface) {
                surfaceTexture?.updateTexImage()
                updateSurface = false
            }
        }

        // 清除背景为完全透明
        GLES20.glClearColor(0.0f, 0.0f, 0.0f, 0.0f)
        GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT)

        if (program == 0) return

        // 开启 Alpha 颜色混合
        GLES20.glEnable(GLES20.GL_BLEND)
        GLES20.glBlendFunc(GLES20.GL_SRC_ALPHA, GLES20.GL_ONE_MINUS_SRC_ALPHA)

        GLES20.glUseProgram(program)

        GLES20.glActiveTexture(GLES20.GL_TEXTURE0)
        GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, textureId)

        vertexBuffer.position(0)
        GLES20.glEnableVertexAttribArray(aPositionHandle)
        GLES20.glVertexAttribPointer(aPositionHandle, 2, GLES20.GL_FLOAT, false, 0, vertexBuffer)

        textureBuffer.position(0)
        GLES20.glEnableVertexAttribArray(aTextureCoordHandle)
        GLES20.glVertexAttribPointer(aTextureCoordHandle, 2, GLES20.GL_FLOAT, false, 0, textureBuffer)

        GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP, 0, 4)

        GLES20.glDisableVertexAttribArray(aPositionHandle)
        GLES20.glDisableVertexAttribArray(aTextureCoordHandle)
        GLES20.glDisable(GLES20.GL_BLEND)
    }

    override fun onFrameAvailable(surfaceTexture: SurfaceTexture?) {
        synchronized(this) {
            updateSurface = true
        }
        requestRender()
    }

    /**
     * 加载并播放 assets 目录下的 WebM 视频。
     */
    fun playAsset(assetPath: String, isLoop: Boolean, speed: Float = 1.0f) {
        mainHandler.post {
            try {
                val player = mediaPlayer ?: MediaPlayer().also {
                    mediaPlayer = it
                    videoSurface?.let { s -> it.setSurface(s) }
                }
                player.reset()
                videoSurface?.let { player.setSurface(it) }

                val afd = context.assets.openFd(assetPath)
                player.setDataSource(afd.fileDescriptor, afd.startOffset, afd.length)
                afd.close()

                player.isLooping = isLoop
                player.setVolume(0f, 0f)
                player.setOnCompletionListener {
                    if (!isLoop) {
                        onPlaybackEnded?.invoke()
                    }
                }
                player.prepare()
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    player.playbackParams = PlaybackParams().apply { this.speed = speed }
                }
                player.start()
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }

    fun setSpeed(speed: Float) {
        mainHandler.post {
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && mediaPlayer?.isPlaying == true) {
                    mediaPlayer?.playbackParams = PlaybackParams().apply { this.speed = speed }
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }

    fun pauseVideo() {
        mainHandler.post {
            try {
                if (mediaPlayer?.isPlaying == true) {
                    mediaPlayer?.pause()
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }

    fun resumeVideo() {
        mainHandler.post {
            try {
                mediaPlayer?.start()
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }

    fun release() {
        mainHandler.post {
            try {
                mediaPlayer?.stop()
                mediaPlayer?.release()
            } catch (e: Exception) {
                // ignore
            }
            mediaPlayer = null
        }
        videoSurface?.release()
        videoSurface = null
        surfaceTexture?.release()
        surfaceTexture = null
    }
}
