//
//  WebViewRepresentable.swift
//  EBookAI
//
//  WebKit集成和JavaScript Bridge通信
//

import SwiftUI
import WebKit

struct WebViewRepresentable: NSViewRepresentable {
    let url: URL
    let coordinator: WebViewCoordinator

    func makeNSView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()

        // 配置JavaScript Bridge
        let userContentController = WKUserContentController()
        userContentController.add(coordinator, name: "nativeInterface")
        configuration.userContentController = userContentController

        // 配置WebView设置
        configuration.preferences.javaScriptEnabled = true
        configuration.allowsAirPlayForMediaPlayback = false

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = coordinator
        webView.uiDelegate = coordinator

        // 允许开发者工具（仅在调试模式）
        #if DEBUG
        if #available(macOS 13.3, *) {
            webView.isInspectable = true
        }
        #endif

        coordinator.webView = webView
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        // 如果URL改变，重新加载
        if webView.url != url {
            let request = URLRequest(url: url)
            webView.load(request)
        }
    }

    func makeCoordinator() -> WebViewCoordinator {
        return coordinator
    }
}

class WebViewCoordinator: NSObject, ObservableObject {
    weak var webView: WKWebView?

    // 回调函数
    var onProgressUpdate: (([String: Any]) -> Void)?
    var onProgressComplete: (() -> Void)?
    var onError: ((String) -> Void)?
    var onNavigationFinished: (() -> Void)?

    // 导航到指定URL
    func navigate(to urlString: String) {
        guard let url = URL(string: urlString) else { return }
        let request = URLRequest(url: url)
        webView?.load(request)
    }

    // 重新加载当前页面
    func reload() {
        webView?.reload()
    }

    // 发送消息到WebView
    func sendMessage(_ type: String, data: Any) {
        let message = [
            "type": type,
            "data": data
        ]

        guard let jsonData = try? JSONSerialization.data(withJSONObject: message),
              let jsonString = String(data: jsonData, encoding: .utf8) else {
            return
        }

        let script = "window.receiveNativeMessage && window.receiveNativeMessage(\(jsonString));"
        webView?.evaluateJavaScript(script) { result, error in
            if let error = error {
                print("JavaScript execution error: \(error)")
            }
        }
    }

    // 执行JavaScript代码
    func evaluateJavaScript(_ script: String, completion: ((Any?, Error?) -> Void)? = nil) {
        webView?.evaluateJavaScript(script, completionHandler: completion)
    }
}

// MARK: - WKNavigationDelegate
extension WebViewCoordinator: WKNavigationDelegate {
    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        print("开始加载页面")
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        print("页面加载完成")
        onNavigationFinished?()

        // 注入JavaScript接口
        let script = """
        window.nativeInterface = {
            selectFile: function() {
                window.webkit.messageHandlers.nativeInterface.postMessage({
                    type: 'selectFile'
                });
            },

            reportProgress: function(progress) {
                window.webkit.messageHandlers.nativeInterface.postMessage({
                    type: 'progress',
                    data: progress
                });
            },

            reportError: function(error) {
                window.webkit.messageHandlers.nativeInterface.postMessage({
                    type: 'error',
                    data: error
                });
            },

            reportComplete: function() {
                window.webkit.messageHandlers.nativeInterface.postMessage({
                    type: 'complete'
                });
            }
        };

        // 通知页面原生接口已准备就绪
        if (window.onNativeInterfaceReady) {
            window.onNativeInterfaceReady();
        }
        """

        webView.evaluateJavaScript(script) { result, error in
            if let error = error {
                print("JavaScript injection error: \(error)")
            }
        }
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        print("页面加载失败: \(error.localizedDescription)")
        onError?("页面加载失败: \(error.localizedDescription)")
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        print("页面加载失败: \(error.localizedDescription)")
        onError?("页面加载失败: \(error.localizedDescription)")
    }
}

// MARK: - WKUIDelegate
extension WebViewCoordinator: WKUIDelegate {
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        // 处理JavaScript alert
        let alert = NSAlert()
        alert.messageText = "网页消息"
        alert.informativeText = message
        alert.alertStyle = .informational
        alert.addButton(withTitle: "确定")
        alert.runModal()
        completionHandler()
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        // 处理JavaScript confirm
        let alert = NSAlert()
        alert.messageText = "确认"
        alert.informativeText = message
        alert.alertStyle = .warning
        alert.addButton(withTitle: "确定")
        alert.addButton(withTitle: "取消")
        let response = alert.runModal()
        completionHandler(response == .alertFirstButtonReturn)
    }
}

// MARK: - WKScriptMessageHandler
extension WebViewCoordinator: WKScriptMessageHandler {
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any],
              let type = body["type"] as? String else {
            return
        }

        switch type {
        case "progress":
            if let data = body["data"] as? [String: Any] {
                onProgressUpdate?(data)
            }

        case "complete":
            onProgressComplete?()

        case "error":
            if let errorMessage = body["data"] as? String {
                onError?(errorMessage)
            }

        case "selectFile":
            // 触发原生文件选择
            NotificationCenter.default.post(name: .selectFileRequested, object: nil)

        default:
            print("未知的消息类型: \(type)")
        }
    }
}

// MARK: - Notification Names
extension Notification.Name {
    static let selectFileRequested = Notification.Name("selectFileRequested")
}