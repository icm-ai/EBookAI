//
//  AIService.swift
//  EBookAI Native
//
//  AI集成服务
//

import Foundation
import Combine
import Alamofire
import AnyCodable
import OSLog

// MARK: - AI服务
@MainActor
class AIService: ObservableObject {
    static let shared = AIService()

    @Published var isProcessing: Bool = false
    @Published var currentProvider: AIProvider = .openai
    @Published var apiKey: String = ""

    private let logger = Logger(subsystem: "com.ebookai.native", category: "AIService")
    private var cancellables = Set<AnyCancellable>()

    private init() {
        loadConfiguration()
    }

    // MARK: - Public Methods
    func enhanceText(_ text: String, type: EnhancementType) async throws -> String {
        logger.info("开始AI文本增强: \(type.displayName)")
        isProcessing = true
        defer { isProcessing = false }

        let request = AIRequest(
            provider: currentProvider,
            type: type,
            content: text,
            options: getEnhancementOptions(for: type)
        )

        return try await processAIRequest(request)
    }

    func generateSummary(_ text: String, maxLength: Int = 200) async throws -> String {
        logger.info("生成文本摘要")
        return try await enhanceText(text, type: .summary(maxLength: maxLength))
    }

    func improveWriting(_ text: String) async throws -> String {
        logger.info("改进写作质量")
        return try await enhanceText(text, type: .writingImprovement)
    }

    func translateText(_ text: String, to language: Language) async throws -> String {
        logger.info("翻译文本到: \(language.displayName)")
        return try await enhanceText(text, type: .translation(to: language))
    }

    func generateChapterTitles(from content: String, chapterCount: Int) async throws -> [String] {
        logger.info("生成章节标题")
        let response = try await enhanceText(content, type: .chapterGeneration(count: chapterCount))
        return parseChapterTitles(response)
    }

    func setProvider(_ provider: AIProvider) {
        currentProvider = provider
        saveConfiguration()
    }

    func setAPIKey(_ key: String) {
        apiKey = key
        saveConfiguration()
    }

    // MARK: - Private Methods
    private func processAIRequest(_ request: AIRequest) async throws -> String {
        guard !apiKey.isEmpty else {
            throw AIError.missingAPIKey
        }

        switch currentProvider {
        case .openai:
            return try await processOpenAIRequest(request)
        case .claude:
            return try await processClaudeRequest(request)
        case .gemini:
            return try await processGeminiRequest(request)
        }
    }

    private func processOpenAIRequest(_ request: AIRequest) async throws -> String {
        let url = "https://api.openai.com/v1/chat/completions"
        let headers: HTTPHeaders = [
            "Authorization": "Bearer \(apiKey)",
            "Content-Type": "application/json"
        ]

        let messages = [
            ["role": "system", "content": request.systemPrompt],
            ["role": "user", "content": request.userPrompt]
        ]

        let parameters: [String: Any] = [
            "model": request.options.model,
            "messages": messages,
            "max_tokens": request.options.maxTokens,
            "temperature": request.options.temperature
        ]

        return try await withCheckedThrowingContinuation { continuation in
            AF.request(url, method: .post, parameters: parameters, encoding: JSONEncoding.default, headers: headers)
                .validate()
                .responseDecodable(of: OpenAIResponse.self) { response in
                    switch response.result {
                    case .success(let aiResponse):
                        if let content = aiResponse.choices.first?.message.content {
                            continuation.resume(returning: content)
                        } else {
                            continuation.resume(throwing: AIError.invalidResponse)
                        }
                    case .failure(let error):
                        continuation.resume(throwing: AIError.networkError(error))
                    }
                }
        }
    }

    private func processClaudeRequest(_ request: AIRequest) async throws -> String {
        let url = "https://api.anthropic.com/v1/messages"
        let headers: HTTPHeaders = [
            "x-api-key": apiKey,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        ]

        let parameters: [String: Any] = [
            "model": request.options.model,
            "max_tokens": request.options.maxTokens,
            "system": request.systemPrompt,
            "messages": [
                ["role": "user", "content": request.userPrompt]
            ]
        ]

        return try await withCheckedThrowingContinuation { continuation in
            AF.request(url, method: .post, parameters: parameters, encoding: JSONEncoding.default, headers: headers)
                .validate()
                .responseDecodable(of: ClaudeResponse.self) { response in
                    switch response.result {
                    case .success(let aiResponse):
                        if let content = aiResponse.content.first?.text {
                            continuation.resume(returning: content)
                        } else {
                            continuation.resume(throwing: AIError.invalidResponse)
                        }
                    case .failure(let error):
                        continuation.resume(throwing: AIError.networkError(error))
                    }
                }
        }
    }

    private func processGeminiRequest(_ request: AIRequest) async throws -> String {
        // Gemini API 实现
        throw AIError.unsupportedProvider
    }

    private func getEnhancementOptions(for type: EnhancementType) -> AIRequestOptions {
        switch type {
        case .summary:
            return AIRequestOptions(
                model: currentProvider.defaultModel,
                maxTokens: 300,
                temperature: 0.3
            )
        case .writingImprovement:
            return AIRequestOptions(
                model: currentProvider.defaultModel,
                maxTokens: 1000,
                temperature: 0.5
            )
        case .translation:
            return AIRequestOptions(
                model: currentProvider.defaultModel,
                maxTokens: 1500,
                temperature: 0.2
            )
        case .chapterGeneration:
            return AIRequestOptions(
                model: currentProvider.defaultModel,
                maxTokens: 500,
                temperature: 0.7
            )
        case .formatting:
            return AIRequestOptions(
                model: currentProvider.defaultModel,
                maxTokens: 800,
                temperature: 0.3
            )
        }
    }

    private func parseChapterTitles(_ response: String) -> [String] {
        return response.components(separatedBy: .newlines)
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    private func loadConfiguration() {
        currentProvider = AIProvider(rawValue: UserDefaults.standard.string(forKey: "AIProvider") ?? "openai") ?? .openai
        apiKey = UserDefaults.standard.string(forKey: "AIAPIKey") ?? ""
    }

    private func saveConfiguration() {
        UserDefaults.standard.set(currentProvider.rawValue, forKey: "AIProvider")
        UserDefaults.standard.set(apiKey, forKey: "AIAPIKey")
    }
}

// MARK: - AI提供商
enum AIProvider: String, CaseIterable, Codable {
    case openai = "openai"
    case claude = "claude"
    case gemini = "gemini"

    var displayName: String {
        switch self {
        case .openai: return "OpenAI"
        case .claude: return "Claude"
        case .gemini: return "Gemini"
        }
    }

    var defaultModel: String {
        switch self {
        case .openai: return "gpt-4"
        case .claude: return "claude-3-sonnet-20240229"
        case .gemini: return "gemini-pro"
        }
    }

    var iconName: String {
        switch self {
        case .openai: return "brain"
        case .claude: return "brain.head.profile"
        case .gemini: return "sparkles"
        }
    }
}

// MARK: - 增强类型
enum EnhancementType {
    case summary(maxLength: Int)
    case writingImprovement
    case translation(to: Language)
    case chapterGeneration(count: Int)
    case formatting

    var displayName: String {
        switch self {
        case .summary: return "生成摘要"
        case .writingImprovement: return "改进写作"
        case .translation(let language): return "翻译为\(language.displayName)"
        case .chapterGeneration: return "生成章节标题"
        case .formatting: return "格式优化"
        }
    }
}

// MARK: - 语言
enum Language: String, CaseIterable, Codable {
    case chinese = "zh"
    case english = "en"
    case japanese = "ja"
    case korean = "ko"
    case french = "fr"
    case german = "de"
    case spanish = "es"

    var displayName: String {
        switch self {
        case .chinese: return "中文"
        case .english: return "English"
        case .japanese: return "日本語"
        case .korean: return "한국어"
        case .french: return "Français"
        case .german: return "Deutsch"
        case .spanish: return "Español"
        }
    }
}

// MARK: - AI请求
struct AIRequest {
    let provider: AIProvider
    let type: EnhancementType
    let content: String
    let options: AIRequestOptions

    var systemPrompt: String {
        switch type {
        case .summary(let maxLength):
            return "你是一个专业的文本摘要专家。请为用户提供的文本生成简洁明了的摘要，长度不超过\(maxLength)字。"
        case .writingImprovement:
            return "你是一个专业的写作指导老师。请改进用户提供的文本，使其更加流畅、准确和富有表现力，但保持原意不变。"
        case .translation(let language):
            return "你是一个专业的翻译专家。请将用户提供的文本翻译为\(language.displayName)，保持原文的风格和语调。"
        case .chapterGeneration(let count):
            return "你是一个专业的编辑。根据用户提供的内容，生成\(count)个章节标题，每个标题单独一行。"
        case .formatting:
            return "你是一个专业的文本格式化专家。请优化用户提供的文本格式，使其更加清晰易读。"
        }
    }

    var userPrompt: String {
        return content
    }
}

// MARK: - AI请求选项
struct AIRequestOptions {
    let model: String
    let maxTokens: Int
    let temperature: Double
}

// MARK: - AI错误
enum AIError: Error, LocalizedError {
    case missingAPIKey
    case invalidResponse
    case networkError(Error)
    case unsupportedProvider
    case rateLimitExceeded
    case contentTooLong

    var errorDescription: String? {
        switch self {
        case .missingAPIKey: return "缺少API密钥"
        case .invalidResponse: return "无效的响应"
        case .networkError(let error): return "网络错误: \(error.localizedDescription)"
        case .unsupportedProvider: return "不支持的AI提供商"
        case .rateLimitExceeded: return "请求频率限制"
        case .contentTooLong: return "内容过长"
        }
    }
}

// MARK: - API响应结构
struct OpenAIResponse: Codable {
    let choices: [OpenAIChoice]
}

struct OpenAIChoice: Codable {
    let message: OpenAIMessage
}

struct OpenAIMessage: Codable {
    let content: String
}

struct ClaudeResponse: Codable {
    let content: [ClaudeContent]
}

struct ClaudeContent: Codable {
    let text: String
}