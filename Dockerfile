FROM python:3.12-slim

WORKDIR /app

# 安装编译依赖
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./

# 先装 CPU-only torch（避免下载 2GB+ 的 GPU 版 nvidia 包）
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 安装其余生产依赖
RUN pip install --no-cache-dir \
    "fastapi>=0.116.0" "uvicorn[standard]>=0.35.0" \
    "sqlalchemy>=2.0.41" "alembic>=1.16.4" \
    "sentence-transformers>=5.0.0" \
    "python-multipart>=0.0.20" "python-dotenv>=1.1.1" \
    "langchain>=0.3.26" "langchain-qdrant>=0.2.0" "qdrant-client>=1.14.2" \
    "langchain-ollama>=0.3.3" "langchain-text-splitters>=0.3.8" \
    "langchain-core>=0.3.69" "pydantic-settings>=2.10.1" \
    "pypdf>=6.14.2"

# 复制项目代码并安装项目包
COPY . .
RUN pip install --no-cache-dir --no-deps .

# 创建运行时目录
RUN mkdir -p logs data

EXPOSE 8000

# 启动前先初始化数据库表，再启动 FastAPI
CMD ["sh", "-c", "python scripts/init_db.py && python main.py"]
