
import re
with open("app/src/main/java/com/amiya/pet/ui/MainActivity.kt", "r", encoding="utf-8") as f:
    text = f.read()

# Find @OptIn(ExperimentalMaterial3Api::class) fun PetDashboardTab()
match = re.search(r"@OptIn\(ExperimentalMaterial3Api::class\)\s*@Composable\s*fun PetDashboardTab\(\).*?^@Composable\s*fun GuideItem", text, flags=re.MULTILINE | re.DOTALL)
if match:
    text = text[:match.start()] + "\n@Composable\nfun GuideItem" + text[match.end():]

# In case some unused imports remain, we can let them be, but we can also remove PetFloatingService
with open("app/src/main/java/com/amiya/pet/ui/MainActivity.kt", "w", encoding="utf-8") as f:
    f.write(text)

