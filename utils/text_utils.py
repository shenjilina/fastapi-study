"""Day5 文本清洗、Token 截断、去重工具，纯无状态函数。"""

from __future__ import annotations

import re

from config.log_config import get_logger
from core.constants import TOKEN_CHARS_RATIO_CN, TOKEN_CHARS_RATIO_EN

logger = get_logger(__name__)

# 匹配连续空白字符（含全角空格、制表符、换行符等）
_WHITESPACE_PATTERN = re.compile(r"[\s\u3000]+")
# 匹配不可见控制字符
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# 匹配常见 BOM 标记
_BOM_PATTERN = re.compile(r"[\ufeff]")
# 匹配中文 Unicode 范围
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def clean_text(text: str) -> str:
    """清洗文本：去除多余空白、控制字符、BOM 标记。

    Args:
        text: 原始文本。

    Returns:
        清洗后的文本，首尾无多余空白。
    """
    if not text:
        return ""

    # 移除 BOM 标记
    result = _BOM_PATTERN.sub("", text)
    # 移除不可见控制字符
    result = _CONTROL_CHAR_PATTERN.sub("", result)
    # 将连续空白（含全角空格、换行）压缩为单个空格
    result = _WHITESPACE_PATTERN.sub(" ", result)
    # 去除首尾空白
    return result.strip()


def estimate_tokens(text: str) -> int:
    """估算文本的近似 Token 数量。

    采用启发式方法：中文字符约 2 字符/token，英文约 4 字符/token。
    这是无需 tokenizer 依赖的轻量估算，满足截断场景的精度需求。

    Args:
        text: 待估算的文本。

    Returns:
        估算的 Token 数量。
    """
    if not text:
        return 0

    cjk_count = len(_CJK_PATTERN.findall(text))
    non_cjk_count = len(text) - cjk_count

    # 中文按 2 字符/token，英文按 4 字符/token
    cjk_tokens = cjk_count / TOKEN_CHARS_RATIO_CN
    en_tokens = non_cjk_count / TOKEN_CHARS_RATIO_EN

    return int(cjk_tokens + en_tokens)


def truncate_by_tokens(text: str, max_tokens: int) -> str:
    """按近似 Token 数截断文本，防止上下文溢出。

    Args:
        text: 原始文本。
        max_tokens: 最大允许的 Token 数。

    Returns:
        截断后的文本。如果原始文本未超限则原样返回。
    """
    if not text or max_tokens <= 0:
        return ""

    estimated = estimate_tokens(text)
    if estimated <= max_tokens:
        return text

    # 按比例计算字符截断位置
    ratio = max_tokens / estimated
    char_limit = int(len(text) * ratio)

    # 尽量在句子边界截断，避免半句话
    truncated = text[:char_limit]
    last_sentence_end = max(
        truncated.rfind("。"),
        truncated.rfind("."),
        truncated.rfind("！"),
        truncated.rfind("!"),
        truncated.rfind("？"),
        truncated.rfind("?"),
        truncated.rfind("\n"),
    )

    if last_sentence_end > char_limit // 2:
        truncated = truncated[: last_sentence_end + 1]

    logger.info(
        "Text truncated: original_tokens=%d max_tokens=%d chars %d->%d",
        estimated,
        max_tokens,
        len(text),
        len(truncated),
    )
    return truncated


def deduplicate_texts(texts: list[str]) -> tuple[list[str], int]:
    """对文本列表去重，保留原始顺序。

    使用文本内容清洗后的 MD5 作为去重依据，
    避免因空白差异导致重复判定失败。

    Args:
        texts: 待去重的文本列表。

    Returns:
        (去重后的文本列表, 被移除的重复数量)
    """
    from utils.hash_utils import compute_text_md5

    seen: set[str] = set()
    unique: list[str] = []
    duplicate_count = 0

    for text in texts:
        cleaned = clean_text(text)
        if not cleaned:
            duplicate_count += 1
            continue
        md5 = compute_text_md5(cleaned)
        if md5 in seen:
            duplicate_count += 1
            continue
        seen.add(md5)
        unique.append(text)

    if duplicate_count > 0:
        logger.info("Deduplicated texts: removed %d duplicates from %d total", duplicate_count, len(texts))

    return unique, duplicate_count


def split_text_into_chunks(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[str]:
    """将长文本按固定字符大小切片，带重叠区。

    这是字符级切片的轻量实现，Day6 接入 LangChain 时会替换为
    智能切片器（RecursiveCharacterTextSplitter），此处保证基础可用。

    Args:
        text: 原始文本。
        chunk_size: 每个切片的字符长度。
        overlap: 相邻切片的重叠字符数。

    Returns:
        切片列表。
    """
    if not text or chunk_size <= 0:
        return []

    cleaned = clean_text(text)
    if not cleaned:
        return []

    if overlap < 0:
        overlap = 0
    if overlap >= chunk_size:
        overlap = chunk_size // 4

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = start + chunk_size
        chunk = cleaned[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start += chunk_size - overlap

    return chunks
