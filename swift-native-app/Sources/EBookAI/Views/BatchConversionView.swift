//
//  BatchConversionView.swift
//  EBookAI Native
//
//  批量转换视图
//

import SwiftUI

struct BatchConversionView: View {
    @EnvironmentObject var conversionService: ConversionService
    @EnvironmentObject var fileManager: FileManagerService

    @State private var selectedFormat: FileFormat = .pdf
    @State private var selectedQuality: ConversionQuality = .standard
    @State private var conversionOptions = ConversionOptions()
    @State private var batchName: String = ""
    @State private var showingOptionsSheet = false

    var body: some View {
        VStack(spacing: 0) {
            // 批量转换设置
            batchConfigurationSection

            Divider()

            // 文件选择区域
            fileSelectionSection

            Divider()

            // 开始转换按钮
            actionSection
        }
    }

    // MARK: - 批量配置部分
    private var batchConfigurationSection: some View {
        VStack(spacing: 16) {
            HStack {
                Text("批量转换设置")
                    .font(.title2)
                    .fontWeight(.semibold)

                Spacer()
            }

            VStack(spacing: 12) {
                // 批次名称
                HStack {
                    Text("批次名称:")
                        .frame(width: 100, alignment: .leading)

                    TextField("输入批次名称", text: $batchName)
                        .textFieldStyle(.roundedBorder)
                        .onAppear {
                            if batchName.isEmpty {
                                batchName = "批量转换 \(DateFormatter.shortDateTime.string(from: Date()))"
                            }
                        }
                }

                // 目标格式
                HStack {
                    Text("目标格式:")
                        .frame(width: 100, alignment: .leading)

                    Picker("目标格式", selection: $selectedFormat) {
                        ForEach(FileFormat.allCases, id: \.self) { format in
                            Label(format.displayName, systemImage: format.iconName)
                                .tag(format)
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(maxWidth: 200)

                    Spacer()
                }

                // 转换质量
                HStack {
                    Text("转换质量:")
                        .frame(width: 100, alignment: .leading)

                    Picker("转换质量", selection: $selectedQuality) {
                        ForEach(ConversionQuality.allCases, id: \.self) { quality in
                            VStack(alignment: .leading) {
                                Text(quality.displayName)
                                Text(quality.description)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            .tag(quality)
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(maxWidth: 200)

                    Button("高级选项...") {
                        showingOptionsSheet = true
                    }
                    .buttonStyle(.borderless)

                    Spacer()
                }
            }
        }
        .padding()
        .background(Color(NSColor.controlBackgroundColor))
        .sheet(isPresented: $showingOptionsSheet) {
            ConversionOptionsSheet(options: $conversionOptions)
        }
    }

    // MARK: - 文件选择部分
    private var fileSelectionSection: some View {
        VStack(spacing: 12) {
            HStack {
                Text("选择文件")
                    .font(.headline)

                Spacer()

                Button("全选") {
                    fileManager.selectAll()
                }
                .buttonStyle(.borderless)

                Button("取消选择") {
                    fileManager.deselectAll()
                }
                .buttonStyle(.borderless)
            }
            .padding(.horizontal)

            if fileManager.files.isEmpty {
                VStack(spacing: 16) {
                    Image(systemName: "doc.text")
                        .font(.system(size: 48))
                        .foregroundColor(.secondary)

                    Text("没有可用文件")
                        .font(.headline)
                        .foregroundColor(.secondary)

                    Text("请先在文件列表中添加文件")
                        .font(.body)
                        .foregroundColor(.secondary)

                    Button("前往文件列表") {
                        NotificationCenter.default.post(name: .showFileList, object: nil)
                    }
                    .buttonStyle(.borderedProminent)
                }
                .frame(maxWidth: .infinity, minHeight: 200)
            } else {
                ScrollView {
                    LazyVStack(spacing: 8) {
                        ForEach(fileManager.files) { file in
                            BatchFileRowView(
                                file: file,
                                isSelected: fileManager.selectedFiles.contains(file.id),
                                canConvert: file.canConvert(to: selectedFormat),
                                estimatedTime: file.estimatedConversionTime(to: selectedFormat, quality: selectedQuality)
                            ) {
                                fileManager.toggleSelection(file)
                            }
                        }
                    }
                    .padding(.horizontal)
                }
            }
        }
        .frame(maxHeight: .infinity)
    }

    // MARK: - 操作部分
    private var actionSection: some View {
        VStack(spacing: 12) {
            // 批量统计信息
            batchStatistics

            // 开始转换按钮
            HStack {
                Spacer()

                Button("开始批量转换") {
                    startBatchConversion()
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(!canStartConversion)
            }
        }
        .padding()
        .background(Color(NSColor.controlBackgroundColor))
    }

    // MARK: - 批量统计
    private var batchStatistics: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("选中文件: \(selectedFilesCount)")
                    .font(.caption)
                    .foregroundColor(.secondary)

                Text("预计用时: \(estimatedTotalTime)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 4) {
                Text("可转换: \(convertibleFilesCount)")
                    .font(.caption)
                    .foregroundColor(.green)

                if incompatibleFilesCount > 0 {
                    Text("不兼容: \(incompatibleFilesCount)")
                        .font(.caption)
                        .foregroundColor(.orange)
                }
            }
        }
    }

    // MARK: - 计算属性
    private var selectedFiles: [FileItem] {
        fileManager.selectedFileItems
    }

    private var selectedFilesCount: Int {
        selectedFiles.count
    }

    private var convertibleFiles: [FileItem] {
        selectedFiles.filter { $0.canConvert(to: selectedFormat) }
    }

    private var convertibleFilesCount: Int {
        convertibleFiles.count
    }

    private var incompatibleFilesCount: Int {
        selectedFilesCount - convertibleFilesCount
    }

    private var estimatedTotalTime: String {
        let totalTime = convertibleFiles.reduce(0) { total, file in
            total + file.estimatedConversionTime(to: selectedFormat, quality: selectedQuality)
        }
        return formatTimeInterval(totalTime)
    }

    private var canStartConversion: Bool {
        !batchName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        convertibleFilesCount > 0
    }

    // MARK: - 方法
    private func startBatchConversion() {
        let batchJob = BatchConversionJob(
            name: batchName.trimmingCharacters(in: .whitespacesAndNewlines),
            sourceFiles: convertibleFiles,
            targetFormat: selectedFormat,
            options: conversionOptions,
            quality: selectedQuality
        )

        Task {
            await conversionService.startBatchConversion(batchJob)
        }

        // 切换到转换视图查看进度
        NotificationCenter.default.post(name: .showConversionQueue, object: nil)
    }
}

// MARK: - 批量文件行视图
struct BatchFileRowView: View {
    let file: FileItem
    let isSelected: Bool
    let canConvert: Bool
    let estimatedTime: TimeInterval
    let onToggle: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            // 选择复选框
            Button(action: onToggle) {
                Image(systemName: isSelected ? "checkmark.square.fill" : "square")
                    .font(.title2)
                    .foregroundColor(isSelected ? .accentColor : .secondary)
            }
            .buttonStyle(.plain)
            .disabled(!canConvert)

            // 文件图标
            Image(systemName: file.iconName)
                .font(.title2)
                .foregroundColor(canConvert ? .accentColor : .secondary)
                .frame(width: 24)

            // 文件信息
            VStack(alignment: .leading, spacing: 4) {
                Text(file.displayName)
                    .font(.body)
                    .fontWeight(.medium)
                    .lineLimit(1)

                HStack {
                    Label(file.format.displayName, systemImage: file.format.iconName)
                        .font(.caption)
                        .foregroundColor(.secondary)

                    Text("•")
                        .font(.caption)
                        .foregroundColor(.secondary)

                    Text(file.formattedSize)
                        .font(.caption)
                        .foregroundColor(.secondary)

                    if !canConvert {
                        Text("•")
                            .font(.caption)
                            .foregroundColor(.secondary)

                        Text("不支持转换")
                            .font(.caption)
                            .foregroundColor(.orange)
                    }
                }
            }

            Spacer()

            // 预计时间
            if canConvert {
                VStack(alignment: .trailing, spacing: 2) {
                    Text("预计用时")
                        .font(.caption2)
                        .foregroundColor(.secondary)

                    Text(formatTimeInterval(estimatedTime))
                        .font(.caption)
                        .fontWeight(.medium)
                }
            } else {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundColor(.orange)
            }
        }
        .padding(.vertical, 8)
        .padding(.horizontal, 12)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(isSelected && canConvert ? Color.accentColor.opacity(0.1) : Color.clear)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(isSelected && canConvert ? Color.accentColor.opacity(0.3) : Color.clear, lineWidth: 1)
        )
        .opacity(canConvert ? 1.0 : 0.6)
    }
}

// MARK: - 日期格式化扩展
extension DateFormatter {
    static let shortDateTime: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .short
        formatter.timeStyle = .short
        return formatter
    }()
}

// MARK: - 辅助函数
private func formatTimeInterval(_ interval: TimeInterval) -> String {
    if interval < 60 {
        return "\(Int(interval))秒"
    } else if interval < 3600 {
        return "\(Int(interval / 60))分钟"
    } else {
        let hours = Int(interval / 3600)
        let minutes = Int((interval.truncatingRemainder(dividingBy: 3600)) / 60)
        return "\(hours)小时\(minutes)分钟"
    }
}

// MARK: - 预览
#Preview {
    BatchConversionView()
        .environmentObject(ConversionService.shared)
        .environmentObject(FileManagerService.shared)
        .frame(width: 800, height: 600)
}