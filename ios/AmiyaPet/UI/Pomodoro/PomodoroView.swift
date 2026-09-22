import SwiftUI

public struct PomodoroView: View {
    @ObservedObject var timer = PomodoroTimer.shared
    @ObservedObject var skinRepo = PetSkinRepository.shared
    @State private var customMinutes: Int = 25

    private let presets = [15, 25, 45, 60]

    public init() {}

    public var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    // 伴学阿米娅状态卡片
                    HStack(spacing: 16) {
                        let assetName = skinRepo.currentSkin.assetName(for: timer.state == .running ? .focusing : .normal)
                        Image(assetName)
                            .resizable()
                            .scaledToFit()
                            .frame(width: 60, height: 60)
                            .shadow(radius: 4)

                        VStack(alignment: .leading, spacing: 4) {
                            Text(timer.state == .running ? "阿米娅正与您共同专注..." : "准备好开始了吗，博士？")
                                .font(.system(size: 15, weight: .bold))
                            Text(timer.state == .running ? "保持心无旁骛，罗德岛的未来因您的专注而更加明晰。" : "点击下方按钮开启一段高效的学习或工作时光。")
                                .font(.system(size: 12))
                                .foregroundColor(.secondary)
                        }
                        Spacer()
                    }
                    .padding()
                    .amiyaCardStyle()
                    .padding(.horizontal)
                    .padding(.top, 8)

                    // 环形倒计时仪表盘
                    ZStack {
                        // 背景圆环
                        Circle()
                            .stroke(Color.secondary.opacity(0.12), lineWidth: 16)
                            .frame(width: 240, height: 240)

                        // 进度圆环
                        Circle()
                            .trim(from: 0, to: CGFloat(timer.progress))
                            .stroke(
                                AngularGradient(
                                    gradient: Gradient(colors: [Color.amiyaPrimary, Color.amiyaCyan]),
                                    center: .center,
                                    startAngle: .degrees(0),
                                    endAngle: .degrees(360)
                                ),
                                style: StrokeStyle(lineWidth: 16, lineCap: .round)
                            )
                            .rotationEffect(.degrees(-90))
                            .frame(width: 240, height: 240)
                            .animation(.linear(duration: 0.5), value: timer.progress)

                        // 核心时间文案
                        VStack(spacing: 6) {
                            Text(timer.mode.title)
                                .font(.system(size: 14, weight: .medium))
                                .foregroundColor(.secondary)

                            Text(timer.formattedTime)
                                .font(.system(size: 48, weight: .bold, design: .rounded))
                                .foregroundColor(.primary)

                            Text(statusDescription)
                                .font(.system(size: 12))
                                .foregroundColor(Color.amiyaPrimary)
                        }
                    }
                    .padding(.vertical, 12)

                    // 预设时长选择
                    if timer.state == .idle {
                        HStack(spacing: 12) {
                            ForEach(presets, id: \.self) { m in
                                Button(action: {
                                    customMinutes = m
                                    timer.startFocus(minutes: m)
                                }) {
                                    Text("\(m) 分钟")
                                        .font(.system(size: 14, weight: .semibold))
                                        .padding(.horizontal, 14)
                                        .padding(.vertical, 8)
                                        .background(customMinutes == m ? Color.amiyaPrimary : Color.secondary.opacity(0.1))
                                        .foregroundColor(customMinutes == m ? .white : .primary)
                                        .cornerRadius(12)
                                }
                            }
                        }
                        .padding(.horizontal)
                    }

                    // 核心操作按钮组
                    HStack(spacing: 20) {
                        if timer.state == .idle {
                            Button(action: { timer.startFocus(minutes: customMinutes) }) {
                                HStack {
                                    Image(systemName: "play.fill")
                                    Text("开启专注")
                                }
                                .font(.system(size: 16, weight: .bold))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 14)
                                .background(Color.amiyaPrimary)
                                .foregroundColor(.white)
                                .cornerRadius(14)
                            }
                        } else if timer.state == .running {
                            Button(action: { timer.pause() }) {
                                HStack {
                                    Image(systemName: "pause.fill")
                                    Text("暂停")
                                }
                                .font(.system(size: 16, weight: .semibold))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 14)
                                .background(Color.secondary.opacity(0.15))
                                .foregroundColor(.primary)
                                .cornerRadius(14)
                            }

                            Button(action: { timer.reset() }) {
                                HStack {
                                    Image(systemName: "stop.fill")
                                    Text("重置")
                                }
                                .font(.system(size: 16, weight: .semibold))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 14)
                                .background(Color.red.opacity(0.15))
                                .foregroundColor(.red)
                                .cornerRadius(14)
                            }
                        } else if timer.state == .paused {
                            Button(action: { timer.resume() }) {
                                HStack {
                                    Image(systemName: "play.fill")
                                    Text("继续")
                                }
                                .font(.system(size: 16, weight: .bold))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 14)
                                .background(Color.amiyaPrimary)
                                .foregroundColor(.white)
                                .cornerRadius(14)
                            }

                            Button(action: { timer.reset() }) {
                                HStack {
                                    Image(systemName: "arrow.counterclockwise")
                                    Text("放弃")
                                }
                                .font(.system(size: 16, weight: .semibold))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 14)
                                .background(Color.secondary.opacity(0.15))
                                .foregroundColor(.secondary)
                                .cornerRadius(14)
                            }
                        } else if timer.state == .completed {
                            Button(action: { timer.startBreak(minutes: 5) }) {
                                HStack {
                                    Image(systemName: "cup.and.saucer.fill")
                                    Text("进入5分钟休息")
                                }
                                .font(.system(size: 16, weight: .bold))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 14)
                                .background(Color.green)
                                .foregroundColor(.white)
                                .cornerRadius(14)
                            }
                        }
                    }
                    .padding(.horizontal, 32)
                }
                .padding(.bottom, 24)
            }
            .navigationTitle("战术专注")
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    private var statusDescription: String {
        switch timer.state {
        case .idle: return "就绪"
        case .running: return "正在专注倒计时"
        case .paused: return "已暂停"
        case .completed: return "专注达成！"
        }
    }
}
