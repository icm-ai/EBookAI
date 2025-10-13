# EBookAI 应用资源

这个目录包含 macOS 应用的图标和其他资源文件。

## 🎨 需要的资源文件

### 1. 应用图标 (icon.icns)

创建一个 1024x1024 像素的应用图标，包含以下尺寸：

- 16x16 (icon_16x16.png)
- 32x32 (icon_32x32.png)
- 64x64 (icon_64x64.png)
- 128x128 (icon_128x128.png)
- 256x256 (icon_256x256.png)
- 512x512 (icon_512x512.png)
- 1024x1024 (icon_1024x1024.png)

### 图标设计建议

- **主题**：电子书、人工智能、转换
- **颜色**：现代、专业的配色方案
- **风格**：符合 macOS 设计规范
- **元素**：可能包含书本、齿轮、魔法棒等象征性图标

### 创建 ICNS 文件

```bash
# 使用 iconutil 创建 .icns 文件
mkdir MyIcon.iconset
cp icon_16x16.png MyIcon.iconset/
cp icon_32x32.png MyIcon.iconset/
cp icon_64x64.png MyIcon.iconset/
cp icon_128x128.png MyIcon.iconset/
cp icon_256x256.png MyIcon.iconset/
cp icon_512x512.png MyIcon.iconset/
cp icon_1024x1024.png MyIcon.iconset/

iconutil -c icns MyIcon.iconset
mv MyIcon.icns icon.icns
```

### 2. DMG 背景图片 (dmg-background.png)

- **尺寸**：540x380 像素
- **格式**：PNG
- **内容**：品牌背景，突出 EBookAI 主题
- **元素**：应用图标、产品名称、简洁的设计

### 3. 临时图标创建

如果你现在没有专业设计的图标，可以创建一个简单的临时图标：

```bash
# 使用 SF Symbols 创建临时图标（需要 Xcode）
# 或者使用在线图标生成器：
# - https://www.canva.com/
# - https://www.figma.com/
# - https://icon.kitchen/
```

## 🛠 快速设置

### 创建基础图标

1. 打开 **预览** 应用
2. 创建新文档，设置为 1024x1024 像素
3. 添加文字 "E" 或 "📚" 作为临时图标
4. 导出为 PNG
5. 使用上面的方法创建 ICNS 文件

### 创建 DMG 背景

1. 创建 540x380 像素的图片
2. 添加渐变背景
3. 居中放置应用图标
4. 添加 "EBookAI" 文字
5. 保存为 `dmg-background.png`

## 📝 注意事项

- 确保图标在不同尺寸下都清晰可见
- 遵循 Apple 的设计指南
- 使用高质量的图像避免模糊
- 测试图标在 Dock、Finder 等场景下的显示效果

## 🎯 推荐工具

- **设计工具**：Sketch, Figma, Adobe Illustrator
- **图标生成**：Icon.Kitchen, AppIconGenerator
- **在线编辑**：Canva, Pixlr
- **格式转换**：ImageOptim, TinyPNG

完成资源文件准备后，运行构建脚本即可生成包含正确图标的 macOS 应用程序。