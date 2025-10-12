# 常见问题 (FAQ)

## 目录

- [一般问题](#一般问题)
- [安装和部署](#安装和部署)
- [格式转换](#格式转换)
- [AI 功能](#ai-功能)
- [性能和资源](#性能和资源)
- [错误和故障](#错误和故障)

## 一般问题

### EBookAI 是什么？

EBookAI 是一个开源的电子书处理工具，支持多种格式转换和 AI 增强功能。可以作为 Web 应用使用，也可以通过 Docker 自行部署。

### 是否需要付费？

项目本身完全免费开源（MIT 许可证）。但如果使用 AI 功能，需要自行购买 AI 服务商的 API 密钥。

### 是否需要联网使用？

格式转换功能不需要联网。AI 功能需要联网访问 AI 服务商 API。

### 数据是否安全？

所有文件都在本地处理，不会上传到任何第三方服务器（除非使用 AI 功能时会将文本发送给 AI 服务商）。临时文件会定期自动清理。

### 支持哪些操作系统？

支持 Linux、macOS 和 Windows。推荐使用 Docker 部署以获得最佳兼容性。

## 安装和部署

### Docker 部署时一直卡在下载？

可能是网络问题。尝试：
1. 使用镜像加速器
2. 手动拉取基础镜像：`docker pull debian:12-slim`
3. 检查防火墙设置

### 如何修改服务端口？

编辑 `docker-compose.yml`：
```yaml
ports:
  - "9000:8000"  # 将 8000 改为您想要的端口
```

### 内存不足怎么办？

最低需要 2GB 内存。如果遇到内存问题：
1. 关闭其他应用程序
2. 增加系统内存
3. 限制 Docker 内存使用
4. 避免同时处理大文件

### 如何升级到最新版本？

Docker 部署：
```bash
git pull
docker-compose build --no-cache
docker-compose up -d
```

手动部署：
```bash
git pull
pip install -r requirements.txt --upgrade
```

## 格式转换

### 支持哪些格式转换？

输入格式：EPUB、PDF、MOBI、AZW3、TXT
输出格式：EPUB、PDF、MOBI、AZW3、TXT

不是所有格式组合都支持，具体请查看 README。

### 转换失败怎么办？

常见原因：
1. **文件损坏**：尝试用其他工具打开文件验证
2. **格式不支持**：检查是否为支持的格式
3. **文件过大**：检查文件大小限制（默认 50MB）
4. **Calibre 未安装**：手动部署需要安装 Calibre

### PDF 转 EPUB 效果不好？

PDF 转其他格式质量取决于原文件：
- **文字版 PDF**：转换效果较好
- **扫描版 PDF**：效果较差，建议先进行 OCR
- **复杂排版**：可能丢失格式

### 转换速度慢？

影响因素：
- 文件大小
- 文件复杂度
- 系统性能
- 磁盘读写速度

优化方法：
- 使用 SSD 存储临时文件
- 增加系统资源
- 避免同时转换多个大文件

### 中文显示乱码？

确保系统安装了中文字体：
```bash
# Ubuntu/Debian
sudo apt-get install fonts-noto-cjk fonts-wqy-zenhei

# macOS
brew install font-noto-sans-cjk
```

### 如何批量转换文件？

Web 界面支持批量上传和转换：
1. 选择多个文件上传
2. 选择目标格式
3. 等待批量处理完成

或使用 API 进行批量处理。

## AI 功能

### AI 功能是可选的吗？

是的。不配置 AI API 密钥也可以使用所有格式转换功能。

### 支持哪些 AI 服务商？

- OpenAI 兼容：OpenAI、DeepSeek、Moonshot、Groq 等
- Anthropic 兼容：Claude

系统会自动发现配置的 API 密钥。

### 推荐哪个 AI 服务商？

- **DeepSeek**：性价比高，中英文效果好
- **OpenAI**：功能最完善，但价格较高
- **Claude**：长文本处理能力强

### AI API 密钥在哪里获取？

- OpenAI: https://platform.openai.com/api-keys
- DeepSeek: https://platform.deepseek.com
- Claude: https://console.anthropic.com

### AI 功能不可用？

检查：
1. **API 密钥是否正确**：在 `.env` 文件中配置
2. **网络连接**：某些地区需要代理
3. **API 配额**：检查是否用完配额
4. **服务商状态**：访问服务商官网检查状态

### 如何设置代理？

在 `.env` 文件中配置：
```bash
HTTP_PROXY=http://proxy.example.com:8080
HTTPS_PROXY=http://proxy.example.com:8080
```

### AI 处理很慢？

可能原因：
- 网络延迟
- AI 服务商负载高
- 文本过长

建议：
- 分段处理长文本
- 选择响应快的服务商（如 Groq）
- 检查网络连接

## 性能和资源

### 磁盘空间不够？

1. **手动清理**：
```bash
curl -X POST http://localhost:8000/api/cleanup/run
```

2. **调整清理策略**：
在 `.env` 中修改：
```bash
FILE_CLEANUP_MAX_AGE_HOURS=12  # 改为 12 小时
```

3. **查看磁盘使用**：
```bash
curl http://localhost:8000/api/cleanup/status
```

### 如何查看磁盘使用情况？

访问：http://localhost:8000/api/cleanup/status

或使用命令：
```bash
du -sh uploads outputs
```

### 临时文件多久会被清理？

默认 24 小时后自动清理。可在 `.env` 中修改 `FILE_CLEANUP_MAX_AGE_HOURS`。

### 可以关闭自动清理吗？

不建议。如果确实需要，可以设置很大的值：
```bash
FILE_CLEANUP_MAX_AGE_HOURS=8760  # 一年
```

### 最大能处理多大的文件？

默认限制 50MB。修改限制：

在 `docker-compose.yml` 或 `.env` 中：
```yaml
environment:
  - MAX_FILE_SIZE=104857600  # 100MB (字节)
```

Nginx 也需要配置：
```nginx
client_max_body_size 100M;
```

## 错误和故障

### 启动失败：端口已被占用

```bash
# 查看端口占用
lsof -i :8000

# 停止占用进程或修改端口
```

### 500 Internal Server Error

查看详细日志：
```bash
# Docker
docker-compose logs -f

# 本地
tail -f logs/ebook-ai.log
```

常见原因：
- Calibre 未正确安装
- 磁盘空间不足
- 权限问题

### 文件上传失败

检查：
1. 文件大小是否超过限制
2. 磁盘空间是否充足
3. 文件格式是否支持

### Docker 容器频繁重启

```bash
# 查看日志
docker logs <container_id>

# 检查资源
docker stats
```

可能原因：
- 内存不足
- 配置错误
- 依赖缺失

### 转换卡住不动？

1. 检查日志查看进度
2. 等待超时（默认 5 分钟）
3. 重新提交任务
4. 检查系统资源

### 无法访问 Web 界面？

1. 检查服务是否启动：
```bash
curl http://localhost:8000/health
```

2. 检查防火墙：
```bash
sudo ufw status
```

3. 检查端口映射（Docker）

### WebSocket 连接失败？

如果使用反向代理，确保配置了 WebSocket 支持：
```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

## 开发相关

### 如何贡献代码？

请查看 [贡献指南](../CONTRIBUTING.md)。

### 如何报告 Bug？

在 GitHub 提交 Issue：https://github.com/YOUR_USERNAME/EBookAI/issues

请提供：
- 详细的问题描述
- 复现步骤
- 系统环境
- 相关日志

### 如何添加新的格式支持？

1. 在 `conversion_service.py` 中添加转换逻辑
2. 更新支持的格式列表
3. 添加测试用例
4. 更新文档
5. 提交 PR

### 如何集成新的 AI 服务商？

系统会自动发现 `{PROVIDER}_API_KEY` 格式的环境变量。只需：
1. 在 `.env.example` 添加配置示例
2. 更新文档说明
3. 测试功能

## 其他问题

### 项目路线图？

查看 README 中的"开发路线图"部分。

### 性能基准测试？

取决于硬件配置和文件大小。参考数据：
- EPUB→PDF (10MB)：约 5-10 秒
- AI 摘要 (5000字)：约 10-30 秒

### 可以商用吗？

可以。项目使用 MIT 许可证，允许商业使用。

### 如何获取技术支持？

1. 查看文档
2. 搜索现有 Issues
3. 在 GitHub 提交新 Issue
4. 参与社区讨论

---

没有找到答案？欢迎在 [GitHub Issues](https://github.com/YOUR_USERNAME/EBookAI/issues) 提问。
