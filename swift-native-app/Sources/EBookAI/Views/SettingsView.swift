//
//  SettingsView.swift
//  EBookAI Native
//
//  设置视图
//

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var aiService: AIService
    @Environment(\.dismiss) private var dismiss

    @State private var selectedTab: SettingsTab = .general

    var body: some View {
        NavigationSplitView {
            // 侧边栏
            settingsSidebar
                .frame(minWidth: 200, maxWidth: 250)
        } detail: {
            // 详细设置
            settingsDetail
                .frame(minWidth: 400, maxWidth: .infinity)
        }
        .navigationTitle("设置")
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                Button("完成") {
                    dismiss()
                }
            }
        }
        .frame(width: 700, height: 500)
    }

    // MARK: - 设置侧边栏
    private var settingsSidebar: some View {
        List(SettingsTab.allCases, id: \.self, selection: $selectedTab) { tab in
            Label(tab.displayName, systemImage: tab.iconName)
                .tag(tab)
        }
        .listStyle(.sidebar)
    }

    // MARK: - 设置详细内容
    @ViewBuilder
    private var settingsDetail: some View {
        switch selectedTab {
        case .general:
            GeneralSettingsView()
        case .conversion:
            ConversionSettingsView()
        case .ai:
            AISettingsView()
                .environmentObject(aiService)
        case .files:
            FileSettingsView()
        case .advanced:
            AdvancedSettingsView()
        case .about:
            AboutSettingsView()
        }
    }
}

// MARK: - 设置标签
enum SettingsTab: String, CaseIterable {
    case general = "general"
    case conversion = "conversion"
    case ai = "ai"
    case files = "files"
    case advanced = "advanced"
    case about = "about"

    var displayName: String {
        switch self {
        case .general: return "通用"
        case .conversion: return "转换"
        case .ai: return "AI"
        case .files: return "文件"
        case .advanced: return "高级"
        case .about: return "关于"
        }
    }

    var iconName: String {
        switch self {
        case .general: return "gear"
        case .conversion: return "arrow.triangle.2.circlepath"
        case .ai: return "brain.head.profile"
        case .files: return "folder"
        case .advanced: return "wrench.and.screwdriver"
        case .about: return "info.circle"
        }
    }
}

// MARK: - 通用设置
struct GeneralSettingsView: View {
    @AppStorage("startMinimized") private var startMinimized = false
    @AppStorage("closeToTray") private var closeToTray = false
    @AppStorage("autoCheckUpdates") private var autoCheckUpdates = true
    @AppStorage("showNotifications") private var showNotifications = true

    var body: some View {
        SettingsContainer(title: "通用设置") {
            VStack(alignment: .leading, spacing: 16) {
                SettingsSection("启动与关闭") {
                    Toggle("启动时最小化", isOn: $startMinimized)
                    Toggle("关闭时最小化到托盘", isOn: $closeToTray)
                }

                SettingsSection("更新与通知") {
                    Toggle("自动检查更新", isOn: $autoCheckUpdates)
                    Toggle("显示通知", isOn: $showNotifications)
                }
            }
        }
    }
}

// MARK: - 转换设置
struct ConversionSettingsView: View {
    @AppStorage("defaultOutputFormat") private var defaultOutputFormat: String = "pdf"
    @AppStorage("defaultQuality") private var defaultQuality: String = "standard"
    @AppStorage("maxConcurrentJobs") private var maxConcurrentJobs = 3
    @AppStorage("deleteOriginalAfterConversion") private var deleteOriginalAfterConversion = false

    var body: some View {
        SettingsContainer(title: "转换设置") {
            VStack(alignment: .leading, spacing: 16) {
                SettingsSection("默认设置") {
                    HStack {
                        Text("默认输出格式:")
                            .frame(width: 120, alignment: .leading)

                        Picker("", selection: $defaultOutputFormat) {
                            ForEach(FileFormat.allCases, id: \.rawValue) { format in
                                Text(format.displayName).tag(format.rawValue)
                            }
                        }
                        .pickerStyle(.menu)
                        .frame(width: 150)

                        Spacer()
                    }

                    HStack {
                        Text("默认质量:")
                            .frame(width: 120, alignment: .leading)

                        Picker("", selection: $defaultQuality) {
                            ForEach(ConversionQuality.allCases, id: \.rawValue) { quality in
                                Text(quality.displayName).tag(quality.rawValue)
                            }
                        }
                        .pickerStyle(.menu)
                        .frame(width: 150)

                        Spacer()
                    }
                }

                SettingsSection("性能") {
                    HStack {
                        Text("最大并发转换数:")
                            .frame(width: 120, alignment: .leading)

                        Stepper(value: $maxConcurrentJobs, in: 1...10) {
                            Text("\(maxConcurrentJobs)")
                        }
                        .frame(width: 100)

                        Spacer()
                    }
                }

                SettingsSection("行为") {
                    Toggle("转换完成后删除原文件", isOn: $deleteOriginalAfterConversion)
                }
            }
        }
    }
}

// MARK: - AI设置
struct AISettingsView: View {
    @EnvironmentObject var aiService: AIService
    @State private var tempAPIKey: String = ""
    @State private var showingAPIKeyAlert = false

    var body: some View {
        SettingsContainer(title: "AI设置") {
            VStack(alignment: .leading, spacing: 16) {
                SettingsSection("AI服务提供商") {
                    HStack {
                        Text("当前提供商:")
                            .frame(width: 120, alignment: .leading)

                        Picker("", selection: Binding(
                            get: { aiService.currentProvider },
                            set: { aiService.setProvider($0) }
                        )) {
                            ForEach(AIProvider.allCases, id: \.self) { provider in
                                Label(provider.displayName, systemImage: provider.iconName)
                                    .tag(provider)
                            }
                        }
                        .pickerStyle(.menu)
                        .frame(width: 150)

                        Spacer()
                    }
                }

                SettingsSection("API配置") {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("API密钥:")
                            .font(.headline)

                        HStack {
                            SecureField("输入API密钥", text: $tempAPIKey)
                                .textFieldStyle(.roundedBorder)
                                .onAppear {
                                    tempAPIKey = aiService.apiKey
                                }

                            Button("保存") {
                                aiService.setAPIKey(tempAPIKey)
                                showingAPIKeyAlert = true
                            }
                            .disabled(tempAPIKey.isEmpty)
                        }

                        Text("API密钥将安全存储在系统钥匙串中")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }

                SettingsSection("使用说明") {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("获取API密钥:")
                            .font(.subheadline)
                            .fontWeight(.medium)

                        VStack(alignment: .leading, spacing: 4) {
                            Text("• OpenAI: https://platform.openai.com/api-keys")
                            Text("• Claude: https://console.anthropic.com/")
                            Text("• Gemini: https://makersuite.google.com/app/apikey")
                        }
                        .font(.caption)
                        .foregroundColor(.secondary)
                    }
                }
            }
        }
        .alert("API密钥已保存", isPresented: $showingAPIKeyAlert) {
            Button("确定") { }
        }
    }
}

// MARK: - 文件设置
struct FileSettingsView: View {
    @AppStorage("defaultSaveLocation") private var defaultSaveLocation = ""
    @AppStorage("organizeByFormat") private var organizeByFormat = false
    @AppStorage("maxRecentFiles") private var maxRecentFiles = 20
    @AppStorage("autoCleanup") private var autoCleanup = false

    var body: some View {
        SettingsContainer(title: "文件设置") {
            VStack(alignment: .leading, spacing: 16) {
                SettingsSection("保存位置") {
                    HStack {
                        Text("默认保存位置:")
                            .frame(width: 120, alignment: .leading)

                        Text(defaultSaveLocation.isEmpty ? "自动选择" : defaultSaveLocation)
                            .foregroundColor(.secondary)
                            .lineLimit(1)

                        Spacer()

                        Button("选择...") {
                            selectSaveLocation()
                        }
                    }

                    Toggle("按格式分类保存", isOn: $organizeByFormat)
                }

                SettingsSection("历史记录") {
                    HStack {
                        Text("最近文件数量:")
                            .frame(width: 120, alignment: .leading)

                        Stepper(value: $maxRecentFiles, in: 5...100, step: 5) {
                            Text("\(maxRecentFiles)")
                        }
                        .frame(width: 100)

                        Spacer()
                    }

                    Toggle("自动清理临时文件", isOn: $autoCleanup)
                }
            }
        }
    }

    private func selectSaveLocation() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false

        if panel.runModal() == .OK {
            defaultSaveLocation = panel.url?.path ?? ""
        }
    }
}

// MARK: - 高级设置
struct AdvancedSettingsView: View {
    @AppStorage("enableDebugMode") private var enableDebugMode = false
    @AppStorage("enableExperimentalFeatures") private var enableExperimentalFeatures = false
    @AppStorage("logLevel") private var logLevel = "info"

    var body: some View {
        SettingsContainer(title: "高级设置") {
            VStack(alignment: .leading, spacing: 16) {
                SettingsSection("开发者选项") {
                    Toggle("启用调试模式", isOn: $enableDebugMode)
                    Toggle("启用实验性功能", isOn: $enableExperimentalFeatures)

                    HStack {
                        Text("日志级别:")
                            .frame(width: 120, alignment: .leading)

                        Picker("", selection: $logLevel) {
                            Text("错误").tag("error")
                            Text("警告").tag("warning")
                            Text("信息").tag("info")
                            Text("调试").tag("debug")
                        }
                        .pickerStyle(.menu)
                        .frame(width: 100)

                        Spacer()
                    }
                }

                SettingsSection("数据") {
                    VStack(alignment: .leading, spacing: 8) {
                        Button("重置所有设置") {
                            resetAllSettings()
                        }
                        .buttonStyle(.bordered)

                        Button("清除所有数据") {
                            clearAllData()
                        }
                        .buttonStyle(.bordered)

                        Text("注意：这些操作不可撤销")
                            .font(.caption)
                            .foregroundColor(.orange)
                    }
                }
            }
        }
    }

    private func resetAllSettings() {
        // 重置设置逻辑
    }

    private func clearAllData() {
        // 清除数据逻辑
    }
}

// MARK: - 关于设置
struct AboutSettingsView: View {
    var body: some View {
        SettingsContainer(title: "关于 EBookAI") {
            VStack(spacing: 20) {
                // 应用图标和信息
                HStack {
                    Image(systemName: "book.circle.fill")
                        .font(.system(size: 64))
                        .foregroundColor(.accentColor)

                    VStack(alignment: .leading, spacing: 4) {
                        Text("EBookAI Native")
                            .font(.title)
                            .fontWeight(.bold)

                        Text("版本 1.0.0")
                            .font(.subheadline)
                            .foregroundColor(.secondary)

                        Text("构建 2024.1.1")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    Spacer()
                }

                Divider()

                // 应用描述
                VStack(alignment: .leading, spacing: 12) {
                    Text("EBookAI Native 是一款专业的电子书处理工具，集成了先进的AI技术，为用户提供高质量的格式转换和内容增强服务。")
                        .font(.body)

                    Text("主要特性:")
                        .font(.headline)

                    VStack(alignment: .leading, spacing: 4) {
                        Text("• 支持多种电子书格式转换")
                        Text("• AI驱动的内容增强和优化")
                        Text("• 批量处理和自动化工作流")
                        Text("• 原生macOS体验和性能")
                    }
                    .font(.body)
                    .foregroundColor(.secondary)
                }

                Spacer()

                // 链接按钮
                HStack(spacing: 16) {
                    Button("官方网站") {
                        if let url = URL(string: "https://ebookai.com") {
                            NSWorkspace.shared.open(url)
                        }
                    }

                    Button("技术支持") {
                        if let url = URL(string: "mailto:support@ebookai.com") {
                            NSWorkspace.shared.open(url)
                        }
                    }

                    Button("开源代码") {
                        if let url = URL(string: "https://github.com/ebookai/ebookai-native") {
                            NSWorkspace.shared.open(url)
                        }
                    }
                }
                .buttonStyle(.borderless)
            }
        }
    }
}

// MARK: - 设置容器
struct SettingsContainer<Content: View>: View {
    let title: String
    let content: Content

    init(title: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.content = content()
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text(title)
                    .font(.title2)
                    .fontWeight(.semibold)

                content
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

// MARK: - 设置节
struct SettingsSection<Content: View>: View {
    let title: String
    let content: Content

    init(_ title: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title)
                .font(.headline)
                .foregroundColor(.primary)

            VStack(alignment: .leading, spacing: 8) {
                content
            }
            .padding(.leading, 16)
        }
    }
}

// MARK: - 预览
#Preview {
    SettingsView()
        .environmentObject(AIService.shared)
}