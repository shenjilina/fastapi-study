# FastAPI Study

使用 `uv` 管理依赖和虚拟环境的 FastAPI 学习项目基础模板。

## 目录结构

```text
fastapi-study/
├─ app/
│  ├─ api/
│  ├─ core/
│  └─ main.py
├─ tests/
├─ .gitignore
├─ pyproject.toml
└─ README.md
```

## 常用命令

```bash
.venv\Scripts\activate
uv sync
uv run uvicorn app.main:app --reload
uv run pytest
```
