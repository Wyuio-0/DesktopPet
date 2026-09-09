
import re
with open("android/app/src/main/java/com/amiya/pet/ui/ScheduleView.kt", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("val weekDays = listOf(\"一\", \"二\", \"三\", \"四\", \"五\", \"六\", \"日\")", "val weekDays = listOf(\"日\", \"一\", \"二\", \"三\", \"四\", \"五\", \"六\")")
text = text.replace("for (wd in 1..7) {", "for (wd in listOf(7, 1, 2, 3, 4, 5, 6)) {")

with open("android/app/src/main/java/com/amiya/pet/ui/ScheduleView.kt", "w", encoding="utf-8") as f:
    f.write(text)

