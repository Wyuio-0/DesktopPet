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
        } else if (intent.action == "com.amiya.pet.ACTION_ADD_COURSE_NL") {
            val text = intent.getStringExtra("text") ?: ""
            Log.d("PetDebug", "Received ACTION_ADD_COURSE_NL: text=$text")
            if (text.isNotEmpty()) {
                com.amiya.pet.core.schedule.ScheduleManager.ensureLoaded(context)
                Log.d("PetDebug", "DEBUG: termStart=${com.amiya.pet.core.schedule.ScheduleManager.termStart}, weekNo=${com.amiya.pet.core.schedule.ScheduleManager.getWeekNo()}")
                val course = com.amiya.pet.core.schedule.ScheduleManager.parseCourseFromNaturalLanguage(text)
                if (course != null) {
                    com.amiya.pet.core.schedule.ScheduleManager.addCourse(course, context)
                    Log.d("PetDebug", "Added course via NL: ${course.name}, weekday=${course.weekday}, sec=${course.secStart}-${course.secEnd}, week=${course.weekStart}~${course.weekEnd}, customTime=${course.customTime}")
                }
            }
        }
    }
}
