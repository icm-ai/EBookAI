//
//  FileFormat.swift
//  EBookAI Native
//
//  文件格式定义和处理
//

import Foundation
import UniformTypeIdentifiers

// MARK: - 支持的文件格式
enum FileFormat: String, CaseIterable, Codable {
    case epub = "epub"
    case pdf = "pdf"
    case txt = "txt"
    case mobi = "mobi"
    case azw3 = "azw3"
    case docx = "docx"
    case html = "html"
    case markdown = "md"

    // 显示名称
    var displayName: String {
        switch self {
        case .epub: return "EPUB"
        case .pdf: return "PDF"
        case .txt: return "纯文本"
        case .mobi: return "MOBI"
        case .azw3: return "AZW3"
        case .docx: return "Word文档"
        case .html: return "HTML"
        case .markdown: return "Markdown"
        }
    }

    // 文件扩展名
    var fileExtension: String {
        return rawValue
    }

    // MIME 类型
    var mimeType: String {
        switch self {
        case .epub: return "application/epub+zip"
        case .pdf: return "application/pdf"
        case .txt: return "text/plain"
        case .mobi: return "application/x-mobipocket-ebook"
        case .azw3: return "application/vnd.amazon.ebook"
        case .docx: return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        case .html: return "text/html"
        case .markdown: return "text/markdown"
        }
    }

    // UTType
    var utType: UTType {
        switch self {
        case .epub: return UTType(mimeType: mimeType) ?? .data
        case .pdf: return .pdf
        case .txt: return .plainText
        case .mobi, .azw3: return UTType(mimeType: mimeType) ?? .data
        case .docx: return UTType(mimeType: mimeType) ?? .data
        case .html: return .html
        case .markdown: return UTType(mimeType: mimeType) ?? .plainText
        }
    }

    // 图标名称
    var iconName: String {
        switch self {
        case .epub: return "book.closed"
        case .pdf: return "doc.richtext"
        case .txt: return "doc.plaintext"
        case .mobi, .azw3: return "book"
        case .docx: return "doc.text"
        case .html: return "globe"
        case .markdown: return "text.alignleft"
        }
    }

    // 是否支持作为源格式
    var canBeSource: Bool {
        return true
    }

    // 是否支持作为目标格式
    var canBeTarget: Bool {
        return true
    }

    // 从文件扩展名创建格式
    static func from(fileExtension: String) -> FileFormat? {
        let ext = fileExtension.lowercased().replacingOccurrences(of: ".", with: "")
        return FileFormat(rawValue: ext)
    }

    // 从URL创建格式
    static func from(url: URL) -> FileFormat? {
        return from(fileExtension: url.pathExtension)
    }

    // 从MIME类型创建格式
    static func from(mimeType: String) -> FileFormat? {
        return allCases.first { $0.mimeType == mimeType }
    }
}

// MARK: - 转换配置
struct ConversionOptions: Codable {
    var preserveFormatting: Bool = true
    var embedImages: Bool = true
    var generateTOC: Bool = true
    var optimizeForReading: Bool = true
    var compressionLevel: CompressionLevel = .balanced
    var pageSize: PageSize = .a4
    var margins: Margins = .normal
    var fontSettings: FontSettings = .default

    enum CompressionLevel: String, CaseIterable, Codable {
        case none = "none"
        case low = "low"
        case balanced = "balanced"
        case high = "high"
        case maximum = "maximum"

        var displayName: String {
            switch self {
            case .none: return "无压缩"
            case .low: return "低压缩"
            case .balanced: return "平衡"
            case .high: return "高压缩"
            case .maximum: return "最大压缩"
            }
        }
    }

    enum PageSize: String, CaseIterable, Codable {
        case a4 = "a4"
        case a5 = "a5"
        case letter = "letter"
        case kindle = "kindle"
        case custom = "custom"

        var displayName: String {
            switch self {
            case .a4: return "A4"
            case .a5: return "A5"
            case .letter: return "Letter"
            case .kindle: return "Kindle"
            case .custom: return "自定义"
            }
        }
    }

    struct Margins: Codable {
        var top: Double
        var bottom: Double
        var left: Double
        var right: Double

        static let normal = Margins(top: 2.54, bottom: 2.54, left: 2.54, right: 2.54)
        static let narrow = Margins(top: 1.27, bottom: 1.27, left: 1.27, right: 1.27)
        static let wide = Margins(top: 3.81, bottom: 3.81, left: 3.81, right: 3.81)
    }

    struct FontSettings: Codable {
        var family: String
        var size: Double
        var lineHeight: Double
        var letterSpacing: Double

        static let `default` = FontSettings(
            family: "SF Pro Text",
            size: 12.0,
            lineHeight: 1.4,
            letterSpacing: 0.0
        )
    }
}

// MARK: - 转换质量
enum ConversionQuality: String, CaseIterable, Codable {
    case draft = "draft"
    case standard = "standard"
    case high = "high"
    case premium = "premium"

    var displayName: String {
        switch self {
        case .draft: return "草稿"
        case .standard: return "标准"
        case .high: return "高质量"
        case .premium: return "专业"
        }
    }

    var description: String {
        switch self {
        case .draft: return "快速转换，基本格式保留"
        case .standard: return "标准质量，适合大多数用途"
        case .high: return "高质量，完整格式保留"
        case .premium: return "专业质量，完美格式和排版"
        }
    }

    var processingTime: TimeInterval {
        switch self {
        case .draft: return 1.0
        case .standard: return 3.0
        case .high: return 8.0
        case .premium: return 15.0
        }
    }
}