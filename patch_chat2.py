
import re

with open("android/app/src/main/java/com/amiya/pet/ui/ChatView.kt", "r", encoding="utf-8") as f:
    text = f.read()

pet_overlay = """            // Floating Pet Overlay
            Box(
                modifier = Modifier
                    .padding(8.dp)
                    .size(130.dp)
                    .align(Alignment.TopStart)
                    .pointerInput(Unit) {
                        detectTapGestures(
                            onTap = { 
                                stateMachine?.onUserClick()
                                voicePlayer.playClickVoice()
                            },
                            onDoubleTap = { 
                                stateMachine?.onUserDoubleClick()
                                voicePlayer.playGreetVoice()
                            }
                        )
                    },
                contentAlignment = Alignment.Center
            ) {
                AndroidView(
                    factory = { ctx ->
                        PetGlSurfaceView(ctx).apply {
                            layoutParams = FrameLayout.LayoutParams(
                                ViewGroup.LayoutParams.MATCH_PARENT,
                                ViewGroup.LayoutParams.MATCH_PARENT
                            )
                            onPlaybackEnded = {
                                stateMachine?.onClipPlaybackEnded()
                            }
                            petView = this
                        }
                    },
                    modifier = Modifier.fillMaxSize()
                )
            }
        }
    }

    if (showCharDialog) {"""

text = text.replace("    }\n\n    if (showCharDialog) {", pet_overlay)

with open("android/app/src/main/java/com/amiya/pet/ui/ChatView.kt", "w", encoding="utf-8") as f:
    f.write(text)

