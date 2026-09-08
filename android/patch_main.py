
import re
with open("app/src/main/java/com/amiya/pet/ui/MainActivity.kt", "r", encoding="utf-8") as f:
    text = f.read()

# Replace starting PetFloatingService with AppBackgroundService
text = text.replace("import com.amiya.pet.service.PetFloatingService", "import com.amiya.pet.service.AppBackgroundService")

# Remove PetDashboardTab completely.
# First, remove it from the enum
text = text.replace("PET(\"桌宠\", Icons.Default.Pets),\n", "")
text = text.replace("var selectedTab by remember { mutableStateOf(MainTab.PET) }", "var selectedTab by remember { mutableStateOf(MainTab.CHAT) }")
text = text.replace("MainTab.PET -> PetDashboardTab()", "")

# Add AppBackgroundService startup in onCreate
text = text.replace("""        setContent {
            AmiyaPetTheme {""", """        val serviceIntent = Intent(this, AppBackgroundService::class.java)
        ContextCompat.startForegroundService(this, serviceIntent)

        setContent {
            AmiyaPetTheme {""")

with open("app/src/main/java/com/amiya/pet/ui/MainActivity.kt", "w", encoding="utf-8") as f:
    f.write(text)

