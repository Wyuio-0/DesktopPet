import SwiftUI

public struct SyncModal: View {
    @ObservedObject var syncManager = SyncManager.shared
    @Environment(\.dismiss) var dismiss
    @State private var testDropText: String = ""

    public init() {}

    public var body: some View {
        NavigationStack {
            Form {
                Section(header: Text("局域网互联状态")) {
                    Toggle("开启跨设备互联监听", isOn: $syncManager.isRunning)
                        .onChange(of: syncManager.isRunning) { running in
                            if running {
                                syncManager.start()
                            } else {
                                syncManager.stop()
                            }
                        }

                    Button("向局域网广播本设备") {
                        syncManager.broadcastSelf()
                    }
                    .disabled(!syncManager.isRunning)
                }

                Section(header: Text("已发现的局域网设备 (PC/Android)")) {
                    if syncManager.discoveredDevices.isEmpty {
                        Text("暂未扫描到同一 Wi-Fi 下的其他阿米娅设备...")
                            .font(.system(size: 13))
                            .foregroundColor(.secondary)
                    } else {
                        ForEach(syncManager.discoveredDevices) { dev in
                            HStack {
                                Image(systemName: dev.deviceType == "pc" ? "desktopcomputer" : "iphone")
                                    .foregroundColor(Color.amiyaPrimary)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(dev.deviceName)
                                        .font(.system(size: 15, weight: .bold))
                                    Text("\(dev.ip):\(dev.httpPort) · v\(dev.version)")
                                        .font(.system(size: 11))
                                        .foregroundColor(.secondary)
                                }
                                Spacer()
                                Button("快传") {
                                    syncManager.sendTacticalDrop(to: dev, text: "来自阿米娅 (iOS) 的战术快传联络！")
                                }
                                .font(.system(size: 12))
                                .buttonStyle(.borderedProminent)
                            }
                        }
                    }
                }
            }
            .navigationTitle("跨端协同互联")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("完成") { dismiss() }
                }
            }
        }
    }
}
