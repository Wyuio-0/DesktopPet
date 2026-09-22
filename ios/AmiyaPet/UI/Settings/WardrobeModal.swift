import SwiftUI

public struct WardrobeModal: View {
    @ObservedObject var skinRepo = PetSkinRepository.shared
    @ObservedObject var voicePlayer = VoicePlayer.shared
    @Environment(\.dismiss) var dismiss

    public init() {}

    public var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // 当前所选形态大图预览
                    VStack(spacing: 8) {
                        Image(skinRepo.currentSkin.defaultAssetName)
                            .resizable()
                            .scaledToFit()
                            .frame(height: 180)
                            .shadow(radius: 6)

                        Text(skinRepo.currentSkin.name)
                            .font(.system(size: 20, weight: .bold))
                            .foregroundColor(Color(hex: skinRepo.currentSkin.themeColor))

                        Text(skinRepo.currentSkin.description)
                            .font(.system(size: 13))
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 24)
                    }
                    .padding(.vertical, 12)

                    // 皮肤选择卡片
                    VStack(alignment: .leading, spacing: 12) {
                        Text("形态衣橱")
                            .font(.system(size: 15, weight: .bold))
                            .padding(.horizontal)

                        ForEach(skinRepo.currentOperator.skins) { skin in
                            let isSelected = skin.id == skinRepo.currentSkin.id
                            HStack(spacing: 14) {
                                Image(skin.defaultAssetName)
                                    .resizable()
                                    .scaledToFit()
                                    .frame(width: 50, height: 50)

                                VStack(alignment: .leading, spacing: 4) {
                                    Text(skin.name)
                                        .font(.system(size: 16, weight: .bold))
                                    Text(skin.description)
                                        .font(.system(size: 12))
                                        .foregroundColor(.secondary)
                                        .lineLimit(1)
                                }

                                Spacer()

                                if isSelected {
                                    Image(systemName: "checkmark.circle.fill")
                                        .foregroundColor(Color(hex: skin.themeColor))
                                        .font(.system(size: 22))
                                }
                            }
                            .padding()
                            .amiyaCardStyle()
                            .overlay(
                                RoundedRectangle(cornerRadius: 14)
                                    .stroke(isSelected ? Color(hex: skin.themeColor) : Color.clear, lineWidth: 2)
                            )
                            .padding(.horizontal)
                            .contentShape(Rectangle())
                            .onTapGesture {
                                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                                skinRepo.setSkin(skinId: skin.id)
                                voicePlayer.playRandomInteractionVoice()
                            }
                        }
                    }

                    // 语音试听库
                    VStack(alignment: .leading, spacing: 12) {
                        Text("干员原声试听")
                            .font(.system(size: 15, weight: .bold))
                            .padding(.horizontal)

                        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                            ForEach(VoicePlayer.VOICE_LINES) { line in
                                Button(action: {
                                    voicePlayer.play(voiceLine: line)
                                }) {
                                    HStack {
                                        Image(systemName: "speaker.wave.2")
                                            .font(.system(size: 12))
                                        Text(line.title)
                                            .font(.system(size: 13, weight: .medium))
                                        Spacer()
                                    }
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 10)
                                    .background(Color.amiyaCardBg)
                                    .cornerRadius(10)
                                }
                                .buttonStyle(PlainButtonStyle())
                            }
                        }
                        .padding(.horizontal)
                    }
                }
                .padding(.bottom, 24)
            }
            .navigationTitle("干员衣橱与原声")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("完成") { dismiss() }
                }
            }
        }
    }
}
