//
//  FileManagerService.swift
//  EBookAI Native
//
//  文件管理服务
//

import Foundation
import Combine
import OSLog

// MARK: - 文件管理服务
@MainActor
class FileManagerService: ObservableObject {
    static let shared = FileManagerService()

    @Published var files: [FileItem] = []
    @Published var selectedFiles: Set<UUID> = []
    @Published var searchText: String = ""
    @Published var sortOrder: SortOrder = .name
    @Published var filterFormat: FileFormat?

    private let logger = Logger(subsystem: "com.ebookai.native", category: "FileManagerService")
    private var cancellables = Set<AnyCancellable>()

    private init() {
        setupBindings()
        loadRecentFiles()
    }

    // MARK: - Computed Properties
    var filteredFiles: [FileItem] {
        var result = files

        // 应用搜索过滤
        if !searchText.isEmpty {
            result = result.filter { file in
                file.name.localizedCaseInsensitiveContains(searchText) ||
                file.displayName.localizedCaseInsensitiveContains(searchText)
            }
        }

        // 应用格式过滤
        if let format = filterFormat {
            result = result.filter { $0.format == format }
        }

        // 应用排序
        switch sortOrder {
        case .name:
            result.sort { $0.name.localizedCompare($1.name) == .orderedAscending }
        case .size:
            result.sort { $0.size < $1.size }
        case .dateCreated:
            result.sort { $0.createdAt > $1.createdAt }
        case .dateModified:
            result.sort { $0.modifiedAt > $1.modifiedAt }
        case .format:
            result.sort { $0.format.displayName.localizedCompare($1.format.displayName) == .orderedAscending }
        }

        return result
    }

    var selectedFileItems: [FileItem] {
        return files.filter { selectedFiles.contains($0.id) }
    }

    var totalSize: Int64 {
        return files.reduce(0) { $0 + $1.size }
    }

    var supportedFormats: [FileFormat] {
        return Array(Set(files.map { $0.format })).sorted { $0.displayName < $1.displayName }
    }

    // MARK: - Public Methods
    func addFiles(_ urls: [URL]) async {
        logger.info("添加文件: \(urls.count) 个")

        for url in urls {
            do {
                let fileItem = try FileItem(url: url)
                if !files.contains(where: { $0.url == url }) {
                    files.append(fileItem)
                    logger.info("已添加文件: \(fileItem.name)")
                }
            } catch {
                logger.error("添加文件失败: \(url.lastPathComponent), 错误: \(error)")
            }
        }

        saveRecentFiles()
    }

    func addFolder(_ url: URL) async {
        logger.info("添加文件夹: \(url.lastPathComponent)")

        guard url.hasDirectoryPath else { return }

        do {
            let contents = try FileManager.default.contentsOfDirectory(
                at: url,
                includingPropertiesForKeys: [.isRegularFileKey],
                options: [.skipsHiddenFiles, .skipsSubdirectoryDescendants]
            )

            let fileURLs = contents.filter { url in
                (try? url.resourceValues(forKeys: [.isRegularFileKey]))?.isRegularFile == true
            }.filter { url in
                FileFormat.from(url: url) != nil
            }

            await addFiles(fileURLs)
        } catch {
            logger.error("读取文件夹失败: \(error)")
        }
    }

    func removeFile(_ file: FileItem) {
        files.removeAll { $0.id == file.id }
        selectedFiles.remove(file.id)
        saveRecentFiles()
        logger.info("已移除文件: \(file.name)")
    }

    func removeFiles(_ fileIDs: [UUID]) {
        files.removeAll { fileIDs.contains($0.id) }
        selectedFiles.subtract(Set(fileIDs))
        saveRecentFiles()
        logger.info("已移除文件: \(fileIDs.count) 个")
    }

    func removeSelectedFiles() {
        let fileIDs = Array(selectedFiles)
        removeFiles(fileIDs)
    }

    func clearAllFiles() {
        files.removeAll()
        selectedFiles.removeAll()
        saveRecentFiles()
        logger.info("已清空所有文件")
    }

    func selectFile(_ file: FileItem) {
        selectedFiles.insert(file.id)
    }

    func deselectFile(_ file: FileItem) {
        selectedFiles.remove(file.id)
    }

    func toggleSelection(_ file: FileItem) {
        if selectedFiles.contains(file.id) {
            deselectFile(file)
        } else {
            selectFile(file)
        }
    }

    func selectAll() {
        selectedFiles = Set(filteredFiles.map { $0.id })
    }

    func deselectAll() {
        selectedFiles.removeAll()
    }

    func revealInFinder(_ file: FileItem) {
        NSWorkspace.shared.selectFile(file.url.path, inFileViewerRootedAtPath: "")
    }

    func openFile(_ file: FileItem) {
        NSWorkspace.shared.open(file.url)
    }

    func duplicateFile(_ file: FileItem) async {
        let fileName = file.url.deletingPathExtension().lastPathComponent
        let fileExtension = file.url.pathExtension
        let duplicateName = "\(fileName) 副本.\(fileExtension)"

        let duplicateURL = file.url.deletingLastPathComponent().appendingPathComponent(duplicateName)

        do {
            try FileManager.default.copyItem(at: file.url, to: duplicateURL)
            await addFiles([duplicateURL])
            logger.info("文件已复制: \(duplicateName)")
        } catch {
            logger.error("文件复制失败: \(error)")
        }
    }

    func setSortOrder(_ order: SortOrder) {
        sortOrder = order
        UserDefaults.standard.set(order.rawValue, forKey: "FileSortOrder")
    }

    func setFilterFormat(_ format: FileFormat?) {
        filterFormat = format
    }

    // MARK: - Private Methods
    private func setupBindings() {
        // 监听搜索文本变化
        $searchText
            .debounce(for: .milliseconds(300), scheduler: RunLoop.main)
            .sink { _ in
                // 搜索结果会通过 filteredFiles 自动更新
            }
            .store(in: &cancellables)
    }

    private func loadRecentFiles() {
        guard let data = UserDefaults.standard.data(forKey: "RecentFiles"),
              let urls = try? NSKeyedUnarchiver.unarchiveTopLevelObjectWithData(data) as? [URL] else {
            return
        }

        Task {
            let validURLs = urls.filter { FileManager.default.fileExists(atPath: $0.path) }
            await addFiles(validURLs)
        }
    }

    private func saveRecentFiles() {
        let urls = files.map { $0.url }
        if let data = try? NSKeyedArchiver.archivedData(withRootObject: urls, requiringSecureCoding: false) {
            UserDefaults.standard.set(data, forKey: "RecentFiles")
        }
    }
}

// MARK: - 排序顺序
enum SortOrder: String, CaseIterable {
    case name = "name"
    case size = "size"
    case dateCreated = "dateCreated"
    case dateModified = "dateModified"
    case format = "format"

    var displayName: String {
        switch self {
        case .name: return "名称"
        case .size: return "大小"
        case .dateCreated: return "创建日期"
        case .dateModified: return "修改日期"
        case .format: return "格式"
        }
    }

    var iconName: String {
        switch self {
        case .name: return "textformat"
        case .size: return "externaldrive"
        case .dateCreated: return "calendar.badge.plus"
        case .dateModified: return "calendar.badge.clock"
        case .format: return "doc.text"
        }
    }
}

// MARK: - 文件统计
struct FileStatistics {
    let totalFiles: Int
    let totalSize: Int64
    let formatCounts: [FileFormat: Int]
    let averageSize: Int64

    var formattedTotalSize: String {
        ByteCountFormatter.string(fromByteCount: totalSize, countStyle: .file)
    }

    var formattedAverageSize: String {
        ByteCountFormatter.string(fromByteCount: averageSize, countStyle: .file)
    }
}

extension FileManagerService {
    var statistics: FileStatistics {
        let formatCounts = Dictionary(grouping: files, by: { $0.format })
            .mapValues { $0.count }

        return FileStatistics(
            totalFiles: files.count,
            totalSize: totalSize,
            formatCounts: formatCounts,
            averageSize: files.isEmpty ? 0 : totalSize / Int64(files.count)
        )
    }
}