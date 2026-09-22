import SwiftUI

public struct SettingsView: View {
    @ObservedObject var skinRepo = PetSkinRepository.shared
    @State private var showWardrobe = false
    @State private var showAIConfig = false
    @State private var showSync = false
    @State private var showScheduleSettings = false
    @State private var showExport = false

    @State private var isCheckingUpdate = false
    @State private var updateInfo: ReleaseInfo?
    @State private var showUpdateAlert = false

    public init() {}

    public var body: some View {
        NavigationStack {
            List {
                // 干员立绘与衣橱
                Section(header: Text("干员与形态")) {
                    Button(action: { showWardrobe = true }) {
                        HStack(spacing: 12) {
                            Image(skinRepo.currentSkin.defaultAssetName)
                                .resizable()
                                .scaledToFit()
                                .frame(width: 40, height: 40)
                            VStack(alignment: .leading, spacing: 2) {
                                Text("干员衣橱与原声")
                                    .font(.system(size: 16, weight: .semibold))
                                    .foregroundColor(.primary)
                                Text("当前形态：\(skinRepo.currentSkin.name)")
                                    .font(.system(size: 12))
                                    .foregroundColor(.secondary)
                            }
                            Spacer()
                            Image(systemName: "chevron.right")
                                .font(.system(size: 12))
                                .foregroundColor(.secondary)
                        }
                    }
                }

                // 核心功能设置
                Section(header: Text("智能体与数据协同")) {
                    Button(action: { showAIConfig = true }) {
                        settingRow(icon: "brain.head.profile", title: "AI 神经元配置", subtitle: "DeepSeek / 智谱大模型端点与 API Key")
                    }
                    Button(action: { showScheduleSettings = true }) {
                        settingRow(icon: "calendar.badge.clock", title: "课表作息与提醒", subtitle: "开学日期、周起始日、灵动岛通知")
                    }
                    Button(action: { showExport = true }) {
                        settingRow(icon: "calendar", title: "系统日历同步与导出", subtitle: "一键导入 Apple 日历或导出 .ics")
                    }
                    Button(action: { showSync = true }) {
                        settingRow(icon: "network", title: "跨设备局域网互联", subtitle: "与 PC 桌面端、安卓手机端配对快传")
                    }
                }

                // 关于与更新检测
                Section(header: Text("关于阿米娅桌宠")) {
                    HStack {
                        Text("当前版本")
                        Spacer()
                        Text("v\(UpdateManager.currentVersion)")
                            .foregroundColor(.secondary)
                    }

                    Button(action: checkUpdate) {
                        HStack {
                            Text("检查最新版本更新")
                            Spacer()
                            if isCheckingUpdate {
                                ProgressView()
                            } else {
                                Image(systemName: "arrow.triangle.2.circlepath")
                                    .foregroundColor(.secondary)
                            }
                        }
                    }

                    Link(destination: URL(string: "https://github.com/Wyuio-0/DesktopPet")!) {
                        HStack {
                            Text("GitHub 开源仓库")
                            Spacer()
                            Image(systemName: "arrow.up.right")
                                .font(.system(size: 12))
                                .foregroundColor(.secondary)
                        }
                    }
                }
            }
            .navigationTitle("系统设置")
            .navigationBarTitleDisplayMode(.inline)
            .sheet(isPresented: $showWardrobe) { WardrobeModal() }
            .sheet(isPresented: $showAIConfig) { AIConfigModal() }
            .sheet(isPresented: $showSync) { SyncModal() }
            .sheet(isPresented: $showScheduleSettings) { ScheduleSettingsModal() }
            .sheet(isPresented: $showExport) { IcsExportModal() }
            .alert("发现新版本", isPresented: $showUpdateAlert) {
                if let info = updateInfo, let url = URL(string: info.htmlUrl) {
                    Link("前往下载", destination: url)
                    Button("稍后", role: .cancel) {}
                }
            } message: {
                if let info = updateInfo {
                    Text("最新版本: \(info.tagName)\n\n\(info.releaseNotes)")
                }
            }
        }
    }

    private func settingRow(icon: String, title: String, subtitle: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 18))
                .foregroundColor(Color.amiyaPrimary)
                .frame(width: 24)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.system(size: 15, weight: .medium))
                    .foregroundColor(.primary)
                Text(subtitle)
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
            }
            Spacer()
            Image(systemName: "chevron.right")
                .font(.system(size: 12))
                .foregroundColor(.secondary)
        }
    }

    private func checkUpdate() {
        isCheckingUpdate = true
        UpdateManager.shared.checkUpdate { result in
            isCheckingUpdate = false
            switch result {
            case .success(let info):
                if let info = info, info.hasUpdate {
                    self.updateInfo = info
                    self.showUpdateAlert = true
                }
            case .failure(let err):
                print("Update check error: \(err)")
            }
        }
    }
}
