from types import SimpleNamespace

import pytest

from common.dependencies import ensure_owner
from core.constants import ACCOUNT_DISABLED_CODE, AUTHENTICATION_ERROR_CODE
from core.exceptions import AppException, _translate_validation_message
from api.user import service
from api.user.schema import ChangePasswordRequest, LoginRequest


def test_ensure_owner_allows_matching_user() -> None:
    ensure_owner(7, SimpleNamespace(id=7))


def test_ensure_owner_rejects_other_user() -> None:
    with pytest.raises(AppException) as exc_info:
        ensure_owner(7, SimpleNamespace(id=8), resource="知识库")

    assert exc_info.value.status_code == 403


def test_login_invalid_credentials_use_authentication_code(monkeypatch) -> None:
    monkeypatch.setattr(service.crud, "get_user_by_username", lambda db, username: None)

    with pytest.raises(AppException) as exc_info:
        service.login(None, LoginRequest(username="missing", password="Password123"))

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == AUTHENTICATION_ERROR_CODE


def test_login_disabled_account_uses_authentication_code(monkeypatch) -> None:
    user = SimpleNamespace(id=1, hashed_password="hashed", is_active=False)
    monkeypatch.setattr(service.crud, "get_user_by_username", lambda db, username: user)
    monkeypatch.setattr(service, "verify_password", lambda password, hashed_password: True)

    with pytest.raises(AppException) as exc_info:
        service.login(None, LoginRequest(username="disabled", password="Password123"))

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == ACCOUNT_DISABLED_CODE


def test_change_password_requires_current_password(monkeypatch) -> None:
    user = SimpleNamespace(hashed_password="old-hash")
    monkeypatch.setattr(service, "verify_password", lambda password, hashed_password: False)

    with pytest.raises(AppException) as exc_info:
        service.change_password(
            SimpleNamespace(),
            user,
            ChangePasswordRequest(old_password="WrongPass", new_password="NewPass123"),
        )

    assert exc_info.value.status_code == 401
    assert user.hashed_password == "old-hash"


def test_change_password_hashes_and_commits_new_password(monkeypatch) -> None:
    user = SimpleNamespace(hashed_password="old-hash")
    db = SimpleNamespace(commit=lambda: None, rollback=lambda: None)
    monkeypatch.setattr(service, "verify_password", lambda password, hashed_password: True)
    monkeypatch.setattr(service, "hash_password", lambda password: "new-hash")

    service.change_password(
        db,
        user,
        ChangePasswordRequest(old_password="OldPass123", new_password="NewPass123"),
    )

    assert user.hashed_password == "new-hash"


def test_validation_messages_are_translated_to_chinese() -> None:
    assert _translate_validation_message("missing", "Field required", {}) == "字段为必填项"
    assert (
        _translate_validation_message(
            "string_too_short", "String should have at least 8 characters", {"min_length": 8}
        )
        == "长度不能少于 8 个字符"
    )
    assert _translate_validation_message("int_parsing", "Input should be a valid integer", {}) == (
        "请输入有效的数字"
    )
