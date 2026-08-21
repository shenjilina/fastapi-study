# Repository Guidelines

## Project Structure & Module Organization

This Python 3.11-3.13 FastAPI RAG service is managed with `uv`. Domain APIs live in `api/` (for example, `api/knowledge/` and `api/rag/`), with controllers, schemas, models, CRUD, and services grouped by domain. Shared code is in `common/`, infrastructure in `core/`, settings and logging in `config/`, and helpers in `utils/`. `main.py` runs locally; `init_app.py` exposes the application. Tests are in `tests/`, scripts and Alembic migrations in `scripts/`, and notes in `docs/`. `chroma/`, `rag_project.db`, and `logs/` are runtime artifacts.

## Build, Test, and Development Commands

- `uv sync` installs the locked runtime and development dependencies.
- `uv run main.py` starts Uvicorn using `.env`; check `http://127.0.0.1:8000/health`.
- `uv run pytest` runs the configured test suite under `tests/`.
- `uv run ruff check .` lints; `uv run ruff format --check .` verifies formatting.
- `uv run python scripts/init_db.py` initializes the local database. Use `uv run alembic upgrade head` for tracked migrations.
- `docker compose up -d --build` builds and starts the container stack; use `docker compose logs -f` for diagnostics.

## Coding Style & Naming Conventions

Use four spaces, type hints, and focused functions. Follow PEP 8 naming: `snake_case` for modules, functions, and variables; `PascalCase` for classes; and `UPPER_SNAKE_CASE` for constants. Keep lines at or below 100 characters per `pyproject.toml`. Preserve the layered API structure and reuse shared response, dependency, settings, and exception helpers. Public schemas should follow the project's Pydantic conventions, including camelCase aliases where applicable.

## Testing Guidelines

Use pytest with files named `test_*.py` and functions named `test_<behavior>`. Add a focused regression test for each behavior change, especially API responses, CRUD, authentication, and RAG errors. Run `uv run pytest`; no coverage threshold is enforced.

## Commit & Pull Request Guidelines

Use imperative Conventional Commit-style subjects with a scope, such as `feat(api): add knowledge search` or `fix(rag): handle empty retrieval`. Keep commits focused. Pull requests should explain the change, list validation commands and configuration or migration steps, link an issue when available, and include examples or screenshots for user-facing API changes. Call out new environment variables and migrations.

## Security & Configuration Tips

Copy local settings into `.env` and never commit real credentials, JWT keys, model tokens, or private data. Review `config/settings.py` and `docker-compose.yml` when adding settings so local and container defaults remain consistent. Treat the SQLite database, Chroma persistence directory, and logs as environment-specific artifacts.
