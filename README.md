# FastAPI Study

This repository follows the Day 1 bootstrap plan from `plan.md`.

## What is ready

- Production-style project skeleton aligned with the target architecture
- `uv`-managed dependencies and lockfile workflow
- Environment-driven settings and logging bootstrap
- SQLAlchemy engine, session factory, and FastAPI dependency injection
- Application factory, startup entrypoints, and health check endpoint
- Basic bootstrap test coverage

## Quick start

```bash
.venv/Scripts/Activate.ps1  
uv sync
# 运行项目
uv run main.py
```

```bash
# chroma 服务
uv run chroma run --path ./chroma --host 0.0.0.0 --port 8000
```


Open `http://127.0.0.1:8000/health` after startup.
