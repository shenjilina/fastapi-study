"""Pydantic 别名机制自检：snake_case <-> camelCase 双向转换。

覆盖场景：
1. to_camel / to_snake 工具函数边界（缩写、多下划线、幂等）
2. 请求入参：camelCase 传参可解析，snake_case 兼容（populate_by_name）
3. 个别字段别名覆盖：AliasChoices 兼容 currentSessionId
4. 响应出参：默认 model_dump 保持 snake_case；by_alias=True 输出 camelCase
5. Python 代码内两种命名读写（populate_by_name 实例化 + 属性访问）
6. ORM 对象 from_attributes 转换不受别名影响
"""

from datetime import datetime
from types import SimpleNamespace

from api.rag.schema import ConversationRead, RAGQuestionRequest
from api.user.schema import UserRead
from common.base_model import ApiBaseModel, to_camel, to_snake


def test_to_camel_basic() -> None:
    assert to_camel("user_id") == "userId"
    assert to_camel("document_id") == "documentId"
    assert to_camel("conversation_session_id") == "conversationSessionId"
    assert to_camel("question") == "question"


def test_to_camel_edge_cases() -> None:
    # 多下划线 / 首尾下划线：空段被过滤
    assert to_camel("__a__b_") == "aB"
    # 单段仅小写化
    assert to_camel("ID") == "id"
    assert to_camel("") == ""


def test_to_snake_basic() -> None:
    assert to_snake("userId") == "user_id"
    assert to_snake("conversationSessionId") == "conversation_session_id"
    assert to_snake("question") == "question"


def test_to_snake_acronym_and_idempotent() -> None:
    # 首字母缩写整体保留，不逐字母拆散
    assert to_snake("userID") == "user_id"
    assert to_snake("HTTPSProxy") == "https_proxy"
    assert to_snake("HTMLParser") == "html_parser"
    # 已是 snake_case 时幂等
    assert to_snake("user_id") == "user_id"


def test_request_accepts_camel_case() -> None:
    payload = RAGQuestionRequest.model_validate(
        {"userId": 1, "knowledgeBaseId": 2, "question": "FastAPI 是什么？"}
    )
    assert payload.user_id == 1
    assert payload.knowledge_base_id == 2


def test_request_still_accepts_snake_case() -> None:
    payload = RAGQuestionRequest.model_validate(
        {"user_id": 1, "knowledge_base_id": 2, "question": "问题"}
    )
    assert payload.user_id == 1


def test_field_level_alias_override() -> None:
    # AliasChoices 覆盖全局别名：currentSessionId 也能命中 conversation_session_id
    via_camel = RAGQuestionRequest.model_validate(
        {"userId": 1, "knowledgeBaseId": 2, "question": "问题", "conversationSessionId": "s1"}
    )
    via_legacy = RAGQuestionRequest.model_validate(
        {"userId": 1, "knowledgeBaseId": 2, "question": "问题", "currentSessionId": "s1"}
    )
    assert via_camel.conversation_session_id == "s1"
    assert via_legacy.conversation_session_id == "s1"


def test_dump_default_keeps_snake_case() -> None:
    # 项目出参约定：不带 by_alias 时保持 snake_case，兼容既有脚本与测试
    payload = RAGQuestionRequest.model_validate(
        {"userId": 1, "knowledgeBaseId": 2, "question": "问题"}
    )
    assert "knowledge_base_id" in payload.model_dump()


def test_dump_by_alias_outputs_camel_case() -> None:
    payload = RAGQuestionRequest.model_validate(
        {"user_id": 1, "knowledge_base_id": 2, "question": "问题"}
    )
    dumped = payload.model_dump(by_alias=True)
    assert dumped["userId"] == 1
    assert dumped["knowledgeBaseId"] == 2
    assert "knowledge_base_id" not in dumped


def test_populate_by_name_instance_access() -> None:
    # Python 代码内部始终用字段原名读写
    payload = RAGQuestionRequest(user_id=9, knowledge_base_id=8, question="问题")
    assert payload.user_id == 9
    payload.top_k = 3
    assert payload.model_dump(by_alias=True)["topK"] == 3


def test_nested_model_serialization_by_alias() -> None:
    conversation = ConversationRead(
        id=1,
        user_id=2,
        knowledge_base_id=3,
        question="问题",
        answer="回答",
        source_document_ids=[10, 11],
        session_id="sess-1",
        status="generated",
        created_at=datetime(2026, 8, 17, 12, 0, 0),
    )
    camel = conversation.model_dump(by_alias=True, mode="json")
    assert camel["knowledgeBaseId"] == 3
    assert camel["sourceDocumentIds"] == [10, 11]
    assert camel["sessionId"] == "sess-1"


def test_orm_from_attributes_unaffected() -> None:
    # ORM 属性为 snake_case，from_attributes 走字段原名通道，别名不干扰
    fake_orm = SimpleNamespace(
        id=1,
        username="alice",
        email="alice@example.com",
        is_active=True,
        created_at=datetime(2026, 8, 17, 12, 0, 0),
        updated_at=datetime(2026, 8, 17, 12, 0, 0),
    )
    user = UserRead.model_validate(fake_orm)
    assert user.username == "alice"
    assert user.model_dump(by_alias=True)["isActive"] is True


def test_round_trip_snake_camel_snake() -> None:
    for name in ("user_id", "knowledge_base_id", "source_document_ids"):
        assert to_snake(to_camel(name)) == name


class _DemoModel(ApiBaseModel):
    """基类继承示例：子类叠加自身 ConfigDict 时别名能力仍保留。"""

    current_page: int = 1
    page_size: int = 10


def test_subclass_config_merge() -> None:
    model = _DemoModel.model_validate({"currentPage": 2, "pageSize": 20})
    assert model.current_page == 2
    assert model.model_dump(by_alias=True) == {"currentPage": 2, "pageSize": 20}
