
import re
with open("android/app/src/main/java/com/amiya/pet/ui/ScheduleView.kt", "r", encoding="utf-8") as f:
    text = f.read()

# Find the Text for time display
# text = if (showTime) ScheduleManager.sections[i.toString()] ?: "$i" else i.toString(),
replacement = """
                            val rawTime = ScheduleManager.sections[i.toString()] ?: "$i"
                            val displayTime = if (!showTime) i.toString() else {
                                if (rawTime.contains("-") || rawTime.contains("\\n")) {
                                    rawTime.replace("-", "\\n")
                                } else if (rawTime.contains(":")) {
                                    try {
                                        val parts = rawTime.split(":")
                                        val h = parts[0].toInt()
                                        val m = parts[1].toInt()
                                        val endM = h * 60 + m + 45
                                        val eH = endM / 60
                                        val eM = endM % 60
                                        "$rawTime\\n${String.format("%02d:%02d", eH, eM)}"
                                    } catch(e: Exception) { rawTime }
                                } else rawTime
                            }
                            Text(
                                text = displayTime,
"""

text = re.sub(r"Text\(\s*text\s*=\s*if\s*\(showTime\)\s*ScheduleManager\.sections\[i\.toString\(\)\]\s*\?:\s*\"\$i\"\s*else\s*i\.toString\(\),", replacement.strip(), text)

# I should also reduce the font size from 10.sp to 9.sp or 8.sp to ensure it fits because there are now two lines of time in a small box!
text = re.sub(r"fontSize\s*=\s*if\s*\(showTime\)\s*10\.sp\s*else\s*11\.sp,", "fontSize = if (showTime) 9.sp else 11.sp,\n                                lineHeight = 11.sp,", text)

with open("android/app/src/main/java/com/amiya/pet/ui/ScheduleView.kt", "w", encoding="utf-8") as f:
    f.write(text)

