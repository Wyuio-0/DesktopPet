
import re

with open("android/app/src/main/java/com/amiya/pet/ui/ScheduleView.kt", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Add date calculation
date_logic = """    val dayOrder = listOf(7, 1, 2, 3, 4, 5, 6)

    val dates = remember(weekNo, refreshTrigger) {
        val start = ScheduleManager.termStart
        if (start != null) {
            val cal = Calendar.getInstance()
            cal.time = start
            cal.add(Calendar.DAY_OF_YEAR, (weekNo - 1) * 7)
            val dayOfWeek = cal.get(Calendar.DAY_OF_WEEK)
            cal.add(Calendar.DAY_OF_YEAR, Calendar.SUNDAY - dayOfWeek)
            
            val result = mutableListOf<String>()
            for (i in 0..6) {
                result.add(java.text.SimpleDateFormat("M.d", java.util.Locale.getDefault()).format(cal.time))
                cal.add(Calendar.DAY_OF_YEAR, 1)
            }
            result
        } else {
            List(7) { "" }
        }
    }

    // Gesture state"""

text = text.replace("    val dayOrder = listOf(7, 1, 2, 3, 4, 5, 6)\n\n    // Gesture state", date_logic)

# 2. Update the header loop
old_header = """        Row(modifier = Modifier.fillMaxWidth().padding(start = 38.dp, end = 8.dp)) {
            weekDays.forEachIndexed { idx, it ->
                val isToday = isCurrentWeek && currentIsoWeekday == dayOrder[idx]
                Text(
                    text = it,
                    modifier = Modifier.weight(1f).clip(RoundedCornerShape(4.dp)).background(if (isToday) MaterialTheme.colorScheme.primary.copy(alpha=0.3f) else Color.Transparent),
                    color = if (isToday) MaterialTheme.colorScheme.primary else Color.LightGray,
                    fontSize = 12.sp,
                    fontWeight = if (isToday) FontWeight.Bold else FontWeight.Normal,
                    textAlign = TextAlign.Center
                )
            }
        }"""

new_header = """        Row(modifier = Modifier.fillMaxWidth().padding(start = 38.dp, end = 8.dp)) {
            weekDays.forEachIndexed { idx, it ->
                val isToday = isCurrentWeek && currentIsoWeekday == dayOrder[idx]
                Column(
                    modifier = Modifier.weight(1f)
                        .clip(RoundedCornerShape(4.dp))
                        .background(if (isToday) MaterialTheme.colorScheme.primary.copy(alpha=0.3f) else Color.Transparent)
                        .padding(vertical = 2.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = it,
                        color = if (isToday) MaterialTheme.colorScheme.primary else Color.LightGray,
                        fontSize = 12.sp,
                        fontWeight = if (isToday) FontWeight.Bold else FontWeight.Normal
                    )
                    if (dates[idx].isNotEmpty()) {
                        Text(
                            text = dates[idx],
                            color = if (isToday) MaterialTheme.colorScheme.primary else Color.Gray,
                            fontSize = 9.sp,
                            fontWeight = if (isToday) FontWeight.Bold else FontWeight.Normal
                        )
                    }
                }
            }
        }"""

text = text.replace(old_header, new_header)

with open("android/app/src/main/java/com/amiya/pet/ui/ScheduleView.kt", "w", encoding="utf-8") as f:
    f.write(text)

