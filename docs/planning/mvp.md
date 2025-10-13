# EBookAI - MVP开发大纲

## 项目概述

### 项目名称

EBookAI

### 项目定位

极简的AI增强电子书处理平台，专注于EPUB与PDF格式转换和基础AI文本处理。

### 核心价值

- 快速可靠的EPUB/PDF格式转换
- 基础AI文本处理（摘要生成）
- 简洁直观的Web界面
- 最小化技术复杂度

## 技术架构

### 整体架构

```
React前端 → FastAPI后端 → 本地文件系统 + AI服务
```

### 核心技术栈

- **后端**: Python 3.11+, FastAPI
- **前端**: React 18
- **格式转换**: Calibre
- **AI集成**: OpenAI API
- **存储**: 本地文件系统

## 核心功能模块

### 1. 格式转换引擎

- **支持格式**: EPUB ↔ PDF
- **核心组件**:
  - `converter.py` - 转换逻辑
  - Calibre集成
- **优先级**: P0

### 2. AI文本处理
- **功能**: 文本摘要生成
- **核心组件**:
  - `ai_service.py` - OpenAI集成
- **优先级**: P1

### 3. Web界面

- **功能**: 文件上传、转换、下载
- **核心组件**: React单页应用
- **优先级**: P0

## MVP功能清单

### 必需功能 (P0)

- [ ] EPUB转PDF
- [ ] PDF转EPUB
- [ ] 文件上传界面
- [ ] 转换进度显示
- [ ] 文件下载

### 增强功能 (P1)

- [ ] 文本摘要生成
- [ ] 转换参数配置
- [ ] 文件预览

## 项目结构

```
ebook-ai/
├── backend/
│   ├── main.py                    # FastAPI应用入口
│   ├── api/
│   │   ├── __init__.py
│   │   ├── conversion.py          # 转换API
│   │   └── ai.py                  # AI处理API
│   ├── services/
│   │   ├── __init__.py
│   │   ├── converter.py           # 格式转换服务
│   │   └── ai_service.py          # AI服务
│   ├── utils/
│   │   ├── __init__.py
│   │   └── file_handler.py        # 文件处理工具
│   └── config.py                  # 配置管理
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   ├── FileUpload.js
│   │   │   ├── ConversionPanel.js
│   │   │   └── ProgressBar.js
│   │   ├── services/
│   │   │   └── api.js
│   │   ├── App.js
│   │   └── index.js
│   └── package.json
├── uploads/                       # 上传文件临时存储
├── outputs/                       # 转换结果存储
├── requirements.txt
├── .env.example
└── README.md
```

## API设计

### 转换API

```
POST /api/convert                  # 文件转换
GET  /api/convert/{task_id}        # 转换状态
GET  /api/download/{file_id}       # 文件下载
```

### AI处理API

```
POST /api/ai/summary              # 生成摘要
```

## 开发计划 (4周)

### 第1周：基础架构

- [ ] FastAPI项目初始化
- [ ] React前端搭建
- [ ] 基础API路由设计
- [ ] 文件上传下载功能

### 第2周：转换功能

- [ ] Calibre集成
- [ ] EPUB转PDF功能
- [ ] PDF转EPUB功能
- [ ] 错误处理机制

### 第3周：AI集成

- [ ] OpenAI API集成
- [ ] 文本提取和处理
- [ ] 摘要生成功能
- [ ] 前端AI功能界面

### 第4周：完善优化

- [ ] 用户体验优化
- [ ] 错误处理完善
- [ ] 性能优化
- [ ] 基础测试

## 环境配置

### 开发环境启动

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# 前端
cd frontend
npm install
npm start
```

### 环境变量

```env
OPENAI_API_KEY=your_openai_key
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs
```

## 依赖项

### 后端依赖

```txt
fastapi
uvicorn
python-multipart
openai
calibre
```

### 前端依赖

```json
{
  "react": "^18.0.0",
  "axios": "^1.0.0"
}
```

## 质量控制

### 代码规范

- 使用Black格式化代码
- 基础单元测试覆盖
- API文档自动生成

### 部署方式

- 开发阶段：本地运行
- 生产环境：可选Docker容器化

## 扩展路径

完成MVP后的潜在扩展方向：

1. 更多格式支持 (mobi, TXT等)
2. 高级AI功能 (翻译, 校对)
3. 用户系统和文件管理
4. 批量处理功能
5. 云存储集成

## 风险控制

### 技术风险

- Calibre依赖稳定性
- OpenAI API限制

### 应对措施

- 充分测试转换质量
- 实现API错误重试机制
- 监控系统资源使用
