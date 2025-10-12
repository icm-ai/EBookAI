//
//  PreferencesView.swift
//  EBookAI
//
//  应用偏好设置界面
//

import SwiftUI

struct PreferencesView: View {
    @State private var selectedTab: PreferenceTab = .general
    @Environment(\.presentationMode) var presentationMode

    var body: some View {
        VStack(spacing: 0) {
            // 标题栏
            HStack {
                Text("偏好设置")
                    .font(.title2)
                    .fontWeight(.medium)

                Spacer()

                Button("完成") {
                    presentationMode.wrappedValue.dismiss()
                }
                .keyboardShortcut(.defaultAction)
            }
            .padding()
            .background(Color(NSColor.controlBackgroundColor))

            // 主内容
            HSplitView {
                // 侧边栏
                sidebar
                    .frame(minWidth: 200, maxWidth: 200)

                // 设置内容
                settingsContent
                    .frame(minWidth: 400)
            }
            .frame(minHeight: 500)
        }
        .frame(width: 650, height: 500)
    }

    // MARK: - 侧边栏
    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 4) {
            PreferenceTabButton(
                icon: "gear",
                title: "通用",
                tab: .general,
                selectedTab: $selectedTab
            )

            PreferenceTabButton(
                icon: "arrow.triangle.2.circlepath",
                title: "转换设置",
                tab: .conversion,
                selectedTab: $selectedTab
            )

            PreferenceTabButton(
                icon: "brain.head.profile",
                title: "AI配置",
                tab: .ai,
                selectedTab: $selectedTab
            )

            PreferenceTabButton(
                icon: "folder",
                title: "文件管理",
                tab: .files,
                selectedTab: $selectedTab
            )

            PreferenceTabButton(
                icon: "info.circle",
                title: "关于",
                tab: .about,
                selectedTab: $selectedTab
            )

            Spacer()
        }
        .padding(.vertical, 16)
        .background(Color(NSColor.controlBackgroundColor))
    }

    // MARK: - 设置内容
    @ViewBuilder
    private var settingsContent: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                switch selectedTab {
                case .general:
                    GeneralSettingsView()
                case .conversion:
                    ConversionSettingsView()
                case .ai:
                    AISettingsView()
                case .files:
                    FileSettingsView()
                case .about:
                    AboutView()
                }
            }
            .padding(24)
        }
        .background(Color(NSColor.textBackgroundColor))
    }
}

// MARK: - 偏好设置标签页按钮
struct PreferenceTabButton: View {
    let icon: String
    let title: String
    let tab: PreferenceTab
    @Binding var selectedTab: PreferenceTab

    var body: some View {
        Button(action: { selectedTab = tab }) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .frame(width: 16)
                    .foregroundColor(selectedTab == tab ? .accentColor : .secondary)

                Text(title)
                    .font(.system(size: 13))
                    .foregroundColor(selectedTab == tab ? .primary : .secondary)

                Spacer()
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(
                selectedTab == tab ? Color.accentColor.opacity(0.15) : Color.clear
            )
            .cornerRadius(6)
        }
        .buttonStyle(PlainButtonStyle())
        .padding(.horizontal, 8)
    }
}

// MARK: - 通用设置
struct GeneralSettingsView: View {
    @AppStorage("startBackendOnLaunch") private var startBackendOnLaunch = true
    @AppStorage("showSidebarOnLaunch") private var showSidebarOnLaunch = true
    @AppStorage("rememberWindowPosition") private var rememberWindowPosition = true

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("通用设置")
                .font(.title2)
                .fontWeight(.medium)

            VStack(alignment: .leading, spacing: 12) {
                Toggle("启动时自动开启后端服务", isOn: $startBackendOnLaunch)

                Toggle("启动时显示侧边栏", isOn: $showSidebarOnLaunch)

                Toggle("记住窗口位置", isOn: $rememberWindowPosition)
            }
        }
    }
}

// MARK: - 转换设置
struct ConversionSettingsView: View {
    @AppStorage("defaultOutputFormat") private var defaultOutputFormat = "pdf"
    @AppStorage("deleteOriginalAfterConversion") private var deleteOriginalAfterConversion = false
    @AppStorage("maxConcurrentConversions") private var maxConcurrentConversions = 3

    private let outputFormats = ["pdf", "epub", "txt", "mobi", "azw3"]

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("转换设置")
                .font(.title2)
                .fontWeight(.medium)

            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("默认输出格式:")
                        .frame(width: 120, alignment: .leading)

                    Picker("", selection: $defaultOutputFormat) {
                        ForEach(outputFormats, id: \.self) { format in
                            Text(format.uppercased()).tag(format)
                        }
                    }
                    .pickerStyle(MenuPickerStyle())
                    .frame(width: 100)

                    Spacer()
                }

                Toggle("转换完成后删除原文件", isOn: $deleteOriginalAfterConversion)

                HStack {
                    Text("最大并发转换数:")
                        .frame(width: 120, alignment: .leading)

                    Stepper(value: $maxConcurrentConversions, in: 1...10) {
                        Text("\(maxConcurrentConversions)")
                    }
                    .frame(width: 100)

                    Spacer()
                }
            }
        }
    }
}

// MARK: - AI设置
struct AISettingsView: View {
    @AppStorage("aiProvider") private var aiProvider = "openai"
    @AppStorage("openaiApiKey") private var openaiApiKey = ""
    @AppStorage("claudeApiKey") private var claudeApiKey = ""

    private let aiProviders = ["openai", "claude"]

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("AI配置")
                .font(.title2)
                .fontWeight(.medium)

            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("AI服务提供商:")
                        .frame(width: 120, alignment: .leading)

                    Picker("", selection: $aiProvider) {
                        Text("OpenAI").tag("openai")
                        Text("Claude").tag("claude")
                    }
                    .pickerStyle(MenuPickerStyle())
                    .frame(width: 120)

                    Spacer()
                }

                if aiProvider == "openai" {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("OpenAI API Key:")
                            .font(.caption)

                        SecureField("输入 OpenAI API Key", text: $openaiApiKey)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                    }
                }

                if aiProvider == "claude" {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Claude API Key:")
                            .font(.caption)

                        SecureField("输入 Claude API Key", text: $claudeApiKey)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                    }
                }

                Text("API Key将安全存储在本地钥匙串中")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }
}

// MARK: - 文件管理设置
struct FileSettingsView: View {
    @AppStorage("defaultDownloadLocation") private var defaultDownloadLocation = "~/Downloads"
    @AppStorage("organizeFilesByFormat") private var organizeFilesByFormat = false
    @AppStorage("maxRecentFiles") private var maxRecentFiles = 10

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("文件管理")
                .font(.title2)
                .fontWeight(.medium)

            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("默认下载位置:")
                        .frame(width: 120, alignment: .leading)

                    Text(defaultDownloadLocation)
                        .foregroundColor(.secondary)

                    Spacer()

                    Button("选择...") {
                        selectDownloadLocation()
                    }
                }

                Toggle("按格式组织文件", isOn: $organizeFilesByFormat)

                HStack {
                    Text("最近文件数量:")
                        .frame(width: 120, alignment: .leading)

                    Stepper(value: $maxRecentFiles, in: 5...50) {
                        Text("\(maxRecentFiles)")
                    }
                    .frame(width: 100)

                    Spacer()
                }
            }
        }
    }

    private func selectDownloadLocation() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false

        if panel.runModal() == .OK {
            if let url = panel.url {
                defaultDownloadLocation = url.path
            }
        }
    }
}

// MARK: - 关于页面
struct AboutView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("关于 EBookAI")
                .font(.title2)
                .fontWeight(.medium)

            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Image(systemName: "book.circle.fill")
                        .font(.system(size: 64))
                        .foregroundColor(.accentColor)

                    VStack(alignment: .leading, spacing: 4) {
                        Text("EBookAI")
                            .font(.title)
                            .fontWeight(.bold)

                        Text("版本 1.0.0")
                            .font(.subheadline)
                            .foregroundColor(.secondary)

                        Text("智能电子书转换工具")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    Spacer()
                }

                Divider()

                Text("EBookAI 是一款现代化的电子书处理平台，集成了先进的AI技术，支持多种格式转换、智能排版和内容生成。")
                    .font(.body)
                    .foregroundColor(.secondary)

                HStack {
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

                    Spacer()
                }
            }
        }
    }
}

// MARK: - 偏好设置标签枚举
enum PreferenceTab: CaseIterable {
    case general
    case conversion
    case ai
    case files
    case about
}