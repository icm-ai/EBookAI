//
//  ConversionView.swift
//  EBookAI Native
//
//  转换视图
//

import SwiftUI

struct ConversionView: View {
    @EnvironmentObject var conversionService: ConversionService
    @State private var selectedQuality: ConversionQuality = .standard
    @State private var showingOptionsSheet = false
    @State private var conversionOptions = ConversionOptions()

    var body: some View {
        VStack(spacing: 0) {
            // 工具栏
            conversionToolbar

            // 主内容
            if conversionService.activeJobs.isEmpty && conversionService.completedJobs.isEmpty {
                emptyState
            } else {
                conversionContent
            }
        }
        .sheet(isPresented: $showingOptionsSheet) {
            ConversionOptionsSheet(options: $conversionOptions)
        }
    }

    // MARK: - 转换工具栏
    private var conversionToolbar: some View {
        HStack {
            // 质量选择
            HStack {
                Text("质量:")
                    .font(.caption)
                    .foregroundColor(.secondary)

                Picker("转换质量", selection: $selectedQuality) {
                    ForEach(ConversionQuality.allCases, id: \.self) { quality in
                        Text(quality.displayName).tag(quality)
                    }
                }
                .pickerStyle(.menu)
                .frame(width: 120)
            }

            // 转换选项
            Button("转换选项...") {
                showingOptionsSheet = true
            }
            .buttonStyle(.borderless)

            Spacer()

            // 控制按钮
            HStack(spacing: 8) {
                if conversionService.isProcessing {
                    Button("暂停全部") {
                        conversionService.cancelAllJobs()
                    }
                    .buttonStyle(.borderedProminent)
                }

                if !conversionService.completedJobs.isEmpty {
                    Button("清除已完成") {
                        conversionService.clearCompletedJobs()
                    }
                    .buttonStyle(.bordered)
                }
            }
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

    // MARK: - 转换内容
    private var conversionContent: some View {
        VStack(spacing: 0) {
            // 活动任务
            if !conversionService.activeJobs.isEmpty {
                Section {
                    ForEach(conversionService.activeJobs) { job in
                        ActiveJobView(job: job)
                            .padding(.horizontal)
                            .padding(.vertical, 8)
                    }
                } header: {
                    sectionHeader("活动任务 (\(conversionService.activeJobs.count))")
                }
            }

            // 已完成任务
            if !conversionService.completedJobs.isEmpty {
                Section {
                    ScrollView {
                        LazyVStack(spacing: 8) {
                            ForEach(conversionService.completedJobs) { job in
                                CompletedJobView(job: job)
                                    .padding(.horizontal)
                            }
                        }
                        .padding(.vertical, 8)
                    }
                } header: {
                    sectionHeader("已完成任务 (\(conversionService.completedJobs.count))")
                }
            }
        }
    }

    // MARK: - 空状态
    private var emptyState: some View {
        VStack(spacing: 20) {
            Image(systemName: "arrow.triangle.2.circlepath")
                .font(.system(size: 64))
                .foregroundColor(.secondary)

            VStack(spacing: 8) {
                Text("没有转换任务")
                    .font(.title2)
                    .fontWeight(.medium)

                Text("从文件列表中选择文件开始转换")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }

            Button("前往文件列表") {
                NotificationCenter.default.post(name: .showFileList, object: nil)
            }
            .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(NSColor.textBackgroundColor))
    }

    // MARK: - 节标题
    private func sectionHeader(_ title: String) -> some View {
        HStack {
            Text(title)
                .font(.headline)
                .fontWeight(.semibold)
                .foregroundColor(.primary)

            Spacer()
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(Color(NSColor.controlBackgroundColor).opacity(0.5))
    }
}

// MARK: - 活动任务视图
struct ActiveJobView: View {
    @ObservedObject var job: ConversionJob
    @EnvironmentObject var conversionService: ConversionService

    var body: some View {
        VStack(spacing: 12) {
            // 任务信息
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(job.sourceFile.displayName)
                        .font(.headline)
                        .lineLimit(1)

                    HStack {
                        Label(job.sourceFile.format.displayName, systemImage: job.sourceFile.format.iconName)
                        Image(systemName: "arrow.right")
                        Label(job.targetFormat.displayName, systemImage: job.targetFormat.iconName)
                    }
                    .font(.caption)
                    .foregroundColor(.secondary)
                }

                Spacer()

                // 状态指示器
                HStack(spacing: 8) {
                    Image(systemName: job.status.iconName)
                        .foregroundColor(Color(job.status.color))

                    Text(job.status.displayName)
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(Color(job.status.color))
                }
            }

            // 进度条
            VStack(spacing: 6) {
                HStack {
                    Text(job.progress.localizedDescription.isEmpty ? "准备中..." : job.progress.localizedDescription)
                        .font(.caption)
                        .foregroundColor(.secondary)

                    Spacer()

                    Text("\(Int(job.progress.fractionCompleted * 100))%")
                        .font(.caption)
                        .fontWeight(.medium)
                }

                ProgressView(value: job.progress.fractionCompleted)
                    .progressViewStyle(.linear)

                if let estimatedTime = job.estimatedTimeRemaining {
                    HStack {
                        Text("预计剩余时间:")
                            .font(.caption2)
                            .foregroundColor(.secondary)

                        Text(formatTimeInterval(estimatedTime))
                            .font(.caption2)
                            .fontWeight(.medium)

                        Spacer()
                    }
                }
            }

            // 操作按钮
            HStack {
                Spacer()

                Button("取消") {
                    conversionService.cancelJob(job)
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(Color(NSColor.controlBackgroundColor))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(Color.accentColor.opacity(0.3), lineWidth: 1)
        )
    }
}

// MARK: - 已完成任务视图
struct CompletedJobView: View {
    @ObservedObject var job: ConversionJob

    var body: some View {
        HStack(spacing: 12) {
            // 状态图标
            Image(systemName: job.status.iconName)
                .font(.title2)
                .foregroundColor(Color(job.status.color))
                .frame(width: 24)

            // 任务信息
            VStack(alignment: .leading, spacing: 4) {
                Text(job.sourceFile.displayName)
                    .font(.body)
                    .fontWeight(.medium)
                    .lineLimit(1)

                HStack {
                    Label(job.sourceFile.format.displayName, systemImage: job.sourceFile.format.iconName)
                    Image(systemName: "arrow.right")
                    Label(job.targetFormat.displayName, systemImage: job.targetFormat.iconName)
                }
                .font(.caption)
                .foregroundColor(.secondary)

                if job.status == .failed, let error = job.error {
                    Text(error.message)
                        .font(.caption)
                        .foregroundColor(.red)
                        .lineLimit(2)
                }
            }

            Spacer()

            // 时间信息
            VStack(alignment: .trailing, spacing: 2) {
                if let duration = job.duration {
                    Text("用时: \(formatTimeInterval(duration))")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                if let endTime = job.endTime {
                    Text(endTime, style: .relative)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            // 操作按钮
            VStack(spacing: 4) {
                if job.status == .completed, let outputFile = job.outputFile {
                    Button("打开") {
                        NSWorkspace.shared.open(outputFile.url)
                    }
                    .buttonStyle(.borderless)
                    .controlSize(.small)

                    Button("显示") {
                        NSWorkspace.shared.selectFile(outputFile.url.path, inFileViewerRootedAtPath: "")
                    }
                    .buttonStyle(.borderless)
                    .controlSize(.small)
                } else if job.status == .failed {
                    Button("重试") {
                        // 重新开始转换
                        let newJob = ConversionJob(
                            sourceFile: job.sourceFile,
                            targetFormat: job.targetFormat,
                            options: job.options,
                            quality: job.quality
                        )
                        Task {
                            await ConversionService.shared.startConversion(newJob)
                        }
                    }
                    .buttonStyle(.borderless)
                    .controlSize(.small)
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(Color(NSColor.controlBackgroundColor).opacity(0.5))
        )
    }
}

// MARK: - 转换选项表单
struct ConversionOptionsSheet: View {
    @Binding var options: ConversionOptions
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationView {
            Form {
                Section("格式选项") {
                    Toggle("保留格式", isOn: $options.preserveFormatting)
                    Toggle("嵌入图片", isOn: $options.embedImages)
                    Toggle("生成目录", isOn: $options.generateTOC)
                    Toggle("优化阅读", isOn: $options.optimizeForReading)
                }

                Section("压缩设置") {
                    Picker("压缩级别", selection: $options.compressionLevel) {
                        ForEach(ConversionOptions.CompressionLevel.allCases, id: \.self) { level in
                            Text(level.displayName).tag(level)
                        }
                    }
                }

                Section("页面设置") {
                    Picker("页面大小", selection: $options.pageSize) {
                        ForEach(ConversionOptions.PageSize.allCases, id: \.self) { size in
                            Text(size.displayName).tag(size)
                        }
                    }

                    VStack(alignment: .leading) {
                        Text("页边距 (cm)")
                            .font(.caption)
                            .foregroundColor(.secondary)

                        HStack {
                            VStack {
                                Text("上")
                                TextField("", value: $options.margins.top, format: .number)
                                    .textFieldStyle(.roundedBorder)
                            }
                            VStack {
                                Text("下")
                                TextField("", value: $options.margins.bottom, format: .number)
                                    .textFieldStyle(.roundedBorder)
                            }
                            VStack {
                                Text("左")
                                TextField("", value: $options.margins.left, format: .number)
                                    .textFieldStyle(.roundedBorder)
                            }
                            VStack {
                                Text("右")
                                TextField("", value: $options.margins.right, format: .number)
                                    .textFieldStyle(.roundedBorder)
                            }
                        }
                    }
                }

                Section("字体设置") {
                    TextField("字体族", text: $options.fontSettings.family)
                        .textFieldStyle(.roundedBorder)

                    HStack {
                        Text("字体大小")
                        Spacer()
                        Stepper(value: $options.fontSettings.size, in: 8...72, step: 1) {
                            Text("\(Int(options.fontSettings.size))pt")
                        }
                    }

                    HStack {
                        Text("行高")
                        Spacer()
                        Stepper(value: $options.fontSettings.lineHeight, in: 1.0...3.0, step: 0.1) {
                            Text(String(format: "%.1f", options.fontSettings.lineHeight))
                        }
                    }
                }
            }
            .navigationTitle("转换选项")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") {
                        dismiss()
                    }
                }

                ToolbarItem(placement: .confirmationAction) {
                    Button("完成") {
                        dismiss()
                    }
                }
            }
        }
        .frame(width: 500, height: 600)
    }
}

// MARK: - 辅助函数
private func formatTimeInterval(_ interval: TimeInterval) -> String {
    let formatter = DateComponentsFormatter()
    formatter.allowedUnits = [.hour, .minute, .second]
    formatter.unitsStyle = .abbreviated
    return formatter.string(from: interval) ?? ""
}

// MARK: - 预览
#Preview {
    ConversionView()
        .environmentObject(ConversionService.shared)
        .frame(width: 800, height: 600)
}