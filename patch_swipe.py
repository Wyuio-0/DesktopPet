
import re

with open("android/app/src/main/java/com/amiya/pet/ui/ScheduleView.kt", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update ScheduleScreen to pass callbacks
text = text.replace(
    "TimetableGrid(currentWeek, refreshTrigger)",
    "TimetableGrid(currentWeek, refreshTrigger, { if (currentWeek > 1) currentWeek-- }, { currentWeek++ })"
)

# 2. Update TimetableGrid signature
text = text.replace(
    "fun TimetableGrid(weekNo: Int, refreshTrigger: Int) {",
    "fun TimetableGrid(weekNo: Int, refreshTrigger: Int, onPrevWeek: () -> Unit, onNextWeek: () -> Unit) {"
)

# 3. Add imports for gestures
if "import androidx.compose.foundation.gestures.detectHorizontalDragGestures" not in text:
    text = text.replace(
        "import androidx.compose.foundation.verticalScroll",
        "import androidx.compose.foundation.verticalScroll\nimport androidx.compose.foundation.gestures.detectHorizontalDragGestures\nimport androidx.compose.ui.input.pointer.pointerInput"
    )

# 4. Add calculation of current real week, day, time
calc_code = """
    var showTime by remember { mutableStateOf(false) }

    val realWeekNo = ScheduleManager.getWeekNo() ?: 1
    val cal = Calendar.getInstance()
    val todayIdx = cal.get(Calendar.DAY_OF_WEEK)
    val currentIsoWeekday = if (todayIdx == Calendar.SUNDAY) 7 else todayIdx - 1
    val isCurrentWeek = (weekNo == realWeekNo)
    val currentMins = cal.get(Calendar.HOUR_OF_DAY) * 60 + cal.get(Calendar.MINUTE)
    val dayOrder = listOf(7, 1, 2, 3, 4, 5, 6)

    // Gesture state
    var dragAccumulator by remember { mutableFloatStateOf(0f) }
"""
text = text.replace("    var showTime by remember { mutableStateOf(false) }", calc_code)

# 5. Highlight current day in header
header_loop_old = """        Row(modifier = Modifier.fillMaxWidth().padding(start = 38.dp, end = 8.dp)) {
            weekDays.forEach {
                Text(it, modifier = Modifier.weight(1f), color = Color.LightGray, fontSize = 12.sp, textAlign = TextAlign.Center)
            }
        }"""
header_loop_new = """        Row(modifier = Modifier.fillMaxWidth().padding(start = 38.dp, end = 8.dp)) {
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
text = text.replace(header_loop_old, header_loop_new)

# 6. Add pointer input to BoxWithConstraints
box_old = "BoxWithConstraints(modifier = Modifier.weight(1f).fillMaxWidth().padding(end = 8.dp, bottom = 16.dp)) {"
box_new = """BoxWithConstraints(modifier = Modifier.weight(1f).fillMaxWidth().padding(end = 8.dp, bottom = 16.dp)
            .pointerInput(Unit) {
                detectHorizontalDragGestures(
                    onDragEnd = { dragAccumulator = 0f },
                    onDragCancel = { dragAccumulator = 0f }
                ) { change, dragAmount ->
                    change.consume()
                    dragAccumulator += dragAmount
                    if (dragAccumulator > 150f) {
                        onPrevWeek()
                        dragAccumulator = 0f
                    } else if (dragAccumulator < -150f) {
                        onNextWeek()
                        dragAccumulator = 0f
                    }
                }
            }
        ) {"""
text = text.replace(box_old, box_new)

# 7. Highlight current time slot in row numbers
row_box_old = """                    Box(modifier = Modifier.fillMaxWidth().height(rowH)) {
                        Box(
                            modifier = Modifier
                                .width(38.dp)
                                .fillMaxHeight()
                                .clickable { showTime = !showTime }
                                .align(Alignment.CenterStart),
                            contentAlignment = Alignment.Center
                        ) {"""
row_box_new = """                    val rawTime = ScheduleManager.sections[i.toString()] ?: ""
                    var isCurrentSlot = false
                    if (isCurrentWeek && rawTime.contains(":")) {
                        try {
                            val parts = rawTime.split(":")
                            val startMins = parts[0].toInt() * 60 + parts[1].toInt()
                            if (currentMins in startMins..(startMins + 45)) {
                                isCurrentSlot = true
                            }
                        } catch(e: Exception){}
                    }

                    Box(modifier = Modifier.fillMaxWidth().height(rowH).background(if (isCurrentSlot) MaterialTheme.colorScheme.primary.copy(alpha=0.1f) else Color.Transparent)) {
                        Box(
                            modifier = Modifier
                                .width(38.dp)
                                .fillMaxHeight()
                                .clickable { showTime = !showTime }
                                .background(if (isCurrentSlot) MaterialTheme.colorScheme.primary.copy(alpha=0.2f) else Color.Transparent)
                                .align(Alignment.CenterStart),
                            contentAlignment = Alignment.Center
                        ) {"""
text = text.replace(row_box_old, row_box_new)
text = text.replace("val rawTime = ScheduleManager.sections[i.toString()] ?: \"$i\"", "val rawTimeText = ScheduleManager.sections[i.toString()] ?: \"$i\"")
text = text.replace("if (rawTime.contains", "if (rawTimeText.contains")
text = text.replace("rawTime.replace", "rawTimeText.replace")
text = text.replace("val parts = rawTime.split", "val parts = rawTimeText.split")
text = text.replace("catch(e: Exception) { rawTime }", "catch(e: Exception) { rawTimeText }")
text = text.replace("else rawTime", "else rawTimeText")


with open("android/app/src/main/java/com/amiya/pet/ui/ScheduleView.kt", "w", encoding="utf-8") as f:
    f.write(text)

