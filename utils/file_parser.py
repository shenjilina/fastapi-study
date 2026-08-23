"""Day5 文档解析工具，支持 PDF/TXT 解析，含空文件与损坏文件兜底。"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from config.log_config import get_logger
from core.constants import (
    CORRUPTED_FILE_ERROR,
    EMPTY_FILE_ERROR,
    SUPPORTED_FILE_EXTENSIONS,
    UNSUPPORTED_FILE_TYPE_ERROR,
)

logger = get_logger(__name__)


class FileParseError(RuntimeError):
    """文档解析失败异常。"""


def _validate_file(file_path: str | Path) -> Path:
    """校验文件路径、存在性、扩展名。"""
    path = Path(file_path)
    if not path.exists():
        raise FileParseError(f"文件不存在: {file_path}")

    if not path.is_file():
        raise FileParseError(f"路径不是文件: {file_path}")

    extension = path.suffix.lower().lstrip(".")
    if extension not in SUPPORTED_FILE_EXTENSIONS:
        raise FileParseError(f"{UNSUPPORTED_FILE_TYPE_ERROR}: .{extension}")

    if path.stat().st_size == 0:
        raise FileParseError(EMPTY_FILE_ERROR)

    return path


def parse_txt(file_path: str | Path) -> str:
    """解析 TXT 文件，返回纯文本内容。

    自动尝试多种编码，确保中文等非 ASCII 文本正常读取。
    """
    path = _validate_file(file_path)
    logger.info("Parsing TXT file: %s (size=%d)", path, path.stat().st_size)

    # 按优先级尝试编码，覆盖中文与英文场景
    encodings = ["utf-8", "gbk", "gb2312", "latin-1"]
    for encoding in encodings:
        try:
            text = path.read_text(encoding=encoding)
            if not text.strip():
                raise FileParseError(EMPTY_FILE_ERROR)
            logger.info("TXT parsed successfully: %d chars", len(text))
            return text
        except UnicodeDecodeError:
            continue

    raise FileParseError(f"无法解码 TXT 文件，尝试编码: {encodings}")


def parse_pdf(file_path: str | Path) -> str:
    """解析 PDF 文件，返回纯文本内容。

    使用 pypdf（PyPDF2 的维护继任者）提取文本，
    处理空页面、加密文件、损坏文件等异常场景。
    """
    path = _validate_file(file_path)
    logger.info("Parsing PDF file: %s (size=%d)", path, path.stat().st_size)

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise FileParseError("未安装 pypdf 依赖") from exc

    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise FileParseError(f"{CORRUPTED_FILE_ERROR}: {exc}") from exc

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise FileParseError(f"PDF 文件已加密且无法解密: {exc}") from exc

    if len(reader.pages) == 0:
        raise FileParseError("PDF 文件不包含任何页面")

    text_parts: list[str] = []
    for page_num, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text.strip())
        except Exception as exc:
            logger.warning("Failed to extract text from page %d: %s", page_num, exc)

    if not text_parts:
        raise FileParseError("PDF 文件解析后未获取到有效文本内容")

    result = "\n\n".join(text_parts)
    logger.info("PDF parsed successfully: %d pages, %d chars", len(reader.pages), len(result))
    return result


def parse_docx(file_path: str | Path) -> str:
    """Extract paragraph text from a DOCX package without an external binary dependency."""
    path = _validate_file(file_path)
    try:
        with ZipFile(path) as archive:
            document_xml = archive.read("word/document.xml")
    except (BadZipFile, KeyError) as exc:
        raise FileParseError(f"{CORRUPTED_FILE_ERROR}: 无效 DOCX 文件") from exc

    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError as exc:
        raise FileParseError(f"{CORRUPTED_FILE_ERROR}: DOCX XML 无法读取") from exc

    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for paragraph in root.iter(f"{namespace}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t"))
        if text.strip():
            paragraphs.append(text.strip())
    if not paragraphs:
        raise FileParseError("DOCX 文件解析后未获取到有效文本内容")
    return "\n\n".join(paragraphs)


def parse_file(file_path: str | Path) -> str:
    """根据文件扩展名自动分发到对应的解析器。

    Args:
        file_path: 文件路径。

    Returns:
        解析后的纯文本内容。

    Raises:
        FileParseError: 文件不存在、格式不支持、文件为空或解析失败。
    """
    path = Path(file_path)
    extension = path.suffix.lower().lstrip(".")

    if extension in {"txt", "md", "markdown"}:
        return parse_txt(path)
    if extension == "pdf":
        return parse_pdf(path)
    if extension == "docx":
        return parse_docx(path)

    raise FileParseError(f"{UNSUPPORTED_FILE_TYPE_ERROR}: .{extension}")


def get_file_extension(file_path: str | Path) -> str:
    """获取文件扩展名（不含点号，小写）。"""
    return Path(file_path).suffix.lower().lstrip(".")
