import SwiftUI

public struct SyncModal: View {
    @ObservedObject var syncManager = SyncManager.shared
    @Environment(\.dismiss) var dismiss
    @State private var remoteAddress = ""
    @State private var pairingSecret = ""
    @State private var localInvite = ""
    @State private var dropText = ""
    public init() {}
    public var body: some View {
        NavigationStack {
            Form {
                Section(header: Text("加密同步 v2")) {
                    Toggle("开启跨设备互联", isOn: Binding(get: { syncManager.isRunning }, set: { value in
                        if value { syncManager.start() } else { syncManager.stop() }
                    }))
                    Text(syncManager.statusText).font(.footnote)
                    Button("生成并复制本机配对密钥") {
                        localInvite = syncManager.createPairingInvite()
                        UIPasteboard.general.string = localInvite
                    }.disabled(!syncManager.isRunning)
                    if !localInvite.isEmpty { Text("密钥已复制，5 分钟有效。请粘贴到另一台设备，再在此确认配对。").font(.footnote) }
                    SecureField("粘贴目标设备生成的配对密钥", text: $pairingSecret)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                    if !pairingSecret.isEmpty { Text("核对码：" + ((try? SyncCrypto.pairingCode(pairingSecret.trimmingCharacters(in: .whitespacesAndNewlines))) ?? "无效密钥")).font(.footnote) }
                    TextField("目标 IP:端口（PC 默认 23333）", text: $remoteAddress)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                    Button("请求加密配对") {
                        let parts = remoteAddress.trimmingCharacters(in: .whitespaces).split(separator: ":")
                        if let ip = parts.first { syncManager.requestPair(ip: String(ip), port: parts.count == 2 ? (Int(parts[1]) ?? 23333) : 23333, secret: pairingSecret.trimmingCharacters(in: .whitespacesAndNewlines)) }
                    }.disabled(!syncManager.isRunning || pairingSecret.isEmpty || remoteAddress.isEmpty)
                    Text("旧配对需要重新建立。配对密钥请只在自己的设备间传递；发现设备不会自动授予访问权限。").font(.footnote)
                }
                Section(header: Text("发现附近设备")) {
                    Button("扫描 PC / Android / iOS") { syncManager.broadcastSelf() }.disabled(!syncManager.isRunning)
                    ForEach(syncManager.discoveredDevices) { device in
                        HStack {
                            VStack(alignment: .leading) { Text(device.deviceName); Text("\(device.ip):\(device.httpPort)").font(.caption) }
                            Spacer()
                            Button("配对") { syncManager.requestPair(ip: device.ip, port: device.httpPort, secret: pairingSecret.trimmingCharacters(in: .whitespacesAndNewlines)) }
                                .disabled(pairingSecret.isEmpty)
                        }
                    }
                }
                Section(header: Text("已配对设备")) {
                    TextField("快传文本", text: $dropText)
                    ForEach(syncManager.pairedDevices) { device in
                        VStack(alignment: .leading) {
                            Text(device.deviceName)
                            HStack {
                                Button("合并拉取") { syncManager.pull(device) }
                                Button("合并推送") { syncManager.push(device) }
                                Button("快传") { syncManager.sendTacticalDrop(to: device, text: dropText) }.disabled(dropText.isEmpty)
                                Button("解除配对", role: .destructive) { syncManager.unpair(device) }
                            }.buttonStyle(.bordered)
                        }
                    }
                }
            }
            .navigationTitle("跨端加密互联")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("完成") { dismiss() } } }
            .alert(item: $syncManager.incomingPair) { request in
                Alert(title: Text("确认加密配对"), message: Text("设备：\(request.name)\n地址：\(request.ip)\n核对码：\(request.pin)\n仅确认您自己发起的请求。"),
                    primaryButton: .default(Text("确认")) { syncManager.confirmPair(request.id, accept: true) },
                    secondaryButton: .cancel(Text("拒绝")) { syncManager.confirmPair(request.id, accept: false) })
            }
        }
    }
}
