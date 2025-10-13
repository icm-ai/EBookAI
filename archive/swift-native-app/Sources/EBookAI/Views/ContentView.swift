//
//  ContentView.swift
//  EBookAI Native
//
//  主界面视图
//

import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @EnvironmentObject var conversionService: ConversionService
    @EnvironmentObject var aiService: AIService
    @EnvironmentObject var fileManager: FileManagerService

    @State private var selectedTab: MainTab = .files
    @State private var showingSidebar = true
    @State private var showingSettings = false
    @State private var showingFileImporter = false

    var body: some View {
        NavigationSplitView(sidebar: {
            if showingSidebar {
                SidebarView(selectedTab: $selectedTab)
                    .frame(minWidth: 250, maxWidth: 300)
            }
        }, detail: {
            mainContent
                .toolbar {
                    ToolbarItemGroup(placement: .navigation) {
                        Button(action: { showingSidebar.toggle() }) {
                            Image(systemName: "sidebar.left")
                        }
                        .help("切换侧边栏")
                    }

                    ToolbarItemGroup(placement: .primaryAction) {
                        Button(action: { showingFileImporter = true }) {
                            Image(systemName: "plus.circle")
                        }
                        .help("添加文件")

                        Button(action: { showingSettings = true }) {
                            Image(systemName: "gearshape")
                        }
                        .help("设置")
                    }
                }
        })
        .fileImporter(
            isPresented: $showingFileImporter,
            allowedContentTypes: supportedFileTypes,
            allowsMultipleSelection: true
        ) { result in
            handleFileImport(result)
        }
        .sheet(isPresented: $showingSettings) {
            SettingsView()
                .environmentObject(aiService)
        }
        .onReceive(NotificationCenter.default.publisher(for: .addFiles)) { _ in
            showingFileImporter = true
        }
        .onReceive(NotificationCenter.default.publisher(for: .showFileList)) { _ in
            selectedTab = .files
        }
        .onReceive(NotificationCenter.default.publisher(for: .showConversionQueue)) { _ in
            selectedTab = .conversion
        }
        .onReceive(NotificationCenter.default.publisher(for: .showAITools)) { _ in
            selectedTab = .ai
        }
    }

    // MARK: - 主内容区域
    @ViewBuilder
    private var mainContent: some View {
        switch selectedTab {
        case .files:
            FileListView()
                .environmentObject(fileManager)
        case .conversion:
            ConversionView()
                .environmentObject(conversionService)
        case .ai:
            AIToolsView()
                .environmentObject(aiService)
        case .batch:
            BatchConversionView()
                .environmentObject(conversionService)
        case .settings:
            SettingsView()
                .environmentObject(aiService)
        }
    }

    // MARK: - 支持的文件类型
    private var supportedFileTypes: [UTType] {
        FileFormat.allCases.compactMap { format in
            switch format {
            case .epub:
                return UTType(mimeType: format.mimeType)
            case .pdf:
                return .pdf
            case .txt:
                return .plainText
            case .docx:
                return UTType(mimeType: format.mimeType)
            case .html:
                return .html
            case .markdown:
                return UTType(mimeType: format.mimeType)
            default:
                return UTType(mimeType: format.mimeType)
            }
        }
    }

    // MARK: - 文件导入处理
    private func handleFileImport(_ result: Result<[URL], Error>) {
        switch result {
        case .success(let urls):
            Task {
                await fileManager.addFiles(urls)
            }
        case .failure(let error):
            // 处理错误
            print("文件导入失败: \(error)")
        }
    }
}

// MARK: - 主标签页
enum MainTab: String, CaseIterable {
    case files = "files"
    case conversion = "conversion"
    case ai = "ai"
    case batch = "batch"
    case settings = "settings"

    var displayName: String {
        switch self {
        case .files: return "文件"
        case .conversion: return "转换"
        case .ai: return "AI工具"
        case .batch: return "批量转换"
        case .settings: return "设置"
        }
    }

    var iconName: String {
        switch self {
        case .files: return "doc.text"
        case .conversion: return "arrow.triangle.2.circlepath"
        case .ai: return "brain.head.profile"
        case .batch: return "doc.on.doc"
        case .settings: return "gearshape"
        }
    }
}

// MARK: - 侧边栏视图
struct SidebarView: View {
    @Binding var selectedTab: MainTab
    @EnvironmentObject var conversionService: ConversionService

    var body: some View {
        List(selection: $selectedTab) {
            Section("主要功能") {
                ForEach([MainTab.files, .conversion, .batch], id: \.self) { tab in
                    NavigationLink(value: tab) {
                        Label(tab.displayName, systemImage: tab.iconName)
                    }
                }
            }

            Section("工具") {
                NavigationLink(value: MainTab.ai) {
                    Label(MainTab.ai.displayName, systemImage: MainTab.ai.iconName)
                }
            }

            Section("状态") {
                VStack(alignment: .leading, spacing: 8) {
                    Label("活动任务", systemImage: "clock")
                        .foregroundColor(.secondary)
                        .font(.caption)

                    Text("\(conversionService.activeJobs.count)")
                        .font(.title2)
                        .fontWeight(.semibold)

                    if conversionService.isProcessing {
                        HStack {
                            ProgressView()
                                .scaleEffect(0.5)
                            Text("转换中...")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                .padding(.vertical, 4)
            }

            Spacer()
        }
        .listStyle(.sidebar)
        .navigationTitle("EBookAI")
    }
}

// MARK: - 预览
#Preview {
    ContentView()
        .environmentObject(ConversionService.shared)
        .environmentObject(AIService.shared)
        .environmentObject(FileManagerService.shared)
}