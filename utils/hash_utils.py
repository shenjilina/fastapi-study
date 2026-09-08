"""Day5 文件 MD5 去重工具，纯无状态函数。"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

from config.log_config import get_logger

logger = get_logger(__name__)

# 读取文件的块大小（8KB），平衡内存占用与 IO 效率
_CHUNK_SIZE = 8192


def compute_file_md5(file_path: str | Path) -> str:
    """计算文件的 MD5 哈希值。

    采用分块读取方式，支持大文件而不占用过多内存。

    Args:
        file_path: 文件路径。

    Returns:
        32 字符的十六进制 MD5 哈希字符串。
    """
    path = Path(file_path)
    md5_hasher = hashlib.md5()
    with path.open("rb") as f:
        for chunk in _read_in_chunks(f):
            md5_hasher.update(chunk)
    return md5_hasher.hexdigest()


def compute_text_md5(text: str) -> str:
    """计算文本的 MD5 哈希值。

    用于文本内容去重，编码统一为 UTF-8。

    Args:
        text: 文本内容。

    Returns:
        32 字符的十六进制 MD5 哈希字符串。
    """
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def compute_bytes_md5(data: bytes) -> str:
    """计算字节流的 MD5 哈希值。

    用于内存中的文件内容去重。

    Args:
        data: 字节流数据。

    Returns:
        32 字符的十六进制 MD5 哈希字符串。
    """
    return hashlib.md5(data).hexdigest()


def _read_in_chunks(file_obj: BinaryIO, chunk_size: int = _CHUNK_SIZE):
    """分块读取文件对象，避免大文件一次性加载到内存。"""
    while True:
        chunk = file_obj.read(chunk_size)
        if not chunk:
            break
        yield chunk


def is_duplicate_file(file_path: str | Path, existing_md5_list: list[str]) -> bool:
    """检查文件是否与已有文件重复（基于 MD5）。

    Args:
        file_path: 待检查的文件路径。
        existing_md5_list: 已存在的 MD5 哈希列表。

    Returns:
        True 表示文件重复，False 表示不重复。
    """
    file_md5 = compute_file_md5(file_path)
    if file_md5 in existing_md5_list:
        logger.info("Duplicate file detected: %s (md5=%s)", file_path, file_md5)
        return True
    return False


def is_duplicate_text(text: str, existing_md5_list: list[str]) -> bool:
    """检查文本内容是否与已有内容重复（基于 MD5）。

    Args:
        text: 待检查的文本内容。
        existing_md5_list: 已存在的 MD5 哈希列表。

    Returns:
        True 表示文本重复，False 表示不重复。
    """
    text_md5 = compute_text_md5(text)
    if text_md5 in existing_md5_list:
        logger.info("Duplicate text detected (md5=%s)", text_md5)
        return True
    return False


def batch_compute_file_md5(file_paths: list[str | Path]) -> dict[str, str]:
    """批量计算多个文件的 MD5 哈希值。

    Args:
        file_paths: 文件路径列表。

    Returns:
        {文件路径: MD5 哈希值} 字典。
    """
    result: dict[str, str] = {}
    for fp in file_paths:
        path = str(fp)
        try:
            result[path] = compute_file_md5(fp)
        except Exception as exc:
            logger.warning("Failed to compute MD5 for %s: %s", path, exc)
            result[path] = ""
    return result
