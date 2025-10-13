# EBookAI Native - Pure Swift macOS App

A completely native macOS application for EBookAI, built with 100% Swift and SwiftUI. This implementation provides the ultimate native experience with optimal performance and deep macOS integration.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    SwiftUI Native App                       │
├─────────────────────────────────────────────────────────────┤
│  Views Layer                                                │
│  ├── ContentView (Main Navigation)                          │
│  ├── FileListView (File Management + Drag & Drop)          │
│  ├── ConversionView (Progress Tracking)                    │
│  ├── BatchConversionView (Batch Processing)                │
│  ├── AIToolsView (AI Integration)                          │
│  └── SettingsView (Configuration)                          │
├─────────────────────────────────────────────────────────────┤
│  Services Layer                                             │
│  ├── ConversionService (Core Conversion Logic)             │
│  ├── AIService (OpenAI/Claude/Gemini Integration)          │
│  └── FileManagerService (File Operations)                  │
├─────────────────────────────────────────────────────────────┤
│  Models Layer                                               │
│  ├── FileFormat & FileItem (File Representations)         │
│  ├── ConversionJob & BatchConversionJob (Task Management)  │
│  └── ConversionOptions (Configuration)                     │
├─────────────────────────────────────────────────────────────┤
│  External Dependencies                                      │
│  ├── Alamofire (HTTP Networking)                           │
│  ├── ZIPFoundation (Archive Handling)                      │
│  └── Swift Standard Library                                │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Features

### Core File Conversion
- **8 Format Support**: EPUB, PDF, TXT, MOBI, AZW3, DOCX, HTML, Markdown
- **Native Conversion Engine**: Pure Swift implementation using Core Graphics and Foundation
- **Quality Settings**: Draft, Standard, High, Premium quality levels
- **Advanced Options**: Compression, page size, margins, fonts

### File Management
- **Drag & Drop**: Native macOS drag and drop support
- **Batch Operations**: Select multiple files for batch processing
- **Smart Filtering**: Filter by format, search by name
- **Recent Files**: Persistent recent files with validation

### Real-time Progress Tracking
- **Live Progress**: Real-time conversion progress with estimated time
- **Multiple Jobs**: Track multiple conversions simultaneously
- **Progress Persistence**: Resume tracking after app restart
- **Error Handling**: Comprehensive error reporting and recovery

### AI Integration
- **Multi-Provider Support**: OpenAI, Claude, Gemini
- **Text Enhancement**: Summary generation, writing improvement
- **Translation**: Multi-language translation support
- **Chapter Generation**: AI-powered chapter title generation
- **Text Formatting**: Intelligent text formatting and optimization

### Native macOS Integration
- **Menu Bar**: Full macOS menu bar with keyboard shortcuts
- **System Integration**: Finder integration, file associations
- **Notifications**: Native notification center integration
- **Settings**: Comprehensive preferences with persistence

## 📁 Project Structure

```
swift-native-app/
├── Package.swift                  # Swift Package Manager configuration
├── README.md                      # This file
├── Sources/EBookAI/
│   ├── App.swift                 # App entry point and delegation
│   ├── Models/                   # Data models
│   │   ├── FileFormat.swift      # File format definitions
│   │   ├── FileItem.swift        # File representation
│   │   └── ConversionJob.swift   # Conversion task models
│   ├── Services/                 # Business logic services
│   │   ├── ConversionService.swift    # Core conversion engine
│   │   ├── AIService.swift           # AI integration
│   │   └── FileManagerService.swift  # File operations
│   ├── Views/                    # SwiftUI views
│   │   ├── ContentView.swift     # Main application view
│   │   ├── FileListView.swift    # File management interface
│   │   ├── ConversionView.swift  # Conversion progress tracking
│   │   ├── BatchConversionView.swift # Batch processing
│   │   ├── AIToolsView.swift     # AI tools interface
│   │   └── SettingsView.swift    # Settings and preferences
│   ├── Utils/                    # Utility classes
│   └── Extensions/               # Swift extensions
├── Tests/EBookAITests/           # Unit tests
├── Tests/UITests/                # UI tests
└── Documentation/                # Additional documentation
```

## 🛠️ Development Setup

### Requirements
- **macOS**: 13.0+ (Ventura)
- **Xcode**: 15.0+
- **Swift**: 5.9+

### Quick Start

1. **Clone and Navigate**
   ```bash
   cd swift-native-app
   ```

2. **Build Dependencies**
   ```bash
   swift package resolve
   ```

3. **Run in Development**
   ```bash
   swift run
   ```

4. **Open in Xcode** (Optional)
   ```bash
   open Package.swift
   ```

### Build Configurations

**Development Build**
```bash
swift build
```

**Release Build**
```bash
swift build -c release
```

**Run Tests**
```bash
swift test
```

## 🔧 Configuration

### AI Service Setup

1. **Get API Keys**
   - OpenAI: https://platform.openai.com/api-keys
   - Claude: https://console.anthropic.com/
   - Gemini: https://makersuite.google.com/app/apikey

2. **Configure in App**
   - Open Settings → AI
   - Select provider
   - Enter API key
   - Keys are stored securely in Keychain

### File Format Support

| Source Format | Target Formats | Notes |
|---------------|----------------|-------|
| EPUB | PDF, TXT, HTML, MOBI | Full metadata preservation |
| PDF | EPUB, TXT, HTML | OCR support planned |
| TXT | PDF, EPUB, HTML, MOBI | Smart formatting |
| MOBI | EPUB, PDF, TXT, HTML | DRM-free only |
| AZW3 | EPUB, PDF, TXT, HTML | DRM-free only |
| DOCX | PDF, EPUB, TXT, HTML | Office integration |
| HTML | PDF, EPUB, TXT | Web content processing |
| Markdown | PDF, HTML, EPUB | Developer-friendly |

## 🎯 Core Components

### ConversionService
The heart of the application, responsible for:
- Managing conversion queue with semaphore-based concurrency
- Progress tracking with real-time updates
- Error handling and recovery
- Format-specific converter delegation

**Key Features:**
- **Concurrent Processing**: Up to 3 simultaneous conversions
- **Progress Callbacks**: Real-time progress updates
- **Error Recovery**: Automatic retry mechanisms
- **Memory Management**: Efficient resource cleanup

### AIService
Handles all AI-related functionality:
- Multi-provider API integration (OpenAI, Claude, Gemini)
- Secure API key management
- Request/response handling
- Error handling and rate limiting

**Supported Operations:**
- Text summarization with configurable length
- Writing improvement and enhancement
- Multi-language translation
- Chapter title generation
- Text formatting optimization

### FileManagerService
Manages file operations and metadata:
- File validation and metadata extraction
- Drag & drop handling
- Recent files persistence
- File system integration

**Features:**
- **Smart Validation**: Format detection and validation
- **Metadata Extraction**: Title, author, page count extraction
- **Thumbnail Generation**: Preview generation for supported formats
- **Search & Filter**: Advanced file filtering capabilities

## 🚀 Building for Distribution

### Create App Bundle

1. **Build Release Version**
   ```bash
   swift build -c release
   ```

2. **Create App Bundle**
   ```bash
   mkdir -p EBookAI.app/Contents/MacOS
   mkdir -p EBookAI.app/Contents/Resources

   # Copy executable
   cp .build/release/EBookAI EBookAI.app/Contents/MacOS/

   # Copy resources
   cp -r Sources/EBookAI/Resources/* EBookAI.app/Contents/Resources/
   ```

3. **Create Info.plist**
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>CFBundleExecutable</key>
       <string>EBookAI</string>
       <key>CFBundleIdentifier</key>
       <string>com.ebookai.native</string>
       <key>CFBundleName</key>
       <string>EBookAI</string>
       <key>CFBundleVersion</key>
       <string>1.0.0</string>
       <key>LSMinimumSystemVersion</key>
       <string>13.0</string>
   </dict>
   </plist>
   ```

### Code Signing (Optional)

```bash
# Sign the executable
codesign --sign "Developer ID Application: Your Name" EBookAI.app

# Verify signature
codesign --verify --verbose EBookAI.app
```

### Create DMG

```bash
# Create DMG
hdiutil create -srcfolder EBookAI.app -volname "EBookAI" -format UDZO EBookAI.dmg
```

## 🧪 Testing

### Unit Tests
```bash
swift test --filter EBookAITests
```

### UI Tests
```bash
swift test --filter UITests
```

### Performance Testing
```bash
swift test --filter PerformanceTests
```

## 📊 Performance Characteristics

### Conversion Performance
- **Text to PDF**: ~2MB/second
- **EPUB to PDF**: ~1MB/second
- **Memory Usage**: <100MB for typical files
- **Startup Time**: <2 seconds

### AI Processing
- **Summary Generation**: 2-5 seconds
- **Translation**: 3-8 seconds
- **Chapter Generation**: 5-10 seconds

## 🔍 Troubleshooting

### Common Issues

**Build Failures**
```bash
# Clean build
swift package clean
swift package resolve
swift build
```

**Permission Errors**
- Ensure app has file system access permissions
- Check macOS security settings

**AI Integration Issues**
- Verify API keys are correctly configured
- Check network connectivity
- Validate API quotas and limits

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=debug
swift run
```

## 🤝 Contributing

### Code Style
- Follow Swift API Design Guidelines
- Use SwiftUI best practices
- Include unit tests for new features
- Document public APIs

### Pull Request Process
1. Fork the repository
2. Create feature branch
3. Implement changes with tests
4. Update documentation
5. Submit pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🔗 Related Projects

- **EBookAI Web**: React-based web interface
- **EBookAI Electron**: Cross-platform desktop app
- **EBookAI CLI**: Command-line interface
- **EBookAI API**: Backend services

## 📞 Support

- **Documentation**: https://docs.ebookai.com
- **Issues**: https://github.com/ebookai/ebookai-native/issues
- **Discussions**: https://github.com/ebookai/ebookai-native/discussions
- **Email**: support@ebookai.com

---

**Note**: This is a pure Swift implementation designed for optimal macOS performance. For cross-platform needs, consider the Electron version. For web deployment, use the React web interface.