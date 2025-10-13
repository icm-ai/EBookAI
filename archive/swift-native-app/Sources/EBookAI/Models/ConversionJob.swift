//
//  ConversionJob.swift
//  EBookAI Native
//
//  转换任务数据模型
//

import Foundation

// MARK: - 转换任务
class ConversionJob: ObservableObject, Identifiable, Codable {
    let id: UUID
    let sourceFile: FileItem
    let targetFormat: FileFormat
    let options: ConversionOptions
    let quality: ConversionQuality

    @Published var status: ConversionStatus = .pending
    @Published var progress: Progress = Progress()
    @Published var startTime: Date?
    @Published var endTime: Date?
    @Published var error: ConversionError?
    @Published var outputFile: FileItem?

    init(
        sourceFile: FileItem,
        targetFormat: FileFormat,
        options: ConversionOptions = ConversionOptions(),
        quality: ConversionQuality = .standard
    ) {
        self.id = UUID()
        self.sourceFile = sourceFile
        self.targetFormat = targetFormat
        self.options = options
        self.quality = quality
    }

    // MARK: - Computed Properties
    var duration: TimeInterval? {
        guard let start = startTime, let end = endTime else { return nil }
        return end.timeIntervalSince(start)
    }

    var estimatedTimeRemaining: TimeInterval? {
        guard let start = startTime,
              progress.fractionCompleted > 0 else { return nil }

        let elapsed = Date().timeIntervalSince(start)
        let totalEstimated = elapsed / progress.fractionCompleted
        return totalEstimated - elapsed
    }

    var outputFileName: String {
        let baseName = sourceFile.url.deletingPathExtension().lastPathComponent
        return "\(baseName).\(targetFormat.fileExtension)"
    }

    // MARK: - Methods
    func start() {
        status = .processing
        startTime = Date()
        progress.totalUnitCount = 100
        progress.completedUnitCount = 0
    }

    func updateProgress(_ percentage: Double, message: String = "") {
        progress.completedUnitCount = Int64(percentage)
        progress.localizedDescription = message
    }

    func complete(outputFile: FileItem) {
        self.outputFile = outputFile
        status = .completed
        endTime = Date()
        progress.completedUnitCount = progress.totalUnitCount
    }

    func fail(with error: ConversionError) {
        self.error = error
        status = .failed
        endTime = Date()
    }

    func cancel() {
        status = .cancelled
        endTime = Date()
    }

    // MARK: - Codable
    enum CodingKeys: String, CodingKey {
        case id, sourceFile, targetFormat, options, quality
        case status, startTime, endTime, error, outputFile
    }

    required init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(UUID.self, forKey: .id)
        sourceFile = try container.decode(FileItem.self, forKey: .sourceFile)
        targetFormat = try container.decode(FileFormat.self, forKey: .targetFormat)
        options = try container.decode(ConversionOptions.self, forKey: .options)
        quality = try container.decode(ConversionQuality.self, forKey: .quality)
        status = try container.decode(ConversionStatus.self, forKey: .status)
        startTime = try container.decodeIfPresent(Date.self, forKey: .startTime)
        endTime = try container.decodeIfPresent(Date.self, forKey: .endTime)
        error = try container.decodeIfPresent(ConversionError.self, forKey: .error)
        outputFile = try container.decodeIfPresent(FileItem.self, forKey: .outputFile)
        progress = Progress()
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(sourceFile, forKey: .sourceFile)
        try container.encode(targetFormat, forKey: .targetFormat)
        try container.encode(options, forKey: .options)
        try container.encode(quality, forKey: .quality)
        try container.encode(status, forKey: .status)
        try container.encodeIfPresent(startTime, forKey: .startTime)
        try container.encodeIfPresent(endTime, forKey: .endTime)
        try container.encodeIfPresent(error, forKey: .error)
        try container.encodeIfPresent(outputFile, forKey: .outputFile)
    }
}

// MARK: - 转换状态
enum ConversionStatus: String, CaseIterable, Codable {
    case pending = "pending"
    case processing = "processing"
    case completed = "completed"
    case failed = "failed"
    case cancelled = "cancelled"

    var displayName: String {
        switch self {
        case .pending: return "等待中"
        case .processing: return "转换中"
        case .completed: return "已完成"
        case .failed: return "失败"
        case .cancelled: return "已取消"
        }
    }

    var iconName: String {
        switch self {
        case .pending: return "clock"
        case .processing: return "gear"
        case .completed: return "checkmark.circle.fill"
        case .failed: return "xmark.circle.fill"
        case .cancelled: return "stop.circle"
        }
    }

    var color: String {
        switch self {
        case .pending: return "gray"
        case .processing: return "blue"
        case .completed: return "green"
        case .failed: return "red"
        case .cancelled: return "orange"
        }
    }
}

// MARK: - 转换错误
struct ConversionError: Error, Codable {
    let code: ErrorCode
    let message: String
    let details: String?
    let timestamp: Date

    init(code: ErrorCode, message: String, details: String? = nil) {
        self.code = code
        self.message = message
        self.details = details
        self.timestamp = Date()
    }

    enum ErrorCode: String, CaseIterable, Codable {
        case fileNotFound = "file_not_found"
        case unsupportedFormat = "unsupported_format"
        case corruptedFile = "corrupted_file"
        case insufficientSpace = "insufficient_space"
        case permissionDenied = "permission_denied"
        case networkError = "network_error"
        case processingError = "processing_error"
        case timeoutError = "timeout_error"
        case unknown = "unknown"

        var displayName: String {
            switch self {
            case .fileNotFound: return "文件未找到"
            case .unsupportedFormat: return "不支持的格式"
            case .corruptedFile: return "文件损坏"
            case .insufficientSpace: return "磁盘空间不足"
            case .permissionDenied: return "权限不足"
            case .networkError: return "网络错误"
            case .processingError: return "处理错误"
            case .timeoutError: return "超时错误"
            case .unknown: return "未知错误"
            }
        }
    }
}

// MARK: - 批量转换任务
class BatchConversionJob: ObservableObject, Identifiable, Codable {
    let id: UUID
    let name: String
    let targetFormat: FileFormat
    let options: ConversionOptions
    let quality: ConversionQuality

    @Published var jobs: [ConversionJob] = []
    @Published var status: BatchStatus = .pending
    @Published var startTime: Date?
    @Published var endTime: Date?

    init(
        name: String,
        sourceFiles: [FileItem],
        targetFormat: FileFormat,
        options: ConversionOptions = ConversionOptions(),
        quality: ConversionQuality = .standard
    ) {
        self.id = UUID()
        self.name = name
        self.targetFormat = targetFormat
        self.options = options
        self.quality = quality
        self.jobs = sourceFiles.map { file in
            ConversionJob(
                sourceFile: file,
                targetFormat: targetFormat,
                options: options,
                quality: quality
            )
        }
    }

    // MARK: - Computed Properties
    var totalJobs: Int {
        return jobs.count
    }

    var completedJobs: Int {
        return jobs.filter { $0.status == .completed }.count
    }

    var failedJobs: Int {
        return jobs.filter { $0.status == .failed }.count
    }

    var cancelledJobs: Int {
        return jobs.filter { $0.status == .cancelled }.count
    }

    var overallProgress: Double {
        guard totalJobs > 0 else { return 0 }
        let totalProgress = jobs.reduce(0.0) { $0 + $1.progress.fractionCompleted }
        return totalProgress / Double(totalJobs)
    }

    var estimatedTimeRemaining: TimeInterval? {
        let activeJobs = jobs.filter { $0.status == .processing }
        guard !activeJobs.isEmpty else { return nil }

        let timeEstimates = activeJobs.compactMap { $0.estimatedTimeRemaining }
        guard !timeEstimates.isEmpty else { return nil }

        return timeEstimates.max()
    }

    // MARK: - Codable
    enum CodingKeys: String, CodingKey {
        case id, name, targetFormat, options, quality
        case status, startTime, endTime
    }

    required init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(UUID.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        targetFormat = try container.decode(FileFormat.self, forKey: .targetFormat)
        options = try container.decode(ConversionOptions.self, forKey: .options)
        quality = try container.decode(ConversionQuality.self, forKey: .quality)
        status = try container.decode(BatchStatus.self, forKey: .status)
        startTime = try container.decodeIfPresent(Date.self, forKey: .startTime)
        endTime = try container.decodeIfPresent(Date.self, forKey: .endTime)
        jobs = []
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(name, forKey: .name)
        try container.encode(targetFormat, forKey: .targetFormat)
        try container.encode(options, forKey: .options)
        try container.encode(quality, forKey: .quality)
        try container.encode(status, forKey: .status)
        try container.encodeIfPresent(startTime, forKey: .startTime)
        try container.encodeIfPresent(endTime, forKey: .endTime)
    }
}

// MARK: - 批量转换状态
enum BatchStatus: String, CaseIterable, Codable {
    case pending = "pending"
    case processing = "processing"
    case completed = "completed"
    case partiallyCompleted = "partially_completed"
    case failed = "failed"
    case cancelled = "cancelled"

    var displayName: String {
        switch self {
        case .pending: return "等待中"
        case .processing: return "转换中"
        case .completed: return "全部完成"
        case .partiallyCompleted: return "部分完成"
        case .failed: return "失败"
        case .cancelled: return "已取消"
        }
    }
}