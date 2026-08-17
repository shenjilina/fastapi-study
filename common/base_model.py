"""Pydantic 模型通用别名基类（snake_case <-> camelCase 双向转换）。

项目使用 Pydantic v2（>=2.0），因此采用 ConfigDict(alias_generator=...) 写法，
而非 v1 的内部类 Config.alias_generator + allow_population_by_field_name。

约定：
- 请求入参：前端可用 camelCase（如 documentId），也可兼容 snake_case（document_id），
  由 alias_generator（生成验证别名）+ populate_by_name=True（放行字段原名）共同实现。
- 响应出参：统一 snake_case。控制器使用 model_dump(mode="json") 不带 by_alias，
  与既有脚本 / 测试约定一致；如需切换 camelCase 出参，只需改为
  model_dump(by_alias=True)，一处开关全局生效。
- Python 代码内部：始终使用字段原名（snake_case）读写字段。

个别特殊字段可在模型内用
Field(validation_alias=..., serialization_alias=...) 单独覆盖全局别名。
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

# userId -> user_id：小写/数字与大写交界处插入下划线
_SNAKE_CASE_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
# HTTPSProxy -> HTTPS_Proxy：连续大写缩写与后续普通单词的交界（全大写词不受影响）
_ACRONYM_BOUNDARY_RE = re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])")


def to_camel(name: str) -> str:
    """snake_case -> camelCase。

    边界处理：
    - 空段过滤：多下划线 / 首尾下划线（如 "__a__b_"）不会产生空片段；
    - 单段原样返回（仅做小写化，如 "ID" -> "id"），无下划线不强拆；
    - 纯大写片段保留语义（如 "md5" -> "Md5" 属常规 title 行为）。
    """
    parts = [part for part in name.split("_") if part]
    if not parts:
        return name
    head, *tail = parts
    return head.lower() + "".join(part[:1].upper() + part[1:].lower() for part in tail)


def to_snake(name: str) -> str:
    """camelCase / PascalCase -> snake_case。

    边界处理：
    - 首字母缩写：userId -> user_id、userID -> user_id、HTTPSProxy -> https_proxy；
    - 连续大写不拆散：HTMLParser -> html_parser（缩写视为整体）；
    - 已是 snake_case 时幂等：user_id -> user_id。
    """
    text = _ACRONYM_BOUNDARY_RE.sub("_", name)
    text = _SNAKE_CASE_RE.sub("_", text)
    return text.lower()


class ApiBaseModel(BaseModel):
    """全项目 API 模型基类：camelCase 别名 + 字段原名双通道。

    - alias_generator=to_camel：序列化/验证别名统一为 camelCase；
    - populate_by_name=True：字段原名（snake_case）同样可用于入参与实例化，
      等价于 v1 的 allow_population_by_field_name，保证 ORM 对象
      （from_attributes）与既有 snake_case 调用方不受影响；
    - 子类可叠加自己的 ConfigDict（如 from_attributes=True），
      Pydantic v2 会将子类配置与基类配置合并，别名能力自动继承。
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )
