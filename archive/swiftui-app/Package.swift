// swift-tools-version: 5.7
// Package.swift - Swift包管理配置

import PackageDescription

let package = Package(
    name: "EBookAI",
    platforms: [
        .macOS(.v12) // 支持 macOS 12.0+
    ],
    products: [
        .executable(
            name: "EBookAI",
            targets: ["EBookAI"]
        )
    ],
    dependencies: [
        // 添加外部依赖（如果需要）
        // .package(url: "https://github.com/apple/swift-log.git", from: "1.0.0"),
    ],
    targets: [
        .executableTarget(
            name: "EBookAI",
            dependencies: [],
            path: "Sources",
            resources: [
                .process("Resources")
            ]
        ),
        .testTarget(
            name: "EBookAITests",
            dependencies: ["EBookAI"],
            path: "Tests"
        )
    ]
)