// swift-tools-version: 5.9
// Pure Swift Native EBookAI macOS Application

import PackageDescription

let package = Package(
    name: "EBookAI",
    platforms: [
        .macOS(.v13) // macOS 13.0+ for latest SwiftUI features
    ],
    products: [
        .executable(
            name: "EBookAI",
            targets: ["EBookAI"]
        )
    ],
    dependencies: [
        // HTTP networking
        .package(url: "https://github.com/Alamofire/Alamofire.git", from: "5.8.0"),

        // JSON handling
        .package(url: "https://github.com/Flight-School/AnyCodable.git", from: "0.6.0"),

        // File format handling
        .package(url: "https://github.com/weichsel/ZIPFoundation.git", from: "0.9.0"),

        // Async operations
        .package(url: "https://github.com/apple/swift-async-algorithms.git", from: "1.0.0"),

        // Logging
        .package(url: "https://github.com/apple/swift-log.git", from: "1.5.0"),

        // Command line processing for embedded tools
        .package(url: "https://github.com/apple/swift-argument-parser.git", from: "1.3.0")
    ],
    targets: [
        .executableTarget(
            name: "EBookAI",
            dependencies: [
                "Alamofire",
                "AnyCodable",
                "ZIPFoundation",
                .product(name: "AsyncAlgorithms", package: "swift-async-algorithms"),
                .product(name: "Logging", package: "swift-log"),
                .product(name: "ArgumentParser", package: "swift-argument-parser")
            ],
            path: "Sources/EBookAI",
            resources: [
                .process("Resources")
            ]
        ),
        .testTarget(
            name: "EBookAITests",
            dependencies: ["EBookAI"],
            path: "Tests/EBookAITests"
        )
    ]
)