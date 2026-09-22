import SwiftUI

public struct AmiyaPetDockView: View {
    @ObservedObject var skinRepo = PetSkinRepository.shared
    @ObservedObject var voicePlayer = VoicePlayer.shared
    @State private var petState: PetState = .normal
    @State private var dragOffset: CGSize = .zero
    @State private var isBouncing: Bool = false

    public init() {}

    public var body: some View {
        VStack(spacing: 6) {
            // 语音气泡
            if let subtitle = voicePlayer.currentSubtitle {
                HStack(spacing: 6) {
                    Image(systemName: "quote.bubble.fill")
                        .foregroundColor(Color.amiyaPrimary)
                        .font(.system(size: 13))
                    Text(subtitle)
                        .font(.system(size: 13, weight: .medium))
                        .foregroundColor(.primary)
                        .lineLimit(2)
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .background(Color.amiyaCardBg)
                .cornerRadius(18)
                .shadow(color: Color.black.opacity(0.08), radius: 6, x: 0, y: 3)
                .transition(.asymmetric(insertion: .scale.combined(with: .opacity), removal: .opacity))
            }

            // 互动立绘桌宠
            ZStack {
                let assetName = skinRepo.currentSkin.assetName(for: petState)
                Image(assetName)
                    .resizable()
                    .scaledToFit()
                    .frame(height: 110)
                    .shadow(color: Color.black.opacity(0.12), radius: 8, x: 0, y: 4)
                    .offset(y: isBouncing ? -4 : 0)
                    .offset(dragOffset)
                    .gesture(
                        DragGesture()
                            .onChanged { value in
                                petState = .dragging
                                dragOffset = CGSize(width: value.translation.width * 0.4, height: value.translation.height * 0.4)
                            }
                            .onEnded { _ in
                                withAnimation(.spring(response: 0.35, dampingFraction: 0.5)) {
                                    dragOffset = .zero
                                    petState = .normal
                                }
                            }
                    )
                    .onTapGesture {
                        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                        withAnimation(.spring(response: 0.25, dampingFraction: 0.4)) {
                            isBouncing = true
                        }
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                            isBouncing = false
                        }
                        voicePlayer.playRandomInteractionVoice()
                    }
            }
            .padding(.top, 4)

            // 干员形态徽章
            HStack(spacing: 4) {
                Text(skinRepo.currentSkin.name)
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(Color(hex: skinRepo.currentSkin.themeColor))
                if voicePlayer.isPlaying {
                    Image(systemName: "waveform")
                        .font(.system(size: 10))
                        .foregroundColor(Color(hex: skinRepo.currentSkin.themeColor))
                }
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 2)
            .background(Color.amiyaCardBg.opacity(0.9))
            .cornerRadius(10)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .animation(.spring(), value: voicePlayer.currentSubtitle)
    }
}
