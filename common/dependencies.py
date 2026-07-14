"""全局依赖与参数清洗工具。"""

from collections.abc import Iterable


def strip_text(value: str | None) -> str | None:
    """去掉字符串首尾空白字符。"""
    if value is None:
        return None
    return value.strip()


def ensure_text(value: str | None, *, field_name: str = "text") -> str:
    """确保字符串非空，常用于业务层参数防御。"""
    text = strip_text(value)
    if not text:
        raise ValueError(f"{field_name} cannot be empty")
    return text


def normalize_optional_text(value: str | None) -> str | None:
    """把空字符串归一化为 `None`，方便数据库层处理可空字段。"""
    text = strip_text(value)
    if text == "":
        return None
    return text


def sanitize_string_list(values: Iterable[str]) -> list[str]:
    """清洗字符串列表，移除空项并保留原始顺序。"""
    items: list[str] = []
    for value in values:
        text = strip_text(value)
        if text and text not in items:
            items.append(text)
    return items


def split_csv_text(value: str | None) -> list[str]:
    """把逗号分隔字符串转换为清洗后的列表。"""
    if value is None:
        return []
    return sanitize_string_list(value.split(","))
