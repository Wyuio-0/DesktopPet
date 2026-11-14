package com.amiya.pet.acceptance

import android.app.Activity
import android.os.Bundle
import android.view.WindowManager
import android.widget.TextView

/** Debug-only foreground; the package guard prevents use in ordinary app builds. */
class SyncAcceptanceActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (packageName != "com.amiya.pet.syncacceptance") { finish(); return }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContentView(TextView(this).apply {
            text = "阿米娅同步验收\n\n正在使用独立应用数据测试加密同步。\n不会读取或修改正式应用中的课表、笔记和配对。\n\n完成后测试应用会自动关闭。"
            textSize = 19f
            setPadding(32, 80, 32, 32)
        })
    }
}
