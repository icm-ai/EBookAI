# EBookAI Native - Build and Development Guide

Comprehensive guide for building, developing, and distributing the pure Swift native macOS application.

## 🏗️ Development Environment Setup

### Prerequisites

**System Requirements:**
- macOS 13.0+ (Ventura)
- Xcode 15.0+
- Swift 5.9+
- Command Line Tools

**Install Dependencies:**
```bash
# Install Xcode Command Line Tools
xcode-select --install

# Verify Swift installation
swift --version

# Install Homebrew (if needed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Project Setup

1. **Clone Repository**
   ```bash
   git clone https://github.com/ebookai/ebookai-native
   cd ebookai-native/swift-native-app
   ```

2. **Resolve Dependencies**
   ```bash
   swift package resolve
   ```

3. **Initial Build**
   ```bash
   swift build
   ```

4. **Run Application**
   ```bash
   swift run
   ```

## 🔨 Build Configurations

### Development Builds

**Debug Build (Default)**
```bash
swift build
# Output: .build/debug/EBookAI
```

**Run in Debug Mode**
```bash
swift run
# Enables debug logging and assertions
```

**Run with Custom Arguments**
```bash
swift run EBookAI --debug --log-level verbose
```

### Release Builds

**Optimized Release Build**
```bash
swift build -c release
# Output: .build/release/EBookAI
```

**Release Build with Optimizations**
```bash
swift build -c release -Xswiftc -O
```

### Build Variants

**Universal Binary (Intel + Apple Silicon)**
```bash
# Build for both architectures
swift build -c release --arch arm64 --arch x86_64
```

**Architecture-Specific Builds**
```bash
# Apple Silicon only
swift build -c release --arch arm64

# Intel only
swift build -c release --arch x86_64
```

## 🧪 Testing

### Unit Tests
```bash
# Run all tests
swift test

# Run specific test target
swift test --filter EBookAITests

# Run with coverage
swift test --enable-code-coverage

# Generate coverage report
xcrun llvm-cov export \
  .build/debug/EBookAIPackageTests.xctest/Contents/MacOS/EBookAIPackageTests \
  -instr-profile .build/debug/codecov/default.profdata \
  -format="text" > coverage.txt
```

### UI Tests
```bash
# Run UI tests
swift test --filter UITests

# Run UI tests with debugging
swift test --filter UITests -v
```

### Performance Tests
```bash
swift test --filter PerformanceTests
```

### Test in Xcode
```bash
# Open project in Xcode
open Package.swift

# Use ⌘+U to run tests in Xcode
```

## 📦 Creating Distribution Builds

### Step 1: Build Release Binary

```bash
# Clean previous builds
swift package clean

# Build optimized release
swift build -c release --arch arm64 --arch x86_64

# Verify binary
file .build/release/EBookAI
# Should show: Mach-O 64-bit executable arm64/x86_64
```

### Step 2: Create App Bundle

```bash
#!/bin/bash
# create_app_bundle.sh

APP_NAME="EBookAI"
VERSION="1.0.0"
BUNDLE_ID="com.ebookai.native"

# Create bundle structure
mkdir -p "${APP_NAME}.app/Contents/MacOS"
mkdir -p "${APP_NAME}.app/Contents/Resources"
mkdir -p "${APP_NAME}.app/Contents/Frameworks"

# Copy executable
cp .build/release/EBookAI "${APP_NAME}.app/Contents/MacOS/"

# Create Info.plist
cat > "${APP_NAME}.app/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>EBookAI</string>
    <key>CFBundleIdentifier</key>
    <string>${BUNDLE_ID}</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>EBookAI Native</string>
    <key>CFBundleVersion</key>
    <string>${VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>${VERSION}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSSupportsAutomaticGraphicsSwitching</key>
    <true/>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeExtensions</key>
            <array>
                <string>epub</string>
                <string>pdf</string>
                <string>txt</string>
                <string>mobi</string>
                <string>azw3</string>
            </array>
            <key>CFBundleTypeName</key>
            <string>E-Book File</string>
            <key>CFBundleTypeRole</key>
            <string>Editor</string>
            <key>LSTypeIsPackage</key>
            <false/>
        </dict>
    </array>
</dict>
</plist>
EOF

# Set executable permissions
chmod +x "${APP_NAME}.app/Contents/MacOS/EBookAI"

echo "App bundle created: ${APP_NAME}.app"
```

### Step 3: Code Signing (Optional but Recommended)

**For Distribution Outside App Store:**
```bash
# Sign with Developer ID
codesign --force --sign "Developer ID Application: Your Name (TEAM_ID)" \
  --options runtime \
  --entitlements entitlements.plist \
  EBookAI.app

# Verify signature
codesign --verify --deep --strict --verbose=2 EBookAI.app
```

**Create entitlements.plist:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.app-sandbox</key>
    <true/>
    <key>com.apple.security.files.user-selected.read-write</key>
    <true/>
    <key>com.apple.security.network.client</key>
    <true/>
</dict>
</plist>
```

### Step 4: Notarization (For Distribution)

```bash
# Create ZIP for notarization
ditto -c -k --keepParent EBookAI.app EBookAI.zip

# Submit for notarization
xcrun notarytool submit EBookAI.zip \
  --apple-id "your-apple-id@example.com" \
  --password "app-specific-password" \
  --team-id "YOUR_TEAM_ID" \
  --wait

# Staple the notarization
xcrun stapler staple EBookAI.app
```

### Step 5: Create DMG

```bash
#!/bin/bash
# create_dmg.sh

APP_NAME="EBookAI"
VERSION="1.0.0"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"

# Create temporary folder
mkdir -p dmg_temp
cp -R "${APP_NAME}.app" dmg_temp/

# Create Applications link
ln -s /Applications dmg_temp/Applications

# Create DMG
hdiutil create -srcfolder dmg_temp \
  -volname "${APP_NAME}" \
  -fs HFS+ \
  -fsargs "-c c=64,a=16,e=16" \
  -format UDBZ \
  -size 100M \
  "${DMG_NAME}"

# Cleanup
rm -rf dmg_temp

echo "DMG created: ${DMG_NAME}"
```

## 🔧 Development Workflow

### Xcode Integration

**Open in Xcode:**
```bash
open Package.swift
```

**Xcode Project Generation:**
```bash
swift package generate-xcodeproj
open EBookAI.xcodeproj
```

### Debugging

**Enable Debug Logging:**
```bash
export LOG_LEVEL=debug
swift run
```

**Use Xcode Debugger:**
1. Open Package.swift in Xcode
2. Set breakpoints in source code
3. Run with ⌘+R
4. Use debugging tools

**Memory Debugging:**
```bash
# Run with AddressSanitizer
swift run -Xswiftc -sanitize=address

# Run with Thread Sanitizer
swift run -Xswiftc -sanitize=thread
```

### Performance Profiling

**Using Instruments:**
1. Build release version
2. Open Instruments
3. Profile the built executable
4. Analyze performance bottlenecks

**Swift Profiling:**
```bash
# Build with profiling
swift build -c release -Xswiftc -profile-generate

# Run to generate profile data
.build/release/EBookAI

# Build optimized with profile data
swift build -c release -Xswiftc -profile-use=default.profdata
```

## 🚀 Continuous Integration

### GitHub Actions Example

```yaml
# .github/workflows/build.yml
name: Build and Test

on: [push, pull_request]

jobs:
  build:
    runs-on: macos-latest

    steps:
    - uses: actions/checkout@v3

    - name: Setup Swift
      uses: swift-actions/setup-swift@v1
      with:
        swift-version: "5.9"

    - name: Build
      run: swift build -c release

    - name: Test
      run: swift test

    - name: Create App Bundle
      run: |
        chmod +x scripts/create_app_bundle.sh
        ./scripts/create_app_bundle.sh

    - name: Upload Artifacts
      uses: actions/upload-artifact@v3
      with:
        name: EBookAI-App
        path: EBookAI.app
```

### Local Build Scripts

**build.sh:**
```bash
#!/bin/bash
set -e

echo "🏗️  Building EBookAI Native..."

# Clean previous builds
swift package clean

# Resolve dependencies
swift package resolve

# Run tests
echo "🧪 Running tests..."
swift test

# Build release
echo "📦 Building release..."
swift build -c release

# Create app bundle
echo "📱 Creating app bundle..."
./scripts/create_app_bundle.sh

# Create DMG
echo "💿 Creating DMG..."
./scripts/create_dmg.sh

echo "✅ Build complete!"
```

## 🔍 Troubleshooting

### Common Build Issues

**Dependency Resolution Errors:**
```bash
# Clear package cache
rm -rf .build
swift package reset
swift package resolve
```

**Architecture Issues:**
```bash
# Check current architecture
uname -m

# Force specific architecture
arch -arm64 swift build
arch -x86_64 swift build
```

**Permission Errors:**
```bash
# Fix permissions
chmod -R 755 .build
sudo xcode-select --reset
```

### Runtime Issues

**App Won't Launch:**
1. Check console logs: `Console.app`
2. Verify code signature: `codesign --verify -v EBookAI.app`
3. Check entitlements: `codesign -d --entitlements - EBookAI.app`

**File Access Issues:**
1. Grant file access permissions in System Preferences
2. Add file access entitlements
3. Test with sandbox disabled (development only)

**AI Service Failures:**
1. Verify API keys in settings
2. Check network connectivity
3. Validate API quotas

### Performance Issues

**Slow Startup:**
1. Profile with Instruments
2. Check for blocking operations in `init()`
3. Use async loading for heavy resources

**Memory Leaks:**
1. Use Xcode Memory Graph Debugger
2. Check for retain cycles in closures
3. Profile with Instruments Leaks tool

**High CPU Usage:**
1. Profile with Instruments CPU tool
2. Check for infinite loops or busy waits
3. Optimize heavy computations

## 📊 Build Metrics

### Target Build Times
- **Debug Build**: < 30 seconds
- **Release Build**: < 2 minutes
- **Tests**: < 1 minute
- **App Bundle Creation**: < 30 seconds

### Distribution Package Sizes
- **App Bundle**: ~15-25 MB
- **DMG**: ~8-15 MB (compressed)
- **Universal Binary**: ~2x single architecture

---

This guide provides comprehensive coverage of the build and development process for the EBookAI Native macOS application. For additional help, refer to the main README or contact the development team.