# Resource Authorization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure every authenticated business operation can access or mutate only resources owned by the authenticated user.

**Architecture:** Keep the existing router-level JWT authentication. Thread the resolved `current_user` into service methods and enforce ownership at the service boundary, where all controller paths converge. Reuse a small common ownership helper and return `403` for existing resources owned by another user.

**Tech Stack:** FastAPI dependencies, SQLAlchemy ORM, Pydantic, pytest.

---

### Task 1: Add shared ownership checks

**Files:**
- Modify: `common/dependencies.py`
- Test: `tests/test_authorization.py`

- [x] Add a helper that compares a resource owner ID to `current_user.id` and raises `AppException(status_code=403)` on mismatch.
- [x] Add unit tests for matching and mismatching owners.

### Task 2: Protect knowledge-base and document services

**Files:**
- Modify: `api/knowledge/controller.py`
- Modify: `api/knowledge/service.py`
- Modify: `api/document/controller.py`
- Modify: `api/document/service.py`
- Test: `tests/test_authorization.py`

- [x] Inject `current_user` into every knowledge/document controller endpoint.
- [x] Validate knowledge-base ownership for create, list, detail, document create/list/upload, document status update, and document delete.
- [x] Add authorization regression coverage for owner mismatch behavior.

### Task 3: Protect user and conversation queries

**Files:**
- Modify: `api/user/controller.py`
- Modify: `api/rag/controller.py`
- Modify: `api/rag/service.py`
- Test: `tests/test_authorization.py`

- [x] Restrict user listing/detail to the authenticated user.
- [x] Pass `current_user` to conversation list/detail/delete methods and enforce conversation/user/knowledge-base ownership.
- [x] Enforce cross-user conversation reads and deletes at the service boundary.

### Task 4: Verify the complete change

- [x] Run `uv run pytest`.
- [x] Run targeted `uv run ruff check` on changed files.
- [x] Run targeted `uv run ruff format --check` on changed files.
