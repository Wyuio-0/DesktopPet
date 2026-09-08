
import re
with open("app/src/main/java/com/amiya/pet/service/PetFloatingService.kt", "r", encoding="utf-8") as f:
    code = f.read()

code = code.replace("import kotlinx.coroutines.flow.asStateFlow", """import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.util.Date
import com.amiya.pet.core.schedule.ScheduleManager""")

code = code.replace("private var voicePlayer: VoicePlayer? = null", """private var voicePlayer: VoicePlayer? = null
    private var reminderJob: Job? = null
    private var lastRemindedClass: String? = null""")

code = code.replace("_isRunning.value = true", """_isRunning.value = true
        startClassReminderLoop()""")

code = code.replace("override fun onDestroy() {", """override fun onDestroy() {
        reminderJob?.cancel()""")

extra_code = """

    private fun startClassReminderLoop() {
        ScheduleManager.load(this)
        reminderJob = CoroutineScope(Dispatchers.Main + Job()).launch {
            while (true) {
                delay(60_000L) // check every minute
                try {
                    val next = ScheduleManager.nextClass(Date())
                    if (next != null) {
                        val diffMillis = next.startTime.time - Date().time
                        val diffMinutes = diffMillis / 60000
                        if (diffMinutes in 0..ScheduleManager.remindMinutes.toLong()) {
                            val classId = "${next.course.name}_${next.startTime.time}"
                            if (lastRemindedClass != classId) {
                                lastRemindedClass = classId
                                val msg = "博士，即将上课：${next.course.name} (在 ${next.course.room})。请做好准备哦！"
                                bubbleView?.showBubble(msg, 8000L)
                                voicePlayer?.playGreetVoice()
                                
                                val manager = getSystemService(NotificationManager::class.java)
                                val notif = NotificationCompat.Builder(this@PetFloatingService, CHANNEL_ID)
                                    .setContentTitle("上课提醒")
                                    .setContentText(msg)
                                    .setSmallIcon(R.mipmap.ic_launcher)
                                    .setPriority(NotificationCompat.PRIORITY_HIGH)
                                    .setAutoCancel(true)
                                    .build()
                                manager.notify(1002, notif)
                            }
                        }
                    }
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }
        }
    }
}
"""
code = re.sub(r"}\s*$", extra_code, code)

with open("app/src/main/java/com/amiya/pet/service/PetFloatingService.kt", "w", encoding="utf-8") as f:
    f.write(code)

