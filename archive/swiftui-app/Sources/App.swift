//
//  App.swift
//  EBookAI
//
//  SwiftUI应用入口点
//

import SwiftUI

@main
struct EBookAIApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        WindowGroup {
            ContentView()
                .frame(minWidth: 1000, minHeight: 700)
                .background(Color(NSColor.windowBackgroundColor))
        }
        .windowStyle(DefaultWindowStyle())
        .commands {
            // 应用菜单栏命令
            AppCommands()
        }

        #if os(macOS)
        Settings {
            PreferencesView()
        }
        #endif
    }
}

// MARK: - 应用委托
class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // 应用启动完成后的初始化
        setupAppearance()
        setupNotifications()
    }

    func applicationWillTerminate(_ notification: Notification) {
        // 应用即将退出时的清理工作
        cleanupResources()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }

    // MARK: - 私有方法
    private func setupAppearance() {
        // 设置应用外观
        if #available(macOS 11.0, *) {
            NSApp.appearance = NSAppearance(named: .aqua)
        }
    }

    private func setupNotifications() {
        // 设置通知观察者
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleSelectFileRequest),
            name: .selectFileRequested,
            object: nil
        )
    }

    private func cleanupResources() {
        // 清理资源
        NotificationCenter.default.removeObserver(self)
    }

    @objc private func handleSelectFileRequest() {
        // 处理文件选择请求
        DispatchQueue.main.async {
            if let window = NSApp.keyWindow {
                let panel = NSOpenPanel()
                panel.allowedContentTypes = [
                    .init(filenameExtension: "epub")!,
                    .init(filenameExtension: "pdf")!,
                    .init(filenameExtension: "txt")!,
                    .init(filenameExtension: "mobi")!,
                    .init(filenameExtension: "azw3")!
                ]
                panel.allowsMultipleSelection = true
                panel.canChooseDirectories = false

                panel.beginSheetModal(for: window) { response in
                    if response == .OK {
                        // 处理选中的文件
                        for url in panel.urls {
                            // 发送到WebView
                            NotificationCenter.default.post(
                                name: .filesSelected,
                                object: nil,
                                userInfo: ["urls": panel.urls]
                            )
                        }
                    }
                }
            }
        }
    }
}

// MARK: - 应用命令
struct AppCommands: Commands {
    var body: some Commands {
        // 替换默认的文件菜单
        CommandGroup(replacing: .newItem) {
            Button("添加文件...") {
                NotificationCenter.default.post(name: .selectFileRequested, object: nil)
            }
            .keyboardShortcut("o", modifiers: .command)
        }

        // 添加自定义菜单
        CommandMenu("转换") {
            Button("单文件转换") {
                // 切换到单文件转换页面
            }
            .keyboardShortcut("1", modifiers: .command)

            Button("批量转换") {
                // 切换到批量转换页面
            }
            .keyboardShortcut("2", modifiers: .command)

            Divider()

            Button("AI增强") {
                // 切换到AI增强页面
            }
            .keyboardShortcut("3", modifiers: .command)
        }

        // 添加窗口命令
        CommandGroup(after: .windowArrangement) {
            Button("显示/隐藏侧边栏") {
                // 切换侧边栏显示
                NotificationCenter.default.post(name: .toggleSidebar, object: nil)
            }
            .keyboardShortcut("s", modifiers: [.command, .shift])
        }

        // 添加帮助菜单
        CommandGroup(replacing: .help) {
            Button("EBookAI 帮助") {
                if let url = URL(string: "https://ebookai.com/help") {
                    NSWorkspace.shared.open(url)
                }
            }

            Button("报告问题") {
                if let url = URL(string: "https://github.com/ebookai/ebookai/issues") {
                    NSWorkspace.shared.open(url)
                }
            }

            Divider()

            Button("关于 EBookAI") {
                NSApp.orderFrontStandardAboutPanel()
            }
        }
    }
}

// MARK: - 通知名称扩展
extension Notification.Name {
    static let filesSelected = Notification.Name("filesSelected")
    static let toggleSidebar = Notification.Name("toggleSidebar")
}