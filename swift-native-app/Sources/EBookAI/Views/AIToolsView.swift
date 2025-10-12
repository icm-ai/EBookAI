//
//  AIToolsView.swift
//  EBookAI Native
//
//  AI工具视图
//

import SwiftUI

struct AIToolsView: View {
    @EnvironmentObject var aiService: AIService
    @State private var inputText: String = ""
    @State private var outputText: String = ""
    @State private var selectedTool: AITool = .summary
    @State private var maxSummaryLength: Int = 200
    @State private var targetLanguage: Language = .english
    @State private var chapterCount: Int = 5

    var body: some View {
        HSplitView {
            // 左侧：工具选择和配置
            VStack(spacing: 0) {
                toolSelection
                Divider()
                toolConfiguration
                Spacer()
            }
            .frame(minWidth: 300, maxWidth: 400)

            // 右侧：输入输出区域
            VStack(spacing: 0) {
                inputOutputArea
            }
        }
    }

    // MARK: - 工具选择
    private var toolSelection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("AI工具")
                .font(.title2)
                .fontWeight(.semibold)

            LazyVStack(spacing: 8) {
                ForEach(AITool.allCases, id: \.self) { tool in
                    AIToolButton(
                        tool: tool,
                        isSelected: selectedTool == tool,
                        isProcessing: aiService.isProcessing
                    ) {
                        selectedTool = tool
                        // 清空之前的输出
                        outputText = ""
                    }
                }
            }
        }
        .padding()
        .background(Color(NSColor.controlBackgroundColor))
    }

    // MARK: - 工具配置
    @ViewBuilder
    private var toolConfiguration: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("配置")
                .font(.headline)

            switch selectedTool {
            case .summary:
                summaryConfiguration
            case .translation:
                translationConfiguration
            case .chapterGeneration:
                chapterConfiguration
            case .writingImprovement, .formatting:
                EmptyView()
            }
        }
        .padding()
    }

    private var summaryConfiguration: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("摘要长度")
                .font(.caption)
                .foregroundColor(.secondary)

            HStack {
                Slider(value: Binding(
                    get: { Double(maxSummaryLength) },
                    set: { maxSummaryLength = Int($0) }
                ), in: 50...500, step: 50) {
                    Text("长度")
                }

                Text("\(maxSummaryLength)字")
                    .font(.caption)
                    .frame(width: 50)
            }
        }
    }

    private var translationConfiguration: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("目标语言")
                .font(.caption)
                .foregroundColor(.secondary)

            Picker("目标语言", selection: $targetLanguage) {
                ForEach(Language.allCases, id: \.self) { language in
                    Text(language.displayName).tag(language)
                }
            }
            .pickerStyle(.menu)
        }
    }

    private var chapterConfiguration: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("章节数量")
                .font(.caption)
                .foregroundColor(.secondary)

            Stepper(value: $chapterCount, in: 1...20, step: 1) {
                Text("\(chapterCount) 个章节")
            }
        }
    }

    // MARK: - 输入输出区域
    private var inputOutputArea: some View {
        VStack(spacing: 0) {
            // 顶部工具栏
            HStack {
                Text(selectedTool.displayName)
                    .font(.headline)
                    .fontWeight(.semibold)

                Spacer()

                if !inputText.isEmpty {
                    Button("清空输入") {
                        inputText = ""
                    }
                    .buttonStyle(.borderless)
                }

                if !outputText.isEmpty {
                    Button("复制结果") {
                        copyToClipboard(outputText)
                    }
                    .buttonStyle(.borderless)
                }

                Button("处理") {
                    processText()
                }
                .buttonStyle(.borderedProminent)
                .disabled(inputText.isEmpty || aiService.isProcessing)
            }
            .padding()
            .background(Color(NSColor.controlBackgroundColor))

            Divider()

            // 输入输出区域
            HSplitView {
                // 输入区域
                VStack(alignment: .leading, spacing: 8) {
                    Text("输入文本")
                        .font(.caption)
                        .foregroundColor(.secondary)

                    ScrollView {
                        TextEditor(text: $inputText)
                            .font(.body)
                            .disabled(aiService.isProcessing)
                    }
                }
                .padding()

                // 输出区域
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text("AI处理结果")
                            .font(.caption)
                            .foregroundColor(.secondary)

                        Spacer()

                        if aiService.isProcessing {
                            HStack(spacing: 8) {
                                ProgressView()
                                    .scaleEffect(0.7)
                                Text("处理中...")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }

                    ScrollView {
                        if outputText.isEmpty && !aiService.isProcessing {
                            VStack(spacing: 16) {
                                Image(systemName: selectedTool.iconName)
                                    .font(.system(size: 48))
                                    .foregroundColor(.secondary)

                                Text(selectedTool.description)
                                    .font(.body)
                                    .foregroundColor(.secondary)
                                    .multilineTextAlignment(.center)
                                    .padding(.horizontal)
                            }
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                        } else {
                            TextEditor(text: .constant(outputText))
                                .font(.body)
                                .disabled(true)
                        }
                    }
                }
                .padding()
                .background(Color(NSColor.textBackgroundColor))
            }
        }
    }

    // MARK: - 方法
    private func processText() {
        guard !inputText.isEmpty else { return }

        Task {
            do {
                let result: String
                switch selectedTool {
                case .summary:
                    result = try await aiService.generateSummary(inputText, maxLength: maxSummaryLength)
                case .writingImprovement:
                    result = try await aiService.improveWriting(inputText)
                case .translation:
                    result = try await aiService.translateText(inputText, to: targetLanguage)
                case .chapterGeneration:
                    let chapters = try await aiService.generateChapterTitles(from: inputText, chapterCount: chapterCount)
                    result = chapters.enumerated().map { index, title in
                        "第\(index + 1)章: \(title)"
                    }.joined(separator: "\n")
                case .formatting:
                    result = try await aiService.enhanceText(inputText, type: .formatting)
                }

                await MainActor.run {
                    outputText = result
                }
            } catch {
                await MainActor.run {
                    outputText = "处理失败: \(error.localizedDescription)"
                }
            }
        }
    }

    private func copyToClipboard(_ text: String) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
    }
}

// MARK: - AI工具枚举
enum AITool: String, CaseIterable {
    case summary = "summary"
    case writingImprovement = "writing"
    case translation = "translation"
    case chapterGeneration = "chapters"
    case formatting = "formatting"

    var displayName: String {
        switch self {
        case .summary: return "生成摘要"
        case .writingImprovement: return "改进写作"
        case .translation: return "文本翻译"
        case .chapterGeneration: return "生成章节"
        case .formatting: return "格式优化"
        }
    }

    var iconName: String {
        switch self {
        case .summary: return "doc.text"
        case .writingImprovement: return "pencil.and.outline"
        case .translation: return "globe"
        case .chapterGeneration: return "list.number"
        case .formatting: return "text.alignleft"
        }
    }

    var description: String {
        switch self {
        case .summary: return "为长文本生成简洁明了的摘要"
        case .writingImprovement: return "改进文本的流畅性和表达力"
        case .translation: return "将文本翻译为指定语言"
        case .chapterGeneration: return "根据内容生成章节标题"
        case .formatting: return "优化文本格式和排版"
        }
    }
}

// MARK: - AI工具按钮
struct AIToolButton: View {
    let tool: AITool
    let isSelected: Bool
    let isProcessing: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: tool.iconName)
                    .font(.title2)
                    .foregroundColor(isSelected ? .white : .accentColor)
                    .frame(width: 24)

                VStack(alignment: .leading, spacing: 2) {
                    Text(tool.displayName)
                        .font(.body)
                        .fontWeight(.medium)
                        .foregroundColor(isSelected ? .white : .primary)

                    Text(tool.description)
                        .font(.caption)
                        .foregroundColor(isSelected ? .white.opacity(0.8) : .secondary)
                        .lineLimit(2)
                }

                Spacer()
            }
            .padding(.vertical, 8)
            .padding(.horizontal, 12)
        }
        .buttonStyle(.plain)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(isSelected ? Color.accentColor : Color.clear)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(isSelected ? Color.clear : Color.accentColor.opacity(0.3), lineWidth: 1)
        )
        .disabled(isProcessing)
    }
}

// MARK: - 预览
#Preview {
    AIToolsView()
        .environmentObject(AIService.shared)
        .frame(width: 1000, height: 600)
}