//
//  ConversionService.swift
//  EBookAI Native
//
//  核心转换服务
//

import Foundation
import Combine
import OSLog
import ZIPFoundation

// MARK: - 转换服务
@MainActor
class ConversionService: ObservableObject {
    static let shared = ConversionService()

    @Published var activeJobs: [ConversionJob] = []
    @Published var completedJobs: [ConversionJob] = []
    @Published var isProcessing: Bool = false

    private let logger = Logger(subsystem: "com.ebookai.native", category: "ConversionService")
    private let queue = DispatchQueue(label: "conversion.queue", qos: .userInitiated)
    private let semaphore = DispatchSemaphore(value: 3) // 最大并发数
    private var cancellables = Set<AnyCancellable>()

    private init() {
        setupBindings()
    }

    // MARK: - Public Methods
    func startConversion(_ job: ConversionJob) async {
        logger.info("开始转换任务: \(job.id)")

        activeJobs.append(job)
        isProcessing = true

        await withTaskGroup(of: Void.self) { group in
            group.addTask {
                await self.processJob(job)
            }
        }
    }

    func startBatchConversion(_ batchJob: BatchConversionJob) async {
        logger.info("开始批量转换: \(batchJob.id), 文件数量: \(batchJob.totalJobs)")

        batchJob.status = .processing
        batchJob.startTime = Date()

        await withTaskGroup(of: Void.self) { group in
            for job in batchJob.jobs {
                group.addTask {
                    await self.processJob(job)
                }
            }
        }

        updateBatchStatus(batchJob)
    }

    func cancelJob(_ job: ConversionJob) {
        logger.info("取消转换任务: \(job.id)")
        job.cancel()
        removeFromActiveJobs(job)
    }

    func cancelAllJobs() {
        logger.info("取消所有转换任务")
        for job in activeJobs {
            job.cancel()
        }
        activeJobs.removeAll()
        isProcessing = false
    }

    func clearCompletedJobs() {
        completedJobs.removeAll()
    }

    // MARK: - Private Methods
    private func setupBindings() {
        $activeJobs
            .map { !$0.isEmpty }
            .assign(to: &$isProcessing)
    }

    private func processJob(_ job: ConversionJob) async {
        semaphore.wait()
        defer { semaphore.signal() }

        do {
            job.start()
            logger.info("开始处理任务: \(job.sourceFile.name) -> \(job.targetFormat.displayName)")

            // 更新进度：准备阶段
            await MainActor.run {
                job.updateProgress(10, message: "准备转换...")
            }

            // 执行转换
            let outputFile = try await performConversion(job)

            // 更新进度：完成
            await MainActor.run {
                job.updateProgress(100, message: "转换完成")
                job.complete(outputFile: outputFile)
                self.moveToCompleted(job)
            }

            logger.info("任务完成: \(job.id)")

        } catch {
            logger.error("任务失败: \(job.id), 错误: \(error)")
            let conversionError = ConversionError(
                code: .processingError,
                message: error.localizedDescription
            )

            await MainActor.run {
                job.fail(with: conversionError)
                self.moveToCompleted(job)
            }
        }
    }

    private func performConversion(_ job: ConversionJob) async throws -> FileItem {
        let converter = try getConverter(from: job.sourceFile.format, to: job.targetFormat)

        // 创建输出文件URL
        let outputURL = createOutputURL(for: job)

        // 执行转换
        try await converter.convert(
            from: job.sourceFile.url,
            to: outputURL,
            options: job.options,
            quality: job.quality
        ) { progress in
            Task { @MainActor in
                job.updateProgress(10 + progress * 0.8, message: "转换中...")
            }
        }

        // 创建输出文件项
        return try FileItem(url: outputURL)
    }

    private func getConverter(from sourceFormat: FileFormat, to targetFormat: FileFormat) throws -> FileConverter {
        switch (sourceFormat, targetFormat) {
        case (.epub, .pdf):
            return EPUBToPDFConverter()
        case (.pdf, .epub):
            return PDFToEPUBConverter()
        case (.txt, .pdf):
            return TextToPDFConverter()
        case (.txt, .epub):
            return TextToEPUBConverter()
        case (.epub, .txt):
            return EPUBToTextConverter()
        case (.pdf, .txt):
            return PDFToTextConverter()
        case (.mobi, .epub):
            return MobiToEPUBConverter()
        case (.azw3, .epub):
            return AZW3ToEPUBConverter()
        case (.docx, .pdf):
            return DocxToPDFConverter()
        case (.html, .pdf):
            return HTMLToPDFConverter()
        case (.markdown, .pdf):
            return MarkdownToPDFConverter()
        default:
            throw ConversionError(code: .unsupportedFormat, message: "不支持的转换: \(sourceFormat.displayName) -> \(targetFormat.displayName)")
        }
    }

    private func createOutputURL(for job: ConversionJob) -> URL {
        let documentsURL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        let outputDirectory = documentsURL.appendingPathComponent("EBookAI/Converted")

        // 确保输出目录存在
        try? FileManager.default.createDirectory(at: outputDirectory, withIntermediateDirectories: true)

        let fileName = job.outputFileName
        return outputDirectory.appendingPathComponent(fileName)
    }

    private func moveToCompleted(_ job: ConversionJob) {
        if let index = activeJobs.firstIndex(where: { $0.id == job.id }) {
            activeJobs.remove(at: index)
        }
        completedJobs.append(job)
    }

    private func removeFromActiveJobs(_ job: ConversionJob) {
        if let index = activeJobs.firstIndex(where: { $0.id == job.id }) {
            activeJobs.remove(at: index)
        }
    }

    private func updateBatchStatus(_ batchJob: BatchConversionJob) {
        let completed = batchJob.completedJobs
        let failed = batchJob.failedJobs
        let total = batchJob.totalJobs

        if completed == total {
            batchJob.status = .completed
        } else if completed + failed == total {
            batchJob.status = failed > 0 ? .partiallyCompleted : .completed
        } else {
            batchJob.status = .processing
        }

        if batchJob.status != .processing {
            batchJob.endTime = Date()
        }
    }
}

// MARK: - 文件转换器协议
protocol FileConverter {
    func convert(
        from sourceURL: URL,
        to targetURL: URL,
        options: ConversionOptions,
        quality: ConversionQuality,
        progressHandler: @escaping (Double) -> Void
    ) async throws
}

// MARK: - EPUB to PDF 转换器
class EPUBToPDFConverter: FileConverter {
    func convert(
        from sourceURL: URL,
        to targetURL: URL,
        options: ConversionOptions,
        quality: ConversionQuality,
        progressHandler: @escaping (Double) -> Void
    ) async throws {
        progressHandler(0.1)

        // 解压EPUB文件
        let tempDirectory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: tempDirectory, withIntermediateDirectories: true)

        try FileManager.default.unzipItem(at: sourceURL, to: tempDirectory)
        progressHandler(0.3)

        // 读取EPUB内容
        let epubContent = try EPUBReader.readContent(from: tempDirectory)
        progressHandler(0.5)

        // 生成PDF
        let pdfGenerator = PDFGenerator(options: options, quality: quality)
        try await pdfGenerator.generate(from: epubContent, to: targetURL) { progress in
            progressHandler(0.5 + progress * 0.5)
        }

        // 清理临时文件
        try? FileManager.default.removeItem(at: tempDirectory)
    }
}

// MARK: - Text to PDF 转换器
class TextToPDFConverter: FileConverter {
    func convert(
        from sourceURL: URL,
        to targetURL: URL,
        options: ConversionOptions,
        quality: ConversionQuality,
        progressHandler: @escaping (Double) -> Void
    ) async throws {
        progressHandler(0.1)

        // 读取文本内容
        let textContent = try String(contentsOf: sourceURL, encoding: .utf8)
        progressHandler(0.3)

        // 生成PDF
        let pdfGenerator = PDFGenerator(options: options, quality: quality)
        try await pdfGenerator.generateFromText(textContent, to: targetURL) { progress in
            progressHandler(0.3 + progress * 0.7)
        }
    }
}

// MARK: - PDF生成器
class PDFGenerator {
    private let options: ConversionOptions
    private let quality: ConversionQuality

    init(options: ConversionOptions, quality: ConversionQuality) {
        self.options = options
        self.quality = quality
    }

    func generate(
        from content: EPUBContent,
        to targetURL: URL,
        progressHandler: @escaping (Double) -> Void
    ) async throws {
        // 实现EPUB内容到PDF的转换
        // 这里是简化版本，实际实现会更复杂
        progressHandler(1.0)
    }

    func generateFromText(
        _ text: String,
        to targetURL: URL,
        progressHandler: @escaping (Double) -> Void
    ) async throws {
        // 实现文本到PDF的转换
        // 使用Core Graphics或其他PDF生成库
        progressHandler(1.0)
    }
}

// MARK: - EPUB内容
struct EPUBContent {
    let metadata: FileMetadata
    let chapters: [EPUBChapter]
    let resources: [EPUBResource]
}

struct EPUBChapter {
    let title: String
    let content: String
    let order: Int
}

struct EPUBResource {
    let url: URL
    let type: ResourceType

    enum ResourceType {
        case image
        case stylesheet
        case font
        case other
    }
}

// MARK: - EPUB阅读器
class EPUBReader {
    static func readContent(from directory: URL) throws -> EPUBContent {
        // 实现EPUB内容解析
        // 这里是简化版本
        return EPUBContent(metadata: FileMetadata(), chapters: [], resources: [])
    }
}

// 其他转换器实现将在后续添加...