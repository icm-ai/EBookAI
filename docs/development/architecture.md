# 架构设计文档

本文档描述 EBookAI 的整体架构设计、核心组件和技术决策。

## 目录

- [系统概览](#系统概览)
- [架构层次](#架构层次)
- [核心组件](#核心组件)
- [数据流](#数据流)
- [技术栈](#技术栈)
- [设计决策](#设计决策)
- [扩展性考虑](#扩展性考虑)

---

## 系统概览

EBookAI 是一个基于微服务思想的电子书处理平台，主要功能包括格式转换、AI文本处理和批量操作。

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                         用户层                               │
│  ┌──────────┐  ┌──────────┐  ┌─────────────┐  ┌──────────┐ │
│  │ Web UI   │  │ CLI Tool │  │   SDK/API   │  │  cURL    │ │
│  └─────┬────┘  └─────┬────┘  └──────┬──────┘  └────┬─────┘ │
└────────┼─────────────┼──────────────┼───────────────┼───────┘
         │             │              │               │
         └─────────────┴──────────────┴───────────────┘
                             │
        ┌────────────────────┴────────────────────┐
        │           API Gateway (FastAPI)          │
        │          http://localhost:8000           │
        └────────────────────┬────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
    ┌────▼────┐         ┌───▼────┐        ┌────▼────┐
    │  转换    │         │   AI   │        │  批量   │
    │  服务    │         │  服务  │        │  服务   │
    └────┬────┘         └───┬────┘        └────┬────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
    ┌────▼────┐         ┌───▼────┐        ┌────▼────┐
    │ Calibre │         │  外部   │        │  文件   │
    │ Engine  │         │AI API  │        │  系统   │
    └─────────┘         └────────┘        └─────────┘
```

---

## 架构层次

### 1. 展示层（Presentation Layer）

**职责**：
- 接收用户请求
- 返回响应
- API 文档生成

**组件**：
- FastAPI Router
- Swagger UI / ReDoc
- WebSocket Handler

**特点**：
- RESTful API 设计
- 自动生成 OpenAPI 规范
- 实时进度推送（WebSocket）

### 2. 业务逻辑层（Business Logic Layer）

**职责**：
- 核心业务逻辑
- 服务编排
- 数据验证

**组件**：
- ConversionService
- AIService
- BatchConversionService
- FileCleanupManager

**特点**：
- 服务解耦
- 可测试性高
- 错误处理统一

### 3. 数据层（Data Layer）

**职责**：
- 文件存储
- 状态管理
- 缓存

**组件**：
- 文件系统（uploads/, outputs/）
- 内存状态（BatchJob, Progress）
- 日志存储

**特点**：
- 无数据库依赖（MVP版本）
- 文件即数据
- 自动清理机制

### 4. 基础设施层（Infrastructure Layer）

**职责**：
- 日志记录
- 监控
- 配置管理

**组件**：
- Logging System
- Health Checks
- Configuration Manager

---

## 核心组件

### 1. API Gateway (FastAPI)

**文件**: `backend/src/main.py`

**职责**：
- 路由管理
- 中间件
- 生命周期管理

**关键代码**：
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    cleanup_manager = get_cleanup_manager()
    cleanup_manager.start()

    yield

    # 关闭时清理
    await cleanup_manager.stop()

app = FastAPI(lifespan=lifespan)
```

**特点**：
- 自动API文档
- 请求验证
- 异步支持

---

### 2. ConversionService

**文件**: `backend/src/services/conversion_service.py`

**职责**：
- 文件格式转换
- Calibre集成
- 进度追踪

**流程**：
```
用户上传 → 验证格式 → 调用Calibre → 生成输出 → 返回结果
```

**关键方法**：
- `convert_file(input_path, target_format)`: 转换文件
- `get_supported_formats()`: 获取支持的格式
- `validate_format(format)`: 验证格式

**设计模式**：
- Strategy Pattern (格式转换策略)
- Template Method (转换流程模板)

---

### 3. AIService

**文件**: `backend/src/services/ai_service.py`

**职责**：
- AI文本处理
- 多提供商支持
- 错误处理和重试

**架构**：
```python
AIService
├── generate_summary()
├── enhance_text()
└── batch_process_texts()
    ├── _call_openai_compatible_api()
    └── _call_anthropic_api()
```

**提供商适配**：
```python
# OpenAI兼容
providers = ['deepseek', 'openai', 'moonshot', 'groq']

# Anthropic兼容
providers = ['claude']
```

**设计模式**：
- Adapter Pattern (API适配)
- Factory Pattern (提供商工厂)

---

### 4. BatchConversionService

**文件**: `backend/src/services/batch_conversion_service.py`

**职责**：
- 批量任务管理
- 并发控制
- 状态追踪

**数据结构**：
```python
@dataclass
class BatchTask:
    file_path: str
    target_format: str
    task_id: str
    status: str  # pending/processing/completed/failed
    output_file: str
    error_message: str

@dataclass
class BatchJob:
    batch_id: str
    tasks: List[BatchTask]
    total_files: int
    completed_files: int
    failed_files: int
    status: str
    created_at: float
    completed_at: float
```

**并发控制**：
```python
# 使用信号量限制并发数
semaphore = asyncio.Semaphore(3)  # 最多3个并发

async def process_task(task):
    async with semaphore:
        await convert_file(task)
```

**设计模式**：
- Observer Pattern (任务状态观察)
- Composite Pattern (批量任务组合)

---

### 5. FileCleanupManager

**文件**: `backend/src/utils/file_cleanup.py`

**职责**：
- 自动文件清理
- 磁盘监控
- 后台任务管理

**清理策略**：
```python
# 基于时间的清理
max_age_hours = 24  # 24小时后删除

# 定期清理
cleanup_interval_minutes = 60  # 每小时清理一次
```

**实现**：
```python
class FileCleanupManager:
    def start(self):
        """启动后台清理任务"""
        asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        """后台清理循环"""
        while self.running:
            await self.cleanup_old_files()
            await asyncio.sleep(self.cleanup_interval * 60)
```

**设计模式**：
- Singleton Pattern (全局管理器)
- Background Worker Pattern (后台任务)

---

## 数据流

### 单文件转换流程

```
1. 用户上传文件
   POST /api/convert
   file=book.epub
   target_format=pdf

2. API层接收请求
   ↓ 验证参数
   ↓ 保存上传文件到 uploads/

3. ConversionService处理
   ↓ 检查格式支持
   ↓ 调用Calibre
   ↓ ebook-convert input.epub output.pdf

4. 生成输出文件
   ↓ 保存到 outputs/
   ↓ 记录转换日志

5. 返回结果
   {
     "output_file": "converted_xxx.pdf",
     "status": "completed"
   }

6. 用户下载
   GET /api/download/converted_xxx.pdf
```

### 批量转换流程

```
1. 创建批量任务
   POST /api/batch/convert
   files=[book1.epub, book2.epub, book3.epub]
   target_format=pdf

2. BatchConversionService
   ↓ 生成batch_id
   ↓ 创建多个BatchTask
   ↓ 存储到active_batches{}

3. 异步处理任务
   ↓ 并发处理（最多3个）
   ↓ 每个任务调用ConversionService
   ↓ 更新任务状态

4. 状态查询
   GET /api/batch/status/{batch_id}
   返回实时进度

5. 完成后清理
   POST /api/batch/cleanup
```

### AI处理流程

```
1. 用户请求摘要
   POST /api/ai/summary
   {
     "text": "长文本...",
     "provider": "deepseek"
   }

2. AIService处理
   ↓ 文本预处理（截断至2000字符）
   ↓ 构建prompt
   ↓ 选择API类型（openai/anthropic）

3. 调用外部API
   ↓ deepseek/openai/claude API
   ↓ 处理响应
   ↓ 提取token使用信息

4. 返回结果
   {
     "summary": "摘要内容",
     "processing_time": 1.23,
     "token_usage": {...}
   }
```

---

## 技术栈

### 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 主要开发语言 |
| FastAPI | 0.100+ | Web框架 |
| Pydantic | 2.0+ | 数据验证 |
| httpx | 0.24+ | 异步HTTP客户端 |
| Calibre | 6.0+ | 电子书转换引擎 |

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18 | UI框架 |
| TypeScript | 4.9+ | 类型安全 |
| Axios | 1.4+ | HTTP客户端 |
| WebSocket | - | 实时通信 |

### 基础设施

| 技术 | 版本 | 用途 |
|------|------|------|
| Docker | 20.10+ | 容器化 |
| Docker Compose | 2.0+ | 多容器编排 |
| GitHub Actions | - | CI/CD |

---

## 设计决策

### 1. 无数据库设计

**决策**: MVP版本不使用数据库

**理由**：
- 简化部署
- 降低复杂度
- 适合工具类应用
- 文件即数据

**权衡**：
- ✅ 部署简单
- ✅ 无需维护数据库
- ❌ 重启后批量任务丢失
- ❌ 无法持久化历史记录

**未来改进**：
- v1.1: 添加可选的SQLite支持
- v2.0: 支持PostgreSQL

### 2. 同步vs异步

**决策**: 混合使用同步和异步

**理由**：
- 文件转换: 同步（Calibre是同步的）
- AI请求: 异步（网络IO密集）
- 批量处理: 异步（并发控制）

**实现**：
```python
# 同步转换
def convert_file(input_path, target_format):
    subprocess.run(['ebook-convert', ...])

# 异步包装
async def convert_file_async(input_path, target_format):
    return await asyncio.to_thread(convert_file, input_path, target_format)
```

### 3. 文件清理策略

**决策**: 基于时间的自动清理

**配置**：
```python
MAX_AGE_HOURS = 24  # 默认24小时
CLEANUP_INTERVAL = 60  # 每小时检查
```

**理由**：
- 防止磁盘空间耗尽
- 用户可以在24小时内下载
- 定期清理减少手动维护

### 4. AI提供商架构

**决策**: 统一接口 + 适配器模式

**设计**：
```python
class AIService:
    async def generate_summary(text, provider):
        config = get_provider_config(provider)

        if config['api_type'] == 'openai':
            return await self._call_openai_api(...)
        elif config['api_type'] == 'anthropic':
            return await self._call_anthropic_api(...)
```

**优势**：
- 轻松添加新提供商
- 统一的错误处理
- 用户可选择提供商

---

## 扩展性考虑

### 水平扩展

**当前限制**：
- 单实例部署
- 内存状态存储
- 本地文件系统

**扩展方案**：

1. **使用Redis进行状态共享**：
```python
# 替换内存存储
self.active_batches = {}  # 当前

# 使用Redis
import redis
r = redis.Redis()
r.set(f"batch:{batch_id}", json.dumps(batch))
```

2. **使用对象存储**：
```python
# 替换本地文件系统
uploads_dir = "./uploads"  # 当前

# 使用MinIO/S3
from minio import Minio
client = Minio('minio:9000')
client.put_object('uploads', filename, file_data)
```

3. **负载均衡**：
```yaml
# docker-compose.yml
services:
  ebook-ai:
    deploy:
      replicas: 3  # 多实例

  nginx:
    image: nginx
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
```

### 垂直扩展

**资源优化**：
```yaml
# 增加单实例资源
deploy:
  resources:
    limits:
      cpus: '4'      # 从2增加到4
      memory: 8G     # 从4G增加到8G
```

### 功能扩展

**插件架构**（未来版本）：
```python
class ConversionPlugin:
    def convert(self, input_path, output_path):
        raise NotImplementedError

# 注册插件
register_plugin('custom_format', CustomFormatPlugin())
```

---

## 性能特征

### 转换性能

| 文件大小 | 格式 | 预计时间 |
|---------|------|----------|
| 1MB | EPUB→PDF | 5-10秒 |
| 5MB | EPUB→PDF | 15-30秒 |
| 10MB | PDF→EPUB | 30-60秒 |

### AI性能

| 提供商 | 平均响应时间 | Token/秒 |
|--------|-------------|----------|
| Groq | 0.5-1秒 | 300+ |
| DeepSeek | 1-2秒 | 100+ |
| Claude | 2-3秒 | 80+ |

### 并发能力

- 单实例并发转换: 3个
- 理论并发AI请求: 无限（受API限制）
- WebSocket连接: 100+

---

## 安全性

### 当前实现

1. **输入验证**:
   - 文件格式检查
   - 文件大小限制
   - 参数类型验证

2. **资源限制**:
   - 文件大小: 50MB
   - 并发转换: 3个
   - API超时: 5分钟

3. **自动清理**:
   - 24小时自动删除
   - 防止磁盘填满

### 未来增强

1. **认证授权** (v1.1):
   - JWT Token
   - API Key
   - 用户配额

2. **加密** (v2.0):
   - HTTPS强制
   - 文件加密存储
   - 敏感数据脱敏

3. **审计日志** (v2.0):
   - 操作记录
   - 访问日志
   - 异常追踪

---

## 监控和可观测性

### 健康检查

```python
# 多层次健康检查
/api/health            # 基础检查
/api/health/detailed   # 组件检查
/api/health/readiness  # K8s就绪探针
/api/health/liveness   # K8s存活探针
```

### 日志

```python
# 结构化日志
logger.info(
    "Conversion completed",
    extra={
        "task_id": task_id,
        "format": target_format,
        "duration": duration
    }
)
```

### 指标

```python
# 业务指标
/api/health/metrics
{
  "batch_conversion": {
    "active_batches": 3,
    "total_processed": 150
  },
  "ai_service": {
    "total_requests": 1000,
    "success_rate": 98.5
  }
}
```

---

## 总结

EBookAI采用简洁的架构设计，重点关注：

1. **简单性**: 无数据库，易于部署
2. **可扩展性**: 模块化设计，便于扩展
3. **可维护性**: 清晰的分层，完善的测试
4. **性能**: 异步处理，并发控制
5. **可靠性**: 错误处理，自动清理

这个架构适合当前的MVP阶段，同时为未来的增强预留了扩展空间。

---

**文档更新日期**: 2024-10-13
**架构版本**: v1.0.0
