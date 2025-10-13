//
//  ContentView.swift
//  EBookAI
//
//  SwiftUI + WebView 混合实现
//  提供原生macOS体验的EBookAI应用
//

import SwiftUI
import WebKit
import UniformTypeIdentifiers

struct ContentView: View {
    @StateObject private var appState = AppState()
    @State private var showingFileImporter = false
    @State private var showingPreferences = false

    var body: some View {
        VStack(spacing: 0) {
            // 原生标题栏
            titleBar

            // 主内容区域
            HStack(spacing: 0) {
                // 侧边栏（原生）
                if appState.showSidebar {
                    sidebar
                        .frame(width: 250)
                        .background(Color(NSColor.controlBackgroundColor))
                }

                // 主工作区（WebView）
                mainContent
            }

            // 底部状态栏
            statusBar
        }
        .background(Color(NSColor.windowBackgroundColor))
        .fileImporter(
            isPresented: $showingFileImporter,
            allowedContentTypes: [
                UTType(filenameExtension: "epub")!,
                UTType(filenameExtension: "pdf")!,
                UTType(filenameExtension: "txt")!,
                UTType(filenameExtension: "mobi")!,
                UTType(filenameExtension: "azw3")!
            ],
            allowsMultipleSelection: true
        ) { result in
            handleFileSelection(result)
        }
        .sheet(isPresented: $showingPreferences) {
            PreferencesView()
        }
        .onAppear {
            appState.startBackendService()
        }
        .onDisappear {
            appState.stopBackendService()
        }
        .onReceive(NotificationCenter.default.publisher(for: .filesSelected)) { notification in
            if let urls = notification.userInfo?["urls"] as? [URL] {
                appState.addFiles(urls)
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: .toggleSidebar)) { _ in
            appState.showSidebar.toggle()
        }
    }

    // MARK: - 标题栏
    private var titleBar: some View {
        HStack {
            Button(action: { appState.showSidebar.toggle() }) {
                Image(systemName: "sidebar.left")
            }
            .buttonStyle(PlainButtonStyle())

            Spacer()

            Text("EBookAI")
                .font(.headline)
                .foregroundColor(.primary)

            Spacer()

            HStack(spacing: 12) {
                Button(action: { showingFileImporter = true }) {
                    Image(systemName: "plus.circle")
                }
                .help("添加文件")

                Button(action: { showingPreferences = true }) {
                    Image(systemName: "gearshape")
                }
                .help("偏好设置")

                Button(action: refreshWebView) {
                    Image(systemName: "arrow.clockwise")
                }
                .help("刷新")
            }
            .buttonStyle(PlainButtonStyle())
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(Color(NSColor.controlBackgroundColor))
        .overlay(
            Rectangle()
                .frame(height: 1)
                .foregroundColor(Color(NSColor.separatorColor)),
            alignment: .bottom
        )
    }

    // MARK: - 侧边栏
    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 16) {
            // 快速访问
            VStack(alignment: .leading, spacing: 8) {
                Text("快速访问")
                    .font(.headline)
                    .foregroundColor(.secondary)

                SidebarItem(
                    icon: "doc.text",
                    title: "单文件转换",
                    isSelected: appState.selectedTab == .singleFile
                ) {
                    appState.selectedTab = .singleFile
                    appState.navigateWebView(to: "/")
                }

                SidebarItem(
                    icon: "doc.on.doc",
                    title: "批量转换",
                    isSelected: appState.selectedTab == .batchConversion
                ) {
                    appState.selectedTab = .batchConversion
                    appState.navigateWebView(to: "/?tab=batch")
                }

                SidebarItem(
                    icon: "brain.head.profile",
                    title: "AI增强",
                    isSelected: appState.selectedTab == .aiEnhancement
                ) {
                    appState.selectedTab = .aiEnhancement
                    appState.navigateWebView(to: "/ai")
                }
            }

            Spacer()

            // 最近文件
            VStack(alignment: .leading, spacing: 8) {
                Text("最近文件")
                    .font(.headline)
                    .foregroundColor(.secondary)

                ForEach(appState.recentFiles, id: \.self) { file in
                    RecentFileItem(file: file) {
                        appState.openFile(file)
                    }
                }
            }

            Spacer()
        }
        .padding(16)
        .overlay(
            Rectangle()
                .frame(width: 1)
                .foregroundColor(Color(NSColor.separatorColor)),
            alignment: .trailing
        )
    }

    // MARK: - 主内容
    private var mainContent: some View {
        GeometryReader { geometry in
            WebViewRepresentable(
                url: appState.webViewURL,
                coordinator: appState.webViewCoordinator
            )
            .background(Color.white)
            .onDrop(of: [.fileURL], isTargeted: nil) { providers in
                handleFileDrop(providers)
            }
        }
    }

    // MARK: - 状态栏
    private var statusBar: some View {
        HStack {
            // 连接状态
            HStack(spacing: 4) {
                Circle()
                    .fill(appState.isBackendConnected ? Color.green : Color.red)
                    .frame(width: 8, height: 8)

                Text(appState.isBackendConnected ? "已连接" : "连接中...")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            // 进度信息
            if let progress = appState.currentProgress {
                HStack(spacing: 8) {
                    ProgressView(value: progress.percentage / 100)
                        .frame(width: 100)

                    Text("\(Int(progress.percentage))% - \(progress.message)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            Spacer()

            // 状态信息
            Text(appState.statusMessage)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 4)
        .background(Color(NSColor.controlBackgroundColor))
        .overlay(
            Rectangle()
                .frame(height: 1)
                .foregroundColor(Color(NSColor.separatorColor)),
            alignment: .top
        )
    }

    // MARK: - 事件处理
    private func handleFileSelection(_ result: Result<[URL], Error>) {
        switch result {
        case .success(let urls):
            appState.addFiles(urls)
        case .failure(let error):
            appState.showError("文件选择失败: \(error.localizedDescription)")
        }
    }

    private func handleFileDrop(_ providers: [NSItemProvider]) -> Bool {
        for provider in providers {
            provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { item, _ in
                if let data = item as? Data,
                   let url = URL(dataRepresentation: data, relativeTo: nil) {
                    DispatchQueue.main.async {
                        appState.addFiles([url])
                    }
                }
            }
        }
        return true
    }

    private func refreshWebView() {
        appState.webViewCoordinator.reload()
    }
}

// MARK: - 侧边栏组件
struct SidebarItem: View {
    let icon: String
    let title: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .frame(width: 16)

                Text(title)
                    .font(.system(size: 13))

                Spacer()
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(
                isSelected ? Color.accentColor.opacity(0.2) : Color.clear
            )
            .cornerRadius(4)
        }
        .buttonStyle(PlainButtonStyle())
        .foregroundColor(isSelected ? .accentColor : .primary)
    }
}

struct RecentFileItem: View {
    let file: URL
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Image(systemName: "doc")
                    .frame(width: 16)

                VStack(alignment: .leading, spacing: 2) {
                    Text(file.lastPathComponent)
                        .font(.system(size: 12))
                        .lineLimit(1)

                    Text(file.deletingLastPathComponent().path)
                        .font(.system(size: 10))
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }

                Spacer()
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
        }
        .buttonStyle(PlainButtonStyle())
    }
}

// MARK: - 应用状态枚举
enum AppTab {
    case singleFile
    case batchConversion
    case aiEnhancement
}

// MARK: - 进度信息
struct ProgressInfo {
    let percentage: Double
    let message: String
}