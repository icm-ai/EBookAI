//
//  FileListView.swift
//  EBookAI Native
//
//  文件列表视图
//

import SwiftUI
import UniformTypeIdentifiers

struct FileListView: View {
    @EnvironmentObject var fileManager: FileManagerService
    @EnvironmentObject var conversionService: ConversionService

    @State private var dragOver = false
    @State private var showingFileImporter = false
    @State private var showingFolderImporter = false
    @State private var showingContextMenu = false
    @State private var viewMode: ViewMode = .list

    var body: some View {
        VStack(spacing: 0) {
            // 工具栏
            toolbar

            // 主内容区域
            if fileManager.files.isEmpty {
                emptyState
            } else {
                fileListContent
            }

            // 状态栏
            statusBar
        }
        .onDrop(of: [.fileURL], isTargeted: $dragOver) { providers in
            handleDrop(providers)
        }
        .overlay(
            dragOverlay,
            alignment: .center
        )
        .fileImporter(
            isPresented: $showingFileImporter,
            allowedContentTypes: supportedFileTypes,
            allowsMultipleSelection: true
        ) { result in
            handleFileImport(result)
        }
        .fileImporter(
            isPresented: $showingFolderImporter,
            allowedContentTypes: [.folder],
            allowsMultipleSelection: false
        ) { result in
            handleFolderImport(result)
        }
    }

    // MARK: - 工具栏
    private var toolbar: some View {
        HStack {
            // 添加按钮
            Menu {
                Button("添加文件...") {
                    showingFileImporter = true
                }
                Button("添加文件夹...") {
                    showingFolderImporter = true
                }
            } label: {
                Label("添加", systemImage: "plus")
            }
            .menuStyle(.borderlessButton)

            Divider()

            // 搜索框
            HStack {
                Image(systemName: "magnifyingglass")
                    .foregroundColor(.secondary)
                TextField("搜索文件...", text: $fileManager.searchText)
                    .textFieldStyle(.roundedBorder)
                    .frame(maxWidth: 200)
            }

            Spacer()

            // 视图切换
            Picker("视图模式", selection: $viewMode) {
                Label("列表", systemImage: "list.bullet").tag(ViewMode.list)
                Label("网格", systemImage: "square.grid.2x2").tag(ViewMode.grid)
            }
            .pickerStyle(.segmented)
            .frame(width: 120)

            // 排序菜单
            Menu {
                ForEach(SortOrder.allCases, id: \.self) { order in
                    Button(action: { fileManager.setSortOrder(order) }) {
                        Label(order.displayName, systemImage: order.iconName)
                        if fileManager.sortOrder == order {
                            Image(systemName: "checkmark")
                        }
                    }
                }
            } label: {
                Label("排序", systemImage: "arrow.up.arrow.down")
            }
            .menuStyle(.borderlessButton)

            // 过滤菜单
            Menu {
                Button("显示全部") {
                    fileManager.setFilterFormat(nil)
                }
                Divider()
                ForEach(fileManager.supportedFormats, id: \.self) { format in
                    Button(format.displayName) {
                        fileManager.setFilterFormat(format)
                    }
                }
            } label: {
                Label("过滤", systemImage: "line.3.horizontal.decrease.circle")
            }
            .menuStyle(.borderlessButton)
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(Color(NSColor.controlBackgroundColor))
        .overlay(
            Rectangle()
                .frame(height: 1)
                .foregroundColor(Color(NSColor.separatorColor)),
            alignment: .bottom
        )
    }

    // MARK: - 文件列表内容
    @ViewBuilder
    private var fileListContent: some View {
        switch viewMode {
        case .list:
            fileListView
        case .grid:
            fileGridView
        }
    }

    // MARK: - 列表视图
    private var fileListView: some View {
        Table(fileManager.filteredFiles, selection: $fileManager.selectedFiles) {
            TableColumn("名称", value: \.name) { file in
                FileRowView(file: file)
                    .contextMenu {
                        fileContextMenu(file)
                    }
            }
            .width(min: 200, ideal: 300, max: 500)

            TableColumn("格式", value: \.format.displayName) { file in
                Label(file.format.displayName, systemImage: file.format.iconName)
                    .font(.caption)
            }
            .width(80)

            TableColumn("大小", value: \.formattedSize) { file in
                Text(file.formattedSize)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .width(80)

            TableColumn("修改时间") { file in
                Text(file.modifiedAt, style: .relative)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .width(100)
        }
        .tableStyle(.inset(alternatesRowBackgrounds: true))
    }

    // MARK: - 网格视图
    private var fileGridView: some View {
        ScrollView {
            LazyVGrid(columns: gridColumns, spacing: 16) {
                ForEach(fileManager.filteredFiles) { file in
                    FileCardView(file: file)
                        .onTapGesture {
                            fileManager.toggleSelection(file)
                        }
                        .contextMenu {
                            fileContextMenu(file)
                        }
                }
            }
            .padding()
        }
    }

    private var gridColumns: [GridItem] {
        Array(repeating: GridItem(.flexible(), spacing: 16), count: 3)
    }

    // MARK: - 空状态
    private var emptyState: some View {
        VStack(spacing: 20) {
            Image(systemName: "doc.text")
                .font(.system(size: 64))
                .foregroundColor(.secondary)

            VStack(spacing: 8) {
                Text("没有文件")
                    .font(.title2)
                    .fontWeight(.medium)

                Text("拖拽文件到这里或点击添加按钮")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }

            HStack(spacing: 12) {
                Button("添加文件") {
                    showingFileImporter = true
                }
                .buttonStyle(.borderedProminent)

                Button("添加文件夹") {
                    showingFolderImporter = true
                }
                .buttonStyle(.bordered)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(NSColor.textBackgroundColor))
    }

    // MARK: - 拖拽覆盖层
    @ViewBuilder
    private var dragOverlay: some View {
        if dragOver {
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.accentColor.opacity(0.1))
                .overlay(
                    VStack(spacing: 16) {
                        Image(systemName: "plus.circle.fill")
                            .font(.system(size: 48))
                            .foregroundColor(.accentColor)

                        Text("释放以添加文件")
                            .font(.title2)
                            .fontWeight(.medium)
                            .foregroundColor(.accentColor)
                    }
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.accentColor, lineWidth: 2)
                        .background(Color.clear)
                )
                .padding(20)
        }
    }

    // MARK: - 状态栏
    private var statusBar: some View {
        HStack {
            Text("\(fileManager.filteredFiles.count) 个文件")
                .font(.caption)
                .foregroundColor(.secondary)

            if !fileManager.selectedFiles.isEmpty {
                Text("已选择 \(fileManager.selectedFiles.count) 个")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            Text("总大小: \(fileManager.statistics.formattedTotalSize)")
                .font(.caption)
                .foregroundColor(.secondary)

            if fileManager.filteredFiles.count != fileManager.files.count {
                Text("(已过滤)")
                    .font(.caption)
                    .foregroundColor(.orange)
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 4)
        .background(Color(NSColor.controlBackgroundColor))
        .overlay(
            Rectangle()
                .frame(height: 1)
                .foregroundColor(Color(NSColor.separatorColor)),
            alignment: .top
        )
    }

    // MARK: - 文件上下文菜单
    @ViewBuilder
    private func fileContextMenu(_ file: FileItem) -> some View {
        Button("在Finder中显示") {
            fileManager.revealInFinder(file)
        }

        Button("打开") {
            fileManager.openFile(file)
        }

        Divider()

        Menu("转换为") {
            ForEach(FileFormat.allCases, id: \.self) { format in
                if file.canConvert(to: format) && format != file.format {
                    Button(format.displayName) {
                        startConversion(file, to: format)
                    }
                }
            }
        }

        Divider()

        Button("复制") {
            Task {
                await fileManager.duplicateFile(file)
            }
        }

        Button("移除", role: .destructive) {
            fileManager.removeFile(file)
        }
    }

    // MARK: - 支持的文件类型
    private var supportedFileTypes: [UTType] {
        FileFormat.allCases.compactMap { $0.utType }
    }

    // MARK: - 视图模式
    enum ViewMode: String, CaseIterable {
        case list = "list"
        case grid = "grid"

        var displayName: String {
            switch self {
            case .list: return "列表"
            case .grid: return "网格"
            }
        }
    }

    // MARK: - 事件处理
    private func handleDrop(_ providers: [NSItemProvider]) -> Bool {
        for provider in providers {
            provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { item, _ in
                if let data = item as? Data,
                   let url = URL(dataRepresentation: data, relativeTo: nil) {
                    DispatchQueue.main.async {
                        if url.hasDirectoryPath {
                            Task {
                                await fileManager.addFolder(url)
                            }
                        } else {
                            Task {
                                await fileManager.addFiles([url])
                            }
                        }
                    }
                }
            }
        }
        return true
    }

    private func handleFileImport(_ result: Result<[URL], Error>) {
        switch result {
        case .success(let urls):
            Task {
                await fileManager.addFiles(urls)
            }
        case .failure(let error):
            print("文件导入失败: \(error)")
        }
    }

    private func handleFolderImport(_ result: Result<[URL], Error>) {
        switch result {
        case .success(let urls):
            if let url = urls.first {
                Task {
                    await fileManager.addFolder(url)
                }
            }
        case .failure(let error):
            print("文件夹导入失败: \(error)")
        }
    }

    private func startConversion(_ file: FileItem, to format: FileFormat) {
        let job = ConversionJob(sourceFile: file, targetFormat: format)
        Task {
            await conversionService.startConversion(job)
        }
    }
}

// MARK: - 文件行视图
struct FileRowView: View {
    let file: FileItem

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: file.iconName)
                .font(.title2)
                .foregroundColor(.accentColor)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 2) {
                Text(file.displayName)
                    .font(.body)
                    .lineLimit(1)

                if let metadata = file.metadata, let author = metadata.author {
                    Text("作者: \(author)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }
            }

            Spacer()

            if !file.isValid {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundColor(.orange)
                    .help("文件不存在或无法访问")
            }
        }
    }
}

// MARK: - 文件卡片视图
struct FileCardView: View {
    let file: FileItem
    @EnvironmentObject var fileManager: FileManagerService

    var body: some View {
        VStack(spacing: 12) {
            // 文件图标
            RoundedRectangle(cornerRadius: 8)
                .fill(Color.accentColor.opacity(0.1))
                .frame(height: 120)
                .overlay(
                    Image(systemName: file.iconName)
                        .font(.system(size: 48))
                        .foregroundColor(.accentColor)
                )

            // 文件信息
            VStack(spacing: 4) {
                Text(file.displayName)
                    .font(.caption)
                    .fontWeight(.medium)
                    .lineLimit(2)
                    .multilineTextAlignment(.center)

                HStack {
                    Text(file.format.displayName)
                        .font(.caption2)
                        .foregroundColor(.secondary)

                    Spacer()

                    Text(file.formattedSize)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(fileManager.selectedFiles.contains(file.id) ? Color.accentColor.opacity(0.2) : Color(NSColor.controlBackgroundColor))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(fileManager.selectedFiles.contains(file.id) ? Color.accentColor : Color.clear, lineWidth: 2)
        )
        .frame(width: 140)
    }
}

// MARK: - 预览
#Preview {
    FileListView()
        .environmentObject(FileManagerService.shared)
        .environmentObject(ConversionService.shared)
        .frame(width: 800, height: 600)
}