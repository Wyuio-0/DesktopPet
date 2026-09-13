package com.amiya.pet.floating

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

/**
 * 桌面桌宠 ADB 极速调试广播接收器 (TEST_ACTION)
 * 允许在无需重新打包的情况下，毫秒级注入状态、手势、卡片与收纳指令
 */
class PetDebugReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == "com.amiya.pet.TEST_ACTION") {
            Log.d("PetDebug", "Received TEST_ACTION: extras=${intent.extras}")
            FloatingPetManager.handleDebugCommand(context, intent)
        } else if (intent.action == "com.amiya.pet.ACTION_RESTORE_PET") {
            Log.d("PetDebug", "Received ACTION_RESTORE_PET")
            FloatingPetManager.restoreFromRest(context)
        }
    }
}
