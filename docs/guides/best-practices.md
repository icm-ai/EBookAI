# 最佳实践指南

本指南提供使用 EBookAI 的最佳实践建议，帮助优化性能、提高可靠性和改善用户体验。

## 目录

- [部署最佳实践](#部署最佳实践)
- [API 使用最佳实践](#api-使用最佳实践)
- [文件管理最佳实践](#文件管理最佳实践)
- [AI 服务最佳实践](#ai-服务最佳实践)
- [性能优化](#性能优化)
- [安全最佳实践](#安全最佳实践)
- [监控和维护](#监控和维护)

---

## 部署最佳实践

### 生产环境配置

#### 1. 使用环境变量管理配置

**推荐做法**：
```bash
# 生产环境 .env
LOG_LEVEL=INFO  # 避免DEBUG级别日志
FILE_MAX_AGE_HOURS=24
CLEANUP_INTERVAL_MINUTES=60

# AI配置
DEEPSEEK_API_KEY=your-production-key
# 不要在.env中硬编码敏感信息，使用密钥管理服务
```

**不推荐**：
```python
# 硬编码在代码中
API_KEY = "sk-xxxxx"  # 危险！
```

#### 2. 资源限制

根据负载设置合理的资源限制：

```yaml
# docker-compose.yml (生产环境)
services:
  ebook-ai:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
    restart: unless-stopped
```

#### 3. 健康检查

配置适当的健康检查：

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

#### 4. 日志管理

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

---

## API 使用最佳实践

### 1. 错误处理

**始终处理错误响应**：

```python
import requests

def convert_file_safe(file_path, target_format):
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(
                'http://localhost:8000/api/convert',
                files={'file': f},
                data={'target_format': target_format},
                timeout=300  # 5分钟超时
            )
        response.raise_for_status()
        return response.json()

    except requests.Timeout:
        print("请求超时，文件可能过大")
        return None
    except requests.HTTPError as e:
        if e.response.status_code == 400:
            print(f"请求错误: {e.response.json()}")
        elif e.response.status_code == 500:
            print("服务器错误，请稍后重试")
        return None
    except Exception as e:
        print(f"未知错误: {e}")
        return None
```

### 2. 使用批量操作

**推荐 - 批量转换**：
```python
# 一次请求处理多个文件
files = [
    ('files', open('book1.epub', 'rb')),
    ('files', open('book2.epub', 'rb')),
    ('files', open('book3.epub', 'rb'))
]

batch = requests.post(
    'http://localhost:8000/api/batch/convert',
    files=files,
    data={'target_format': 'pdf'}
).json()
```

**不推荐 - 循环单个请求**：
```python
# 效率低，服务器压力大
for file in file_list:
    requests.post(
        'http://localhost:8000/api/convert',
        files={'file': open(file, 'rb')},
        data={'target_format': 'pdf'}
    )
```

### 3. 合理的轮询间隔

```python
import time

def wait_for_batch_completion(batch_id, poll_interval=5):
    """
    等待批量任务完成

    Args:
        batch_id: 批量任务ID
        poll_interval: 轮询间隔（秒）
    """
    while True:
        status = requests.get(
            f'http://localhost:8000/api/batch/status/{batch_id}'
        ).json()

        if status['status'] in ['completed', 'failed']:
            return status

        # 避免过于频繁的请求
        time.sleep(poll_interval)

        # 可选：添加超时机制
        # if time.time() - start_time > max_wait_time:
        #     raise TimeoutError("批量任务超时")
```

### 4. 使用连接池

```python
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)

# 使用session发送请求
response = session.post('http://localhost:8000/api/convert', ...)
```

---

## 文件管理最佳实践

### 1. 定期清理

**自动清理**：
依赖内置的自动清理机制（默认24小时）。

**手动清理**：
```bash
# 定期执行（通过cron）
*/6 * * * * curl -X POST http://localhost:8000/api/cleanup/run
```

### 2. 监控磁盘使用

```python
import requests

def check_disk_usage():
    status = requests.get(
        'http://localhost:8000/api/cleanup/status'
    ).json()

    total_mb = (
        status['disk_usage']['uploads']['total_size_mb'] +
        status['disk_usage']['outputs']['total_size_mb']
    )

    # 超过1GB时触发清理
    if total_mb > 1000:
        requests.post('http://localhost:8000/api/cleanup/run')
        print(f"清理完成: 释放 {total_mb}MB")
```

### 3. 文件命名规范

**下载文件时使用明确的命名**：
```python
import os

def download_converted_file(output_file, save_path):
    response = requests.get(
        f'http://localhost:8000/api/download/{output_file}',
        stream=True
    )

    # 使用有意义的文件名
    filename = f"converted_{os.path.basename(save_path)}"

    with open(filename, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
```

### 4. 大文件处理

```python
def convert_large_file(file_path, target_format, chunk_size=10*1024*1024):
    """
    处理大文件（分块上传）
    注意：当前版本不支持分块上传，这是未来的改进方向
    """
    file_size = os.path.getsize(file_path)

    if file_size > 50 * 1024 * 1024:  # 50MB
        print("警告：文件过大，可能导致超时")
        print("建议：使用Calibre预处理或分割文件")
        return None

    # 正常处理
    return convert_file_safe(file_path, target_format)
```

---

## AI 服务最佳实践

### 1. 选择合适的提供商

**按需求选择**：
```python
# 速度优先：Groq
summary = generate_summary(text, provider='groq')

# 质量优先：Claude
summary = generate_summary(text, provider='claude')

# 成本优先：DeepSeek
summary = generate_summary(text, provider='deepseek')
```

### 2. 处理速率限制

```python
import time
from functools import wraps

def with_retry(max_retries=3, backoff_factor=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.HTTPError as e:
                    if e.response.status_code == 429:  # Rate limit
                        if attempt < max_retries - 1:
                            wait_time = backoff_factor ** attempt
                            print(f"速率限制，等待 {wait_time}秒...")
                            time.sleep(wait_time)
                        else:
                            raise
                    else:
                        raise
            return None
        return wrapper
    return decorator

@with_retry(max_retries=3)
def generate_summary(text, provider='deepseek'):
    return requests.post(
        'http://localhost:8000/api/ai/summary',
        json={'text': text, 'provider': provider}
    ).json()
```

### 3. 文本预处理

```python
def preprocess_text(text, max_length=2000):
    """
    预处理文本以优化AI处理
    """
    # 移除多余空白
    text = ' '.join(text.split())

    # 截断至限制长度
    if len(text) > max_length:
        text = text[:max_length]
        # 在句子边界截断
        last_period = text.rfind('。')
        if last_period > max_length * 0.8:
            text = text[:last_period + 1]

    return text
```

### 4. 缓存AI结果

```python
import hashlib
import json

class AICache:
    def __init__(self):
        self.cache = {}

    def get_cache_key(self, text, provider):
        content = f"{text}:{provider}"
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, text, provider):
        key = self.get_cache_key(text, provider)
        return self.cache.get(key)

    def set(self, text, provider, result):
        key = self.get_cache_key(text, provider)
        self.cache[key] = result

    def generate_summary_cached(self, text, provider='deepseek'):
        # 检查缓存
        cached = self.get(text, provider)
        if cached:
            return cached

        # 调用API
        result = generate_summary(text, provider)

        # 保存缓存
        self.set(text, provider, result)
        return result

# 使用
cache = AICache()
summary = cache.generate_summary_cached(text, 'deepseek')
```

---

## 性能优化

### 1. 并发处理

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def batch_convert_concurrent(files, target_format, max_workers=3):
    """
    并发处理多个文件（客户端并发）
    注意：服务端已有并发限制
    """
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(convert_file_safe, f, target_format): f
            for f in files
        }

        for future in as_completed(future_to_file):
            file = future_to_file[future]
            try:
                result = future.result()
                results.append({'file': file, 'result': result})
            except Exception as e:
                results.append({'file': file, 'error': str(e)})

    return results
```

### 2. 异步处理

```python
import asyncio
import aiohttp

async def convert_file_async(session, file_path, target_format):
    """异步文件转换"""
    async with session.post(
        'http://localhost:8000/api/convert',
        data={
            'file': open(file_path, 'rb'),
            'target_format': target_format
        }
    ) as response:
        return await response.json()

async def batch_convert_async(files, target_format):
    """异步批量转换"""
    async with aiohttp.ClientSession() as session:
        tasks = [
            convert_file_async(session, f, target_format)
            for f in files
        ]
        return await asyncio.gather(*tasks)

# 使用
results = asyncio.run(batch_convert_async(files, 'pdf'))
```

### 3. 请求压缩

```python
import gzip
import json

def post_with_compression(url, data):
    """
    发送压缩数据（适用于大型JSON请求）
    """
    compressed_data = gzip.compress(json.dumps(data).encode())

    headers = {
        'Content-Type': 'application/json',
        'Content-Encoding': 'gzip'
    }

    return requests.post(url, data=compressed_data, headers=headers)
```

---

## 安全最佳实践

### 1. API密钥管理

**不要**：
```python
# 硬编码API密钥
API_KEY = "sk-xxxxx"  # 危险！

# 提交到Git
git add .env  # 危险！
```

**应该**：
```python
# 使用环境变量
import os
API_KEY = os.getenv('DEEPSEEK_API_KEY')

# 或使用密钥管理服务
from azure.keyvault.secrets import SecretClient
secret_client = SecretClient(vault_url, credential)
API_KEY = secret_client.get_secret("deepseek-api-key").value
```

**Git忽略敏感文件**：
```gitignore
# .gitignore
.env
.env.local
.env.production
*.key
```

### 2. 输入验证

```python
def validate_file(file_path):
    """验证上传文件"""
    import magic

    # 检查文件存在
    if not os.path.exists(file_path):
        raise ValueError("文件不存在")

    # 检查文件大小
    size = os.path.getsize(file_path)
    if size > 50 * 1024 * 1024:  # 50MB
        raise ValueError("文件过大")

    # 检查文件类型（使用magic number，不只是扩展名）
    mime_type = magic.from_file(file_path, mime=True)
    allowed_types = [
        'application/epub+zip',
        'application/pdf',
        'application/x-mobipocket-ebook',
        'text/plain'
    ]

    if mime_type not in allowed_types:
        raise ValueError(f"不支持的文件类型: {mime_type}")

    return True
```

### 3. 速率限制（客户端）

```python
from time import time, sleep

class RateLimiter:
    def __init__(self, max_calls, period):
        self.max_calls = max_calls
        self.period = period
        self.calls = []

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            now = time()
            self.calls = [c for c in self.calls if now - c < self.period]

            if len(self.calls) >= self.max_calls:
                sleep_time = self.period - (now - self.calls[0])
                sleep(sleep_time)

            self.calls.append(time())
            return func(*args, **kwargs)
        return wrapper

# 限制为每分钟10个请求
@RateLimiter(max_calls=10, period=60)
def call_api(endpoint, data):
    return requests.post(endpoint, json=data)
```

---

## 监控和维护

### 1. 健康检查监控

```python
import requests
import time

def monitor_service(check_interval=60):
    """持续监控服务健康状态"""
    while True:
        try:
            response = requests.get(
                'http://localhost:8000/api/health/detailed',
                timeout=10
            )
            health = response.json()

            if health['status'] != 'healthy':
                print(f"警告：服务状态异常 - {health['status']}")
                # 发送告警（邮件、Slack等）
                send_alert(health)

        except Exception as e:
            print(f"健康检查失败: {e}")
            send_alert({'error': str(e)})

        time.sleep(check_interval)
```

### 2. 日志分析

```bash
# 统计错误日志
docker-compose logs | grep ERROR | wc -l

# 查找特定错误
docker-compose logs | grep "Conversion failed"

# 分析响应时间
docker-compose logs | grep "processing_time" | \
  awk '{print $NF}' | \
  awk '{sum+=$1; count++} END {print "平均:", sum/count}'
```

### 3. 性能指标收集

```python
import time
import statistics

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {
            'conversion_times': [],
            'ai_times': [],
            'errors': 0
        }

    def record_conversion(self, duration):
        self.metrics['conversion_times'].append(duration)

    def record_ai_request(self, duration):
        self.metrics['ai_times'].append(duration)

    def record_error(self):
        self.metrics['errors'] += 1

    def get_stats(self):
        return {
            'avg_conversion_time': statistics.mean(self.metrics['conversion_times'])
                if self.metrics['conversion_times'] else 0,
            'avg_ai_time': statistics.mean(self.metrics['ai_times'])
                if self.metrics['ai_times'] else 0,
            'total_errors': self.metrics['errors'],
            'total_conversions': len(self.metrics['conversion_times'])
        }

# 使用
monitor = PerformanceMonitor()

start = time.time()
result = convert_file('book.epub', 'pdf')
monitor.record_conversion(time.time() - start)

print(monitor.get_stats())
```

### 4. 定期维护任务

```bash
#!/bin/bash
# maintenance.sh - 定期维护脚本

# 清理旧文件
curl -X POST http://localhost:8000/api/cleanup/run

# 清理Docker资源
docker system prune -f

# 备份日志
tar -czf logs-$(date +%Y%m%d).tar.gz logs/

# 重启服务（如需要）
# docker-compose restart
```

**设置定时任务**：
```bash
# crontab -e
0 2 * * * /path/to/maintenance.sh  # 每天凌晨2点执行
```

---

## 总结清单

### 部署前检查
- [ ] 环境变量正确配置
- [ ] 资源限制合理设置
- [ ] 健康检查已配置
- [ ] 日志轮转已启用
- [ ] 备份策略已制定

### 开发最佳实践
- [ ] 错误处理完善
- [ ] 使用批量操作
- [ ] 实施速率限制
- [ ] 缓存AI结果
- [ ] 输入验证严格

### 维护检查
- [ ] 定期检查健康状态
- [ ] 监控磁盘使用
- [ ] 分析性能指标
- [ ] 定期清理资源
- [ ] 及时更新依赖

---

**文档更新日期**: 2024-10-13
**版本**: 1.0.0
