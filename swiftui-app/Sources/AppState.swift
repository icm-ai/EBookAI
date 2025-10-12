//
//  AppState.swift
//  EBookAI
//
//  应用状态管理和业务逻辑
//

import SwiftUI
import Foundation
import Combine

class AppState: ObservableObject {
    // MARK: - Published Properties
    @Published var showSidebar = true
    @Published var selectedTab: AppTab = .singleFile
    @Published var isBackendConnected = false
    @Published var statusMessage = "准备就绪"
    @Published var currentProgress: ProgressInfo?
    @Published var recentFiles: [URL] = []

    // MARK: - Private Properties
    private var backendProcess: Process?
    private var frontendProcess: Process?
    private var connectionCheckTimer: Timer?
    private var cancellables = Set<AnyCancellable>()

    // MARK: - Configuration
    private let backendPort = 8000
    private let frontendPort = 3000
    private let maxRecentFiles = 10

    var webViewURL: URL {
        URL(string: "http://localhost:\(frontendPort)")!
    }

    var webViewCoordinator = WebViewCoordinator()

    // MARK: - Initialization
    init() {
        loadRecentFiles()
        setupWebViewCoordinator()
    }

    deinit {
        stopBackendService()
        stopFrontendService()
    }

    // MARK: - Backend Service Management
    func startBackendService() {
        guard backendProcess == nil else { return }

        statusMessage = "启动后端服务..."

        // 启动FastAPI后端
        #if DEBUG
        let pythonPath = getBackendExecutablePath()
        let scriptPath = getBackendScriptPath()
        backendProcess = Process()
        backendProcess?.executableURL = URL(fileURLWithPath: pythonPath)
        backendProcess?.arguments = [scriptPath]
        backendProcess?.environment = [
            "PORT": "\(backendPort)",
            "HOST": "127.0.0.1",
            "PYTHONPATH": scriptPath.replacingOccurrences(of: "/src/main.py", with: "")
        ]
        #else
        let backendPath = getBackendExecutablePath()
        backendProcess = Process()
        backendProcess?.executableURL = URL(fileURLWithPath: backendPath)
        backendProcess?.environment = [
            "PORT": "\(backendPort)",
            "HOST": "127.0.0.1"
        ]
        #endif

        do {
            try backendProcess?.run()
            statusMessage = "后端服务已启动"

            // 启动前端开发服务器（开发模式）或提供静态文件
            #if DEBUG
            startFrontendDevServer()
            #else
            // 生产模式：前端已打包到应用内
            #endif

            // 开始检查连接状态
            startConnectionCheck()

        } catch {
            statusMessage = "后端服务启动失败: \(error.localizedDescription)"
        }
    }

    func stopBackendService() {
        backendProcess?.terminate()
        backendProcess = nil

        stopFrontendService()
        stopConnectionCheck()

        isBackendConnected = false
        statusMessage = "服务已停止"
    }

    private func startFrontendDevServer() {
        guard frontendProcess == nil else { return }

        let frontendPath = getFrontendPath()
        frontendProcess = Process()
        frontendProcess?.executableURL = URL(fileURLWithPath: "/usr/bin/npm")
        frontendProcess?.arguments = ["start"]
        frontendProcess?.currentDirectoryURL = URL(fileURLWithPath: frontendPath)

        do {
            try frontendProcess?.run()
        } catch {
            print("前端服务启动失败: \(error)")
        }
    }

    private func stopFrontendService() {
        frontendProcess?.terminate()
        frontendProcess = nil
    }

    // MARK: - Connection Management
    private func startConnectionCheck() {
        connectionCheckTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { _ in
            self.checkBackendConnection()
        }
    }

    private func stopConnectionCheck() {
        connectionCheckTimer?.invalidate()
        connectionCheckTimer = nil
    }

    private func checkBackendConnection() {
        guard let url = URL(string: "http://localhost:\(backendPort)/health") else { return }

        URLSession.shared.dataTask(with: url) { _, response, _ in
            DispatchQueue.main.async {
                if let httpResponse = response as? HTTPURLResponse,
                   httpResponse.statusCode == 200 {
                    if !self.isBackendConnected {
                        self.isBackendConnected = true
                        self.statusMessage = "服务运行中"
                    }
                } else {
                    if self.isBackendConnected {
                        self.isBackendConnected = false
                        self.statusMessage = "连接中断"
                    }
                }
            }
        }.resume()
    }

    // MARK: - File Management
    func addFiles(_ urls: [URL]) {
        // 添加到最近文件
        for url in urls {
            addToRecentFiles(url)
        }

        // 通过JavaScript Bridge发送到WebView
        let fileData = urls.map { [
            "path": $0.path,
            "name": $0.lastPathComponent,
            "size": getFileSize($0)
        ] }

        webViewCoordinator.sendMessage("filesAdded", data: fileData)
    }

    func openFile(_ url: URL) {
        addFiles([url])
        // 导航到单文件转换页面
        navigateWebView(to: "/")
    }

    private func addToRecentFiles(_ url: URL) {
        // 移除重复项
        recentFiles.removeAll { $0 == url }
        // 添加到开头
        recentFiles.insert(url, at: 0)
        // 限制数量
        if recentFiles.count > maxRecentFiles {
            recentFiles = Array(recentFiles.prefix(maxRecentFiles))
        }
        // 保存到UserDefaults
        saveRecentFiles()
    }

    private func getFileSize(_ url: URL) -> Int64 {
        do {
            let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
            return attributes[.size] as? Int64 ?? 0
        } catch {
            return 0
        }
    }

    // MARK: - WebView Integration
    func navigateWebView(to path: String) {
        webViewCoordinator.navigate(to: "http://localhost:\(frontendPort)\(path)")
    }

    private func setupWebViewCoordinator() {
        // 设置WebView回调
        webViewCoordinator.onProgressUpdate = { [weak self] progress in
            DispatchQueue.main.async {
                self?.currentProgress = ProgressInfo(
                    percentage: progress["percentage"] as? Double ?? 0,
                    message: progress["message"] as? String ?? ""
                )
            }
        }

        webViewCoordinator.onProgressComplete = { [weak self] in
            DispatchQueue.main.async {
                self?.currentProgress = nil
                self?.statusMessage = "转换完成"
            }
        }

        webViewCoordinator.onError = { [weak self] error in
            DispatchQueue.main.async {
                self?.showError(error)
            }
        }
    }

    // MARK: - Error Handling
    func showError(_ message: String) {
        statusMessage = "错误: \(message)"
        currentProgress = nil

        // 显示系统通知
        let notification = NSUserNotification()
        notification.title = "EBookAI"
        notification.informativeText = message
        notification.soundName = NSUserNotificationDefaultSoundName
        NSUserNotificationCenter.default.deliver(notification)
    }

    // MARK: - Persistence
    private func loadRecentFiles() {
        if let data = UserDefaults.standard.data(forKey: "RecentFiles"),
           let urls = try? NSKeyedUnarchiver.unarchiveTopLevelObjectWithData(data) as? [URL] {
            recentFiles = urls.filter { FileManager.default.fileExists(atPath: $0.path) }
        }
    }

    private func saveRecentFiles() {
        if let data = try? NSKeyedArchiver.archivedData(withRootObject: recentFiles, requiringSecureCoding: false) {
            UserDefaults.standard.set(data, forKey: "RecentFiles")
        }
    }

    // MARK: - Path Helpers
    private func getBackendExecutablePath() -> String {
        #if DEBUG
        // 开发模式：使用源码运行
        return "/usr/bin/python3"
        #else
        // 生产模式：使用打包的可执行文件
        let bundle = Bundle.main
        let resourcePath = bundle.resourcePath ?? ""
        return "\(resourcePath)/backend/main"
        #endif
    }

    private func getBackendScriptPath() -> String {
        #if DEBUG
        // 开发模式：使用源码路径
        let bundle = Bundle.main
        let resourcePath = bundle.resourcePath ?? ""
        return "\(resourcePath)/../../../backend/src/main.py"
        #else
        // 生产模式：使用打包的脚本
        let bundle = Bundle.main
        let resourcePath = bundle.resourcePath ?? ""
        return "\(resourcePath)/backend/main.py"
        #endif
    }

    private func getFrontendPath() -> String {
        #if DEBUG
        // 开发模式：使用开发服务器
        let bundle = Bundle.main
        let resourcePath = bundle.resourcePath ?? ""
        return "\(resourcePath)/../../../frontend/web"
        #else
        // 生产模式：使用打包的前端文件
        let bundle = Bundle.main
        let resourcePath = bundle.resourcePath ?? ""
        return "\(resourcePath)/frontend"
        #endif
    }
}