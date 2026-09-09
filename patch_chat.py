
import re

with open("android/app/src/main/java/com/amiya/pet/ui/ChatView.kt", "r", encoding="utf-8") as f:
    text = f.read()

old_block = """        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // Pet rendering area
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(130.dp)
                    .background(Color(0xFF161920))
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
                contentAlignment = Alignment.CenterStart
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
                    modifier = Modifier.fillMaxHeight().aspectRatio(1f)
                )
            }
            
            Spacer(modifier = Modifier.height(1.dp).fillMaxWidth().background(Color(0xFF2A2E38)))

            // Chat messages"""

new_block = """        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            Column(
                modifier = Modifier.fillMaxSize()
            ) {
                // Chat messages"""

text = text.replace(old_block, new_block)

# Add the pet back at the end of the Scaffold block
# Find the end of the Scaffold block
scaffold_end = """                }
            }
        }
    }
}"""
pet_overlay = """                }
            }
            
            // Floating Pet Overlay
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
}"""

text = text.replace(scaffold_end, pet_overlay)

with open("android/app/src/main/java/com/amiya/pet/ui/ChatView.kt", "w", encoding="utf-8") as f:
    f.write(text)

