# Docker 部署指南

## 一、前置依赖要求

| 依赖 | 最低版本 | 说明 |
|------|---------|------|
| Docker Engine | 24.0+ | 容器运行时 |
| Docker Compose | v2.20+ | 容器编排（`docker compose` 内置命令） |

> Windows 用户需安装 Docker Desktop 并启用 WSL2 后端。

## 二、服务架构

| 服务 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| FastAPI 应用 | fastapi-app | 8000 | RAG 项目主服务 |
| ChromaDB 服务器 | chroma | 8001 | 独立向量数据库实例 |
| ChromaDB 管理界面 | chroma-admin | 3434 | 向量库可视化工具 |

## 三、启动步骤

```bash
# 1. 清理旧容器和卷（全新环境可跳过）
docker compose down -v

# 2. 拉取依赖镜像
docker compose pull

# 3. 构建并启动所有服务
docker compose up -d --build

# 4. 查看容器状态
docker compose ps
```

等待 `fastapi-app` 和 `chroma` 显示 `healthy` 后即可访问。

## 四、访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| FastAPI 接口 | http://localhost:8000 | 业务 API |
| API 文档 | http://localhost:8000/docs | Swagger UI |
| 健康检查 | http://localhost:8000/health | 服务状态 |
| ChromaDB Admin | http://localhost:3434 | 向量库可视化 |
| ChromaDB API | http://localhost:8001 | 向量库 HTTP 接口 |

## 五、停止与清理

```bash
# 停止所有容器（保留数据）
docker compose stop

# 停止并删除容器（保留数据卷）
docker compose down

# 停止、删除容器并清除数据（完全重置）
docker compose down -v
```

## 六、日志查看

```bash
# 查看所有服务日志
docker compose logs -f

# 只看 FastAPI 日志
docker compose logs -f fastapi-app

# 只看最近 50 行
docker compose logs --tail 50 fastapi-app
```

## 七、常见问题排查

### 1. 构建失败：README.md not found

**原因**：`.dockerignore` 排除了 `*.md` 文件，但 `pyproject.toml` 的 `readme = "README.md"` 需要该文件。

**解决**：确保 `.dockerignore` 中没有 `*.md`，且 Dockerfile 中 `COPY` 包含 `README.md`。

### 2. 构建极慢：下载 2GB+ 的 GPU 包

**原因**：`sentence-transformers` 依赖 `torch`，默认拉取 GPU 版（含 NVIDIA CUDA 库）。

**解决**：Dockerfile 中先通过 `pip install torch --index-url https://download.pytorch.org/whl/cpu` 安装 CPU 版 torch（约 192MB），再安装其余依赖。

### 3. chroma 容器健康检查失败

**原因**：chromadb/chroma 镜像是极简 Debian，没有 `python`/`curl`/`wget` 命令。

**解决**：健康检查改用 `bash -c 'echo > /dev/tcp/localhost/8000'`（bash 内置端口检测，无需额外工具）。

### 4. ChromaDB API 返回 "v1 API is deprecated"

**原因**：ChromaDB 1.x 已弃用 v1 API，需要使用 `/api/v2/` 前缀。

**解决**：将所有 ChromaDB API 请求改为 `/api/v2/heartbeat`、`/api/v2/collections` 等。

### 5. chroma-admin 显示 unhealthy

**原因**：`neetpalsingh/chromadb-admin` 镜像内置的健康检查依赖 `python`，但镜像内没有。

**解决**：不影响使用，管理界面仍可通过 http://localhost:3434 正常访问。

### 6. Ollama 连接失败

**原因**：容器内无法访问宿主机的 Ollama 服务。

**解决**：确保 Ollama 在宿主机上运行，且 `OLLAMA_BASE_URL=http://host.docker.internal:11434`（Docker Desktop 自动解析 `host.docker.internal`）。

## 八、数据持久化

| 数据卷 | 挂载点 | 说明 |
|--------|--------|------|
| app-data | /app/data | SQLite 数据库文件 |
| app-chroma | /app/chroma | 应用内嵌 Chroma 向量数据 |
| app-logs | /app/logs | 应用日志文件 |
| chroma-data | /chroma/chroma | 独立 ChromaDB 服务器数据 |

> 注意：FastAPI 应用使用内嵌 Chroma（本地文件），与独立的 ChromaDB 服务器是两个独立实例。chroma-admin 只能查看 ChromaDB 服务器的数据，不能查看应用内嵌 Chroma 的数据。

## 九、配置说明

通过 `docker-compose.yml` 的 `environment` 段覆盖 `.env` 文件中的配置：

```yaml
environment:
  - APP_HOST=0.0.0.0          # 容器内必须为 0.0.0.0
  - APP_DEBUG=false            # 生产环境关闭调试
  - DATABASE_URL=sqlite:///./data/rag_project.db
  - OLLAMA_BASE_URL=http://host.docker.internal:11434
```

如需修改配置，编辑 `docker-compose.yml` 后执行：

```bash
docker compose up -d
```
