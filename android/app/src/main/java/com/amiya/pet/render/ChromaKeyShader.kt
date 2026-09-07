package com.amiya.pet.render

import android.opengl.GLES20
import android.util.Log

object ChromaKeyShader {
    private const val TAG = "ChromaKeyShader"

    const val VERTEX_SHADER = """
        attribute vec4 aPosition;
        attribute vec4 aTextureCoord;
        varying vec2 vTextureCoord;
        void main() {
            gl_Position = aPosition;
            vTextureCoord = aTextureCoord.xy;
        }
    """

    // 使用 samplerExternalOES 直采 SurfaceTexture 的视频流
    const val FRAGMENT_SHADER = """
        #extension GL_OES_EGL_image_external : require
        precision mediump float;
        varying vec2 vTextureCoord;
        uniform samplerExternalOES sTexture;

        void main() {
            vec4 c = texture2D(sTexture, vTextureCoord);
            float maxc = max(max(c.r, c.g), c.b);
            float minc = min(min(c.r, c.g), c.b);
            float chroma = maxc - minc;

            // 背景黑边精准扣除与边缘平滑渐变（GPU硬件加速，0发热）
            if (maxc < 0.07 && chroma < 0.05) {
                gl_FragColor = vec4(0.0, 0.0, 0.0, 0.0);
            } else if (maxc < 0.16 && chroma < 0.05) {
                float a = smoothstep(0.07, 0.16, maxc);
                gl_FragColor = vec4(c.rgb, a);
            } else {
                gl_FragColor = c;
            }
        }
    """

    fun createProgram(): Int {
        val vertexShader = loadShader(GLES20.GL_VERTEX_SHADER, VERTEX_SHADER)
        val fragmentShader = loadShader(GLES20.GL_FRAGMENT_SHADER, FRAGMENT_SHADER)
        if (vertexShader == 0 || fragmentShader == 0) return 0

        val program = GLES20.glCreateProgram()
        if (program != 0) {
            GLES20.glAttachShader(program, vertexShader)
            GLES20.glAttachShader(program, fragmentShader)
            GLES20.glLinkProgram(program)
            val linkStatus = IntArray(1)
            GLES20.glGetProgramiv(program, GLES20.GL_LINK_STATUS, linkStatus, 0)
            if (linkStatus[0] != GLES20.GL_TRUE) {
                Log.e(TAG, "无法链接 OpenGL 程序: " + GLES20.glGetProgramInfoLog(program))
                GLES20.glDeleteProgram(program)
                return 0
            }
        }
        return program
    }

    private fun loadShader(shaderType: Int, source: String): Int {
        var shader = GLES20.glCreateShader(shaderType)
        if (shader != 0) {
            GLES20.glShaderSource(shader, source)
            GLES20.glCompileShader(shader)
            val compiled = IntArray(1)
            GLES20.glGetShaderiv(shader, GLES20.GL_COMPILE_STATUS, compiled, 0)
            if (compiled[0] == 0) {
                Log.e(TAG, "着色器编译失败 $shaderType: " + GLES20.glGetShaderInfoLog(shader))
                GLES20.glDeleteShader(shader)
                shader = 0
            }
        }
        return shader
    }
}
