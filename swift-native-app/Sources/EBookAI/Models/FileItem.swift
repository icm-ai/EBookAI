//
//  FileItem.swift
//  EBookAI Native
//
//  文件项目数据模型
//

import Foundation
import UniformTypeIdentifiers

// MARK: - 文件项目
struct FileItem: Identifiable, Codable, Hashable {
    let id: UUID
    let url: URL
    let name: String
    let format: FileFormat
    let size: Int64
    let createdAt: Date
    let modifiedAt: Date
    var metadata: FileMetadata?

    init(url: URL) throws {
        guard url.startAccessingSecurityScopedResource() else {
            throw FileError.accessDenied
        }
        defer { url.stopAccessingSecurityScopedResource() }

        self.id = UUID()
        self.url = url
        self.name = url.lastPathComponent

        guard let format = FileFormat.from(url: url) else {
            throw FileError.unsupportedFormat
        }
        self.format = format

        let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
        self.size = attributes[.size] as? Int64 ?? 0
        self.createdAt = attributes[.creationDate] as? Date ?? Date()
        self.modifiedAt = attributes[.modificationDate] as? Date ?? Date()

        // 尝试读取元数据
        self.metadata = try? FileMetadata.extract(from: url, format: format)
    }

    // MARK: - Computed Properties
    var formattedSize: String {
        return ByteCountFormatter.string(fromByteCount: size, countStyle: .file)
    }

    var isValid: Bool {
        return FileManager.default.fileExists(atPath: url.path)
    }

    var iconName: String {
        return format.iconName
    }

    var displayName: String {
        return url.deletingPathExtension().lastPathComponent
    }

    var pathExtension: String {
        return url.pathExtension
    }

    // MARK: - Methods
    func canConvert(to targetFormat: FileFormat) -> Bool {
        // 检查是否支持从当前格式转换到目标格式
        return ConversionCapability.canConvert(from: format, to: targetFormat)
    }

    func estimatedConversionTime(to targetFormat: FileFormat, quality: ConversionQuality) -> TimeInterval {
        let baseTime = quality.processingTime
        let sizeMultiplier = Double(size) / (1024 * 1024) // MB
        let complexityMultiplier = ConversionCapability.complexityMultiplier(from: format, to: targetFormat)

        return baseTime * (1 + sizeMultiplier * 0.1) * complexityMultiplier
    }

    func thumbnail() async -> Data? {
        // 根据文件类型生成缩略图
        switch format {
        case .pdf:
            return await PDFThumbnailGenerator.generate(from: url)
        case .epub:
            return await EPUBThumbnailGenerator.generate(from: url)
        default:
            return nil
        }
    }
}

// MARK: - 文件元数据
struct FileMetadata: Codable, Hashable {
    var title: String?
    var author: String?
    var publisher: String?
    var publicationDate: Date?
    var description: String?
    var language: String?
    var pageCount: Int?
    var wordCount: Int?
    var chapters: [Chapter]?
    var coverImage: Data?

    static func extract(from url: URL, format: FileFormat) throws -> FileMetadata {
        switch format {
        case .epub:
            return try EPUBMetadataExtractor.extract(from: url)
        case .pdf:
            return try PDFMetadataExtractor.extract(from: url)
        case .mobi, .azw3:
            return try MobiMetadataExtractor.extract(from: url)
        case .docx:
            return try DocxMetadataExtractor.extract(from: url)
        default:
            return try BasicMetadataExtractor.extract(from: url)
        }
    }
}

// MARK: - 章节信息
struct Chapter: Codable, Hashable, Identifiable {
    let id: UUID = UUID()
    let title: String
    let level: Int
    let startPage: Int?
    let wordCount: Int?

    init(title: String, level: Int = 1, startPage: Int? = nil, wordCount: Int? = nil) {
        self.title = title
        self.level = level
        self.startPage = startPage
        self.wordCount = wordCount
    }
}

// MARK: - 文件错误
enum FileError: Error, LocalizedError {
    case notFound
    case accessDenied
    case unsupportedFormat
    case corruptedFile
    case tooLarge
    case readError
    case writeError

    var errorDescription: String? {
        switch self {
        case .notFound: return "文件未找到"
        case .accessDenied: return "无法访问文件"
        case .unsupportedFormat: return "不支持的文件格式"
        case .corruptedFile: return "文件已损坏"
        case .tooLarge: return "文件太大"
        case .readError: return "文件读取失败"
        case .writeError: return "文件写入失败"
        }
    }
}

// MARK: - 转换能力
struct ConversionCapability {
    static func canConvert(from source: FileFormat, to target: FileFormat) -> Bool {
        // 定义转换矩阵
        let conversionMatrix: [FileFormat: Set<FileFormat>] = [
            .epub: [.pdf, .txt, .html, .mobi],
            .pdf: [.txt, .html, .epub],
            .txt: [.pdf, .epub, .html, .mobi],
            .mobi: [.epub, .pdf, .txt, .html],
            .azw3: [.epub, .pdf, .txt, .html],
            .docx: [.pdf, .txt, .html, .epub],
            .html: [.pdf, .epub, .txt, .mobi],
            .markdown: [.pdf, .html, .epub, .txt]
        ]

        return conversionMatrix[source]?.contains(target) ?? false
    }

    static func complexityMultiplier(from source: FileFormat, to target: FileFormat) -> Double {
        // 转换复杂度系数
        switch (source, target) {
        case (.txt, _): return 0.5
        case (_, .txt): return 0.3
        case (.pdf, .epub), (.epub, .pdf): return 2.0
        case (.mobi, .epub), (.azw3, .epub): return 1.5
        case (.docx, _): return 1.8
        default: return 1.0
        }
    }
}

// MARK: - 元数据提取器协议
protocol MetadataExtractor {
    static func extract(from url: URL) throws -> FileMetadata
}

// MARK: - 基础元数据提取器
struct BasicMetadataExtractor: MetadataExtractor {
    static func extract(from url: URL) throws -> FileMetadata {
        var metadata = FileMetadata()
        metadata.title = url.deletingPathExtension().lastPathComponent

        // 尝试从文件内容中提取基本信息
        if let content = try? String(contentsOf: url) {
            metadata.wordCount = content.components(separatedBy: .whitespacesAndNewlines)
                .filter { !$0.isEmpty }.count
        }

        return metadata
    }
}

// MARK: - 缩略图生成器协议
protocol ThumbnailGenerator {
    static func generate(from url: URL) async -> Data?
}

// MARK: - PDF缩略图生成器
struct PDFThumbnailGenerator: ThumbnailGenerator {
    static func generate(from url: URL) async -> Data? {
        // 实现PDF缩略图生成
        return nil
    }
}

// MARK: - EPUB缩略图生成器
struct EPUBThumbnailGenerator: ThumbnailGenerator {
    static func generate(from url: URL) async -> Data? {
        // 实现EPUB缩略图生成
        return nil
    }
}

// 其他格式的元数据提取器将在后续实现