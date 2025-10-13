//
//  App.swift
//  EBookAI Native
//
//  纯Swift原生macOS应用入口
//

import SwiftUI

@main
struct EBookAINativeApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var conversionService = ConversionService.shared
    @StateObject private var aiService = AIService.shared
    @StateObject private var fileManager = FileManagerService.shared

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(conversionService)
                .environmentObject(aiService)
                .environmentObject(fileManager)
                .frame(minWidth: 1200, minHeight: 800)
        }
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unified)
        .commands {
            AppCommands()
        }

        Settings {
            SettingsView()
                .environmentObject(aiService)
                .frame(width: 600, height: 500)
        }
    }
}

// MARK: - 应用委托
class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        setupApp()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }

    private func setupApp() {
        // 设置应用外观
        NSApp.appearance = NSAppearance(named: .aqua)

        // 配置日志
        setupLogging()

        // 创建必要的目录
        createAppDirectories()
    }

    private func setupLogging() {
        // 配置日志系统
    }

    private func createAppDirectories() {
        let documentsURL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        let appDirectories = [
            "EBookAI/Converted",
            "EBookAI/Temp",
            "EBookAI/Exports"
        ]

        for directory in appDirectories {
            let directoryURL = documentsURL.appendingPathComponent(directory)
            try? FileManager.default.createDirectory(at: directoryURL, withIntermediateDirectories: true)
        }
    }
}

// MARK: - 应用命令
struct AppCommands: Commands {
    var body: some Commands {
        CommandGroup(replacing: .newItem) {
            Button("添加文件...") {
                NotificationCenter.default.post(name: .addFiles, object: nil)
            }
            .keyboardShortcut("o", modifiers: .command)

            Button("添加文件夹...") {
                NotificationCenter.default.post(name: .addFolder, object: nil)
            }
            .keyboardShortcut("o", modifiers: [.command, .shift])
        }

        CommandMenu("转换") {
            Button("开始转换") {
                NotificationCenter.default.post(name: .startConversion, object: nil)
            }
            .keyboardShortcut(.return, modifiers: .command)

            Button("暂停转换") {
                NotificationCenter.default.post(name: .pauseConversion, object: nil)
            }
            .keyboardShortcut("p", modifiers: .command)

            Divider()

            Button("清除已完成") {
                NotificationCenter.default.post(name: .clearCompleted, object: nil)
            }
            .keyboardShortcut("k", modifiers: [.command, .shift])
        }

        CommandMenu("AI") {
            Button("文本增强") {
                NotificationCenter.default.post(name: .enhanceText, object: nil)
            }
            .keyboardShortcut("e", modifiers: [.command, .option])

            Button("生成摘要") {
                NotificationCenter.default.post(name: .generateSummary, object: nil)
            }
            .keyboardShortcut("s", modifiers: [.command, .option])
        }

        CommandGroup(after: .windowArrangement) {
            Button("显示文件列表") {
                NotificationCenter.default.post(name: .showFileList, object: nil)
            }
            .keyboardShortcut("1", modifiers: .command)

            Button("显示转换队列") {
                NotificationCenter.default.post(name: .showConversionQueue, object: nil)
            }
            .keyboardShortcut("2", modifiers: .command)

            Button("显示AI工具") {
                NotificationCenter.default.post(name: .showAITools, object: nil)
            }
            .keyboardShortcut("3", modifiers: .command)
        }
    }
}

// MARK: - 通知名称扩展
extension Notification.Name {
    static let addFiles = Notification.Name("addFiles")
    static let addFolder = Notification.Name("addFolder")
    static let startConversion = Notification.Name("startConversion")
    static let pauseConversion = Notification.Name("pauseConversion")
    static let clearCompleted = Notification.Name("clearCompleted")
    static let enhanceText = Notification.Name("enhanceText")
    static let generateSummary = Notification.Name("generateSummary")
    static let showFileList = Notification.Name("showFileList")
    static let showConversionQueue = Notification.Name("showConversionQueue")
    static let showAITools = Notification.Name("showAITools")
}