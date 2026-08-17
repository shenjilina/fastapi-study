"""接口层统一日期时间格式自检：YYYY-MM-DD HH:mm:ss。

覆盖场景：
1. 序列化输出：JSON 模式下时间字段为统一格式，无 ISO 'T' 分隔符
2. Python 模式保留 datetime 对象，内部读写与 ORM 存储不受影响
3. 入参解析：'YYYY-MM-DD HH:mm:ss' 字符串可正确解析；ISO 等格式兼容回退
4. ORM from_attributes 转换链路不受影响
5. camelCase 别名配置不受影响
6. 端到端：真实接口响应中的 createdAt 为统一格式
"""

import re
import uuid
from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.rag.schema import ConversationRead
from api.user.schema import UserRead
from common.base_model import ApiDateTime, DATETIME_FORMAT
from init_app import app
from pydantic import BaseModel

DATETIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

client = TestClient(app)


def _make_user_read() -> UserRead:
    return UserRead(
        id=1,
        username="alice",
        email="alice@example.com",
        is_active=True,
        created_at=datetime(2026, 8, 17, 14, 30, 0),
        updated_at=datetime(2026, 8, 17, 15, 0, 5),
    )


def test_json_serialization_uses_unified_format() -> None:
    dumped = _make_user_read().model_dump(mode="json", by_alias=True)
    assert dumped["createdAt"] == "2026-08-17 14:30:00"
    assert dumped["updatedAt"] == "2026-08-17 15:00:05"
    assert "T" not in dumped["createdAt"], "不应输出 ISO 格式"


def test_python_mode_keeps_datetime_object() -> None:
    # Python 模式保留 datetime 对象，不影响代码内部读写
    dumped = _make_user_read().model_dump()
    assert isinstance(dumped["created_at"], datetime)


def test_parse_unified_format_input() -> None:
    user = UserRead.model_validate(
        {
            "id": 1,
            "username": "alice",
            "email": "a@example.com",
            "isActive": True,
            "createdAt": "2026-08-17 14:30:00",
            "updatedAt": "2026-08-17 15:00:05",
        }
    )
    assert user.created_at == datetime(2026, 8, 17, 14, 30, 0)
    assert user.updated_at == datetime(2026, 8, 17, 15, 0, 5)


def test_parse_iso_fallback_still_works() -> None:
    # 统一格式优先，其他格式回退 Pydantic 默认解析，避免误伤旧客户端
    user = UserRead.model_validate(
        {
            "id": 1,
            "username": "alice",
            "email": "a@example.com",
            "isActive": True,
            "createdAt": "2026-08-17T14:30:00",
            "updatedAt": "2026-08-17T15:00:05",
        }
    )
    assert user.created_at == datetime(2026, 8, 17, 14, 30, 0)


def test_orm_from_attributes_unaffected() -> None:
    fake_orm = SimpleNamespace(
        id=1,
        username="alice",
        email="a@example.com",
        is_active=True,
        created_at=datetime(2026, 8, 17, 14, 30, 0),
        updated_at=datetime(2026, 8, 17, 15, 0, 5),
    )
    user = UserRead.model_validate(fake_orm)
    assert user.created_at == datetime(2026, 8, 17, 14, 30, 0)
    assert user.model_dump(mode="json", by_alias=True)["createdAt"] == "2026-08-17 14:30:00"


def test_nested_read_model_format() -> None:
    conversation = ConversationRead(
        id=1,
        user_id=2,
        knowledge_base_id=3,
        question="问题",
        answer="回答",
        source_document_ids=[10],
        session_id=None,
        status="generated",
        created_at=datetime(2026, 8, 17, 14, 30, 0),
    )
    dumped = conversation.model_dump(mode="json", by_alias=True)
    assert DATETIME_PATTERN.match(dumped["createdAt"]), dumped["createdAt"]


def test_datetime_format_constant() -> None:
    assert DATETIME_FORMAT == "%Y-%m-%d %H:%M:%S"
    assert datetime(2026, 8, 17, 14, 30, 0).strftime(DATETIME_FORMAT) == "2026-08-17 14:30:00"


def test_standalone_annotated_type() -> None:
    # ApiDateTime 可独立用于任意新模型的 datetime 字段
    class _Demo(BaseModel):
        occurred_at: ApiDateTime

    demo = _Demo.model_validate({"occurred_at": "2026-08-17 14:30:00"})
    assert demo.occurred_at == datetime(2026, 8, 17, 14, 30, 0)
    assert demo.model_dump(mode="json")["occurred_at"] == "2026-08-17 14:30:00"


def test_endpoint_response_datetime_format() -> None:
    # 端到端：注册接口（免鉴权）响应的 createdAt/updatedAt 为统一格式
    suffix = uuid.uuid4().hex[:8]
    username = f"dt_user_{suffix}"
    resp = client.post(
        "/api/auth/create_user",
        json={"username": username, "email": f"{username}@example.com", "password": "Password123"},
    )
    assert resp.status_code == 201, f"注册失败: {resp.json()}"
    data = resp.json()["data"]
    assert DATETIME_PATTERN.match(data["createdAt"]), data["createdAt"]
    assert DATETIME_PATTERN.match(data["updatedAt"]), data["updatedAt"]
    assert "T" not in data["createdAt"], "接口响应不应输出 ISO 格式"
