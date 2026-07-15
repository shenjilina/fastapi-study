"""Day5 单元测试：覆盖 LLM、检索器、文件解析、MD5 去重、文本工具。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ============================================================
# utils/hash_utils 测试
# ============================================================


class TestHashUtils:
    """文件 MD5 去重工具测试。"""

    def test_compute_text_md5_returns_hex_string(self) -> None:
        from utils.hash_utils import compute_text_md5

        md5 = compute_text_md5("hello world")
        assert len(md5) == 32
        assert all(c in "0123456789abcdef" for c in md5)

    def test_compute_text_md5_deterministic(self) -> None:
        from utils.hash_utils import compute_text_md5

        assert compute_text_md5("test") == compute_text_md5("test")

    def test_compute_text_md5_different_inputs(self) -> None:
        from utils.hash_utils import compute_text_md5

        assert compute_text_md5("text1") != compute_text_md5("text2")

    def test_compute_bytes_md5(self) -> None:
        from utils.hash_utils import compute_bytes_md5

        md5 = compute_bytes_md5(b"hello")
        assert len(md5) == 32

    def test_compute_file_md5(self, tmp_path: Path) -> None:
        from utils.hash_utils import compute_file_md5

        file_path = tmp_path / "test.txt"
        file_path.write_text("hello world", encoding="utf-8")
        md5 = compute_file_md5(file_path)
        assert len(md5) == 32
        assert md5 == compute_file_md5(file_path)

    def test_compute_file_md5_large_file(self, tmp_path: Path) -> None:
        """验证大文件分块读取的 MD5 正确性。"""
        from utils.hash_utils import compute_bytes_md5, compute_file_md5

        content = b"A" * 20000
        file_path = tmp_path / "large.txt"
        file_path.write_bytes(content)

        assert compute_file_md5(file_path) == compute_bytes_md5(content)

    def test_is_duplicate_file_true(self, tmp_path: Path) -> None:
        from utils.hash_utils import compute_file_md5, is_duplicate_file

        file_path = tmp_path / "dup.txt"
        file_path.write_text("content", encoding="utf-8")
        md5 = compute_file_md5(file_path)
        assert is_duplicate_file(file_path, [md5]) is True

    def test_is_duplicate_file_false(self, tmp_path: Path) -> None:
        from utils.hash_utils import is_duplicate_file

        file_path = tmp_path / "unique.txt"
        file_path.write_text("unique content", encoding="utf-8")
        assert is_duplicate_file(file_path, ["00000000000000000000000000000000"]) is False

    def test_is_duplicate_text_true(self) -> None:
        from utils.hash_utils import compute_text_md5, is_duplicate_text

        md5 = compute_text_md5("duplicate")
        assert is_duplicate_text("duplicate", [md5]) is True

    def test_is_duplicate_text_false(self) -> None:
        from utils.hash_utils import is_duplicate_text

        assert is_duplicate_text("unique", ["00000000000000000000000000000000"]) is False

    def test_batch_compute_file_md5(self, tmp_path: Path) -> None:
        from utils.hash_utils import batch_compute_file_md5

        f1 = tmp_path / "a.txt"
        f1.write_text("aaa", encoding="utf-8")
        f2 = tmp_path / "b.txt"
        f2.write_text("bbb", encoding="utf-8")

        result = batch_compute_file_md5([f1, f2])
        assert len(result) == 2
        assert result[str(f1)] != result[str(f2)]


# ============================================================
# utils/text_utils 测试
# ============================================================


class TestTextUtils:
    """文本清洗、Token 截断、去重工具测试。"""

    def test_clean_text_removes_extra_whitespace(self) -> None:
        from utils.text_utils import clean_text

        assert clean_text("  hello   world  ") == "hello world"
        assert clean_text("a\t\tb\n\nc") == "a b c"

    def test_clean_text_removes_bom(self) -> None:
        from utils.text_utils import clean_text

        text = "\ufeffHello"
        assert clean_text(text) == "Hello"

    def test_clean_text_removes_control_chars(self) -> None:
        from utils.text_utils import clean_text

        text = "Hello\x00\x07World"
        assert clean_text(text) == "HelloWorld"

    def test_clean_text_handles_empty(self) -> None:
        from utils.text_utils import clean_text

        assert clean_text("") == ""
        assert clean_text("   ") == ""

    def test_clean_text_normalizes_fullwidth_space(self) -> None:
        from utils.text_utils import clean_text

        assert clean_text("你好\u3000世界") == "你好 世界"

    def test_estimate_tokens_english(self) -> None:
        from utils.text_utils import estimate_tokens

        # 英文约 4 字符/token
        text = "hello world"  # 11 chars
        tokens = estimate_tokens(text)
        assert tokens > 0
        assert tokens == int(11 / 4)

    def test_estimate_tokens_chinese(self) -> None:
        from utils.text_utils import estimate_tokens

        # 中文约 2 字符/token
        text = "你好世界"  # 4 CJK chars
        tokens = estimate_tokens(text)
        assert tokens == int(4 / 2)

    def test_estimate_tokens_empty(self) -> None:
        from utils.text_utils import estimate_tokens

        assert estimate_tokens("") == 0

    def test_estimate_tokens_mixed(self) -> None:
        from utils.text_utils import estimate_tokens

        text = "Hello 你好"  # 5 English + 1 space + 2 CJK
        tokens = estimate_tokens(text)
        assert tokens > 0

    def test_truncate_by_tokens_short_text_returns_original(self) -> None:
        from utils.text_utils import truncate_by_tokens

        text = "short text"
        assert truncate_by_tokens(text, 100) == text

    def test_truncate_by_tokens_long_text(self) -> None:
        from utils.text_utils import truncate_by_tokens

        text = "This is a sentence. " * 100
        truncated = truncate_by_tokens(text, 10)
        assert len(truncated) < len(text)
        assert len(truncated) > 0

    def test_truncate_by_tokens_empty(self) -> None:
        from utils.text_utils import truncate_by_tokens

        assert truncate_by_tokens("", 100) == ""
        assert truncate_by_tokens("text", 0) == ""

    def test_truncate_by_tokens_prefers_sentence_boundary(self) -> None:
        from utils.text_utils import truncate_by_tokens

        text = "First sentence. Second sentence. Third sentence."
        truncated = truncate_by_tokens(text, 5)
        # 应在句号处截断
        assert truncated.endswith(".")

    def test_deduplicate_texts_removes_duplicates(self) -> None:
        from utils.text_utils import deduplicate_texts

        texts = ["hello", "world", "hello", "world", "unique"]
        unique, count = deduplicate_texts(texts)
        assert len(unique) == 3
        assert count == 2
        assert unique == ["hello", "world", "unique"]

    def test_deduplicate_texts_preserves_order(self) -> None:
        from utils.text_utils import deduplicate_texts

        texts = ["c", "b", "a", "b", "c"]
        unique, count = deduplicate_texts(texts)
        assert unique == ["c", "b", "a"]
        assert count == 2

    def test_deduplicate_texts_all_unique(self) -> None:
        from utils.text_utils import deduplicate_texts

        texts = ["a", "b", "c"]
        unique, count = deduplicate_texts(texts)
        assert len(unique) == 3
        assert count == 0

    def test_deduplicate_texts_empty(self) -> None:
        from utils.text_utils import deduplicate_texts

        unique, count = deduplicate_texts([])
        assert unique == []
        assert count == 0

    def test_split_text_into_chunks_basic(self) -> None:
        from utils.text_utils import split_text_into_chunks

        text = "abcdefghij" * 100  # 1000 chars
        chunks = split_text_into_chunks(text, chunk_size=200, overlap=20)
        assert len(chunks) > 1
        assert all(len(c) <= 200 for c in chunks)

    def test_split_text_into_chunks_overlap(self) -> None:
        from utils.text_utils import split_text_into_chunks

        text = "abcdefghijklmnopqrstuvwxyz"
        chunks = split_text_into_chunks(text, chunk_size=10, overlap=3)
        # 第二个 chunk 应该与前一个有 3 字符重叠
        if len(chunks) >= 2:
            assert chunks[0][-3:] == chunks[1][:3]

    def test_split_text_into_chunks_empty(self) -> None:
        from utils.text_utils import split_text_into_chunks

        assert split_text_into_chunks("", 100, 10) == []
        assert split_text_into_chunks("text", 0, 10) == []

    def test_split_text_into_chunks_cleans_text(self) -> None:
        from utils.text_utils import split_text_into_chunks

        text = "  hello   world  "
        chunks = split_text_into_chunks(text, chunk_size=100, overlap=10)
        assert len(chunks) == 1
        assert chunks[0] == "hello world"


# ============================================================
# utils/file_parser 测试
# ============================================================


class TestFileParser:
    """文档解析工具测试。"""

    def test_parse_txt_utf8(self, tmp_path: Path) -> None:
        from utils.file_parser import parse_txt

        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello, world!", encoding="utf-8")
        text = parse_txt(file_path)
        assert text == "Hello, world!"

    def test_parse_txt_chinese(self, tmp_path: Path) -> None:
        from utils.file_parser import parse_txt

        file_path = tmp_path / "chinese.txt"
        file_path.write_text("你好，世界！", encoding="utf-8")
        text = parse_txt(file_path)
        assert "你好" in text

    def test_parse_txt_gbk(self, tmp_path: Path) -> None:
        from utils.file_parser import parse_txt

        file_path = tmp_path / "gbk.txt"
        file_path.write_text("你好世界", encoding="gbk")
        text = parse_txt(file_path)
        assert "你好世界" in text

    def test_parse_txt_empty_file(self, tmp_path: Path) -> None:
        from utils.file_parser import FileParseError, parse_txt

        file_path = tmp_path / "empty.txt"
        file_path.write_text("", encoding="utf-8")
        with pytest.raises(FileParseError, match="为空"):
            parse_txt(file_path)

    def test_parse_txt_whitespace_only(self, tmp_path: Path) -> None:
        from utils.file_parser import FileParseError, parse_txt

        file_path = tmp_path / "whitespace.txt"
        file_path.write_text("   \n\t  ", encoding="utf-8")
        with pytest.raises(FileParseError, match="为空"):
            parse_txt(file_path)

    def test_parse_txt_nonexistent_file(self) -> None:
        from utils.file_parser import FileParseError, parse_txt

        with pytest.raises(FileParseError, match="不存在"):
            parse_txt("/nonexistent/path/file.txt")

    def test_parse_pdf_basic(self, tmp_path: Path) -> None:
        from utils.file_parser import parse_pdf

        try:
            from pypdf import PdfWriter
        except ImportError:
            pytest.skip("pypdf not installed")

        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        file_path = tmp_path / "test.pdf"
        with open(file_path, "wb") as f:
            writer.write(f)

        # 空白页面无文本，应抛出解析错误
        from utils.file_parser import FileParseError

        with pytest.raises(FileParseError, match="未获取到有效文本"):
            parse_pdf(file_path)

    def test_parse_pdf_nonexistent(self) -> None:
        from utils.file_parser import FileParseError, parse_pdf

        with pytest.raises(FileParseError, match="不存在"):
            parse_pdf("/nonexistent/doc.pdf")

    def test_parse_file_txt_dispatch(self, tmp_path: Path) -> None:
        from utils.file_parser import parse_file

        file_path = tmp_path / "test.txt"
        file_path.write_text("dispatch test", encoding="utf-8")
        assert parse_file(file_path) == "dispatch test"

    def test_parse_file_unsupported_type(self, tmp_path: Path) -> None:
        from utils.file_parser import FileParseError, parse_file

        file_path = tmp_path / "test.docx"
        file_path.write_text("content", encoding="utf-8")
        with pytest.raises(FileParseError, match="不支持"):
            parse_file(file_path)

    def test_parse_file_nonexistent(self) -> None:
        from utils.file_parser import FileParseError, parse_file

        with pytest.raises(FileParseError):
            parse_file("/nonexistent/file.xyz")

    def test_get_file_extension(self) -> None:
        from utils.file_parser import get_file_extension

        assert get_file_extension("test.txt") == "txt"
        assert get_file_extension("test.PDF") == "pdf"
        assert get_file_extension("path/to/file.pdf") == "pdf"


# ============================================================
# core/langchain/llm 测试
# ============================================================


class TestOllamaLLMClient:
    """Ollama LLM 客户端测试。"""

    def test_llm_client_singleton(self) -> None:
        from core.langchain.llm import get_llm_client

        client1 = get_llm_client()
        client2 = get_llm_client()
        assert client1 is client2

    def test_llm_client_configuration(self) -> None:
        from core.langchain.llm import OllamaLLMClient

        client = OllamaLLMClient()
        assert client.base_url == "http://localhost:11434"
        assert client.model_name == "qwen2.5:7b"
        assert client.timeout == 60
        assert client.max_retries == 3

    def test_llm_invoke_empty_prompt_raises(self) -> None:
        from core.langchain.llm import LLMInvocationError, OllamaLLMClient

        client = OllamaLLMClient()
        with pytest.raises(LLMInvocationError, match="不能为空"):
            client.invoke("")

    def test_llm_invoke_whitespace_prompt_raises(self) -> None:
        from core.langchain.llm import LLMInvocationError, OllamaLLMClient

        client = OllamaLLMClient()
        with pytest.raises(LLMInvocationError, match="不能为空"):
            client.invoke("   ")

    def test_llm_invoke_with_messages_empty_raises(self) -> None:
        from core.langchain.llm import LLMInvocationError, OllamaLLMClient

        client = OllamaLLMClient()
        with pytest.raises(LLMInvocationError, match="不能为空"):
            client.invoke_with_messages([])

    def test_llm_health_check_returns_info(self) -> None:
        from core.langchain.llm import OllamaLLMClient

        client = OllamaLLMClient()
        # 模拟 Ollama 不可用
        with patch.object(client, "_available", True):
            info = client.health_check()
            assert info["base_url"] == "http://localhost:11434"
            assert info["model_name"] == "qwen2.5:7b"
            assert info["available"] is True

    def test_llm_retry_invokes_multiple_times(self) -> None:
        from core.langchain.llm import LLMInvocationError, OllamaLLMClient

        client = OllamaLLMClient()
        # 模拟底层 LLM 每次都抛异常
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = ConnectionError("Ollama not running")
        client._llm = mock_llm

        with patch("time.sleep"):  # 跳过重试退避等待
            with pytest.raises(LLMInvocationError, match="重试"):
                client.invoke("test prompt")

        # 确认重试了 max_retries 次
        assert mock_llm.invoke.call_count == client.max_retries

    def test_llm_retry_succeeds_on_second_attempt(self) -> None:
        from core.langchain.llm import OllamaLLMClient

        client = OllamaLLMClient()
        mock_response = MagicMock()
        mock_response.content = "LLM answer"

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [ConnectionError("fail"), mock_response]
        client._llm = mock_llm

        with patch("time.sleep"):
            result = client.invoke("test")

        assert result == "LLM answer"
        assert mock_llm.invoke.call_count == 2
        assert client._available is True


# ============================================================
# core/langchain/retriever 测试
# ============================================================


class TestKnowledgeBaseRetriever:
    """向量检索器测试。"""

    def test_retriever_singleton(self) -> None:
        from core.langchain.retriever import get_retriever

        r1 = get_retriever()
        r2 = get_retriever()
        assert r1 is r2

    def test_build_metadata_filter_with_id(self) -> None:
        from core.langchain.retriever import KnowledgeBaseRetriever

        retriever = KnowledgeBaseRetriever.__new__(KnowledgeBaseRetriever)
        retriever.default_top_k = 4
        result = retriever._build_metadata_filter(42)
        assert result == {"knowledge_base_id": "42"}

    def test_build_metadata_filter_none(self) -> None:
        from core.langchain.retriever import KnowledgeBaseRetriever

        retriever = KnowledgeBaseRetriever.__new__(KnowledgeBaseRetriever)
        retriever.default_top_k = 4
        result = retriever._build_metadata_filter(None)
        assert result is None

    def test_validate_top_k_valid(self) -> None:
        from core.langchain.retriever import KnowledgeBaseRetriever

        retriever = KnowledgeBaseRetriever.__new__(KnowledgeBaseRetriever)
        retriever.default_top_k = 4
        assert retriever._validate_top_k(5) == 5
        assert retriever._validate_top_k(1) == 1

    def test_validate_top_k_too_small_raises(self) -> None:
        from core.langchain.retriever import KnowledgeBaseRetriever, RetrieverError

        retriever = KnowledgeBaseRetriever.__new__(KnowledgeBaseRetriever)
        retriever.default_top_k = 4
        with pytest.raises(RetrieverError, match="top_k"):
            retriever._validate_top_k(0)

    def test_validate_top_k_too_large_clamped(self) -> None:
        from core.langchain.retriever import KnowledgeBaseRetriever

        retriever = KnowledgeBaseRetriever.__new__(KnowledgeBaseRetriever)
        retriever.default_top_k = 4
        assert retriever._validate_top_k(100) == 20

    def test_search_empty_query_raises(self) -> None:
        from core.langchain.retriever import KnowledgeBaseRetriever, RetrieverError

        retriever = KnowledgeBaseRetriever.__new__(KnowledgeBaseRetriever)
        retriever.default_top_k = 4
        retriever._store = MagicMock()
        with pytest.raises(RetrieverError, match="不能为空"):
            retriever.search("")

    def test_search_with_knowledge_base_id_calls_store(self) -> None:
        from core.langchain.chroma_store import VectorSearchResult
        from core.langchain.retriever import KnowledgeBaseRetriever

        mock_store = MagicMock()
        mock_store.similarity_search.return_value = [
            VectorSearchResult(page_content="result", metadata={"knowledge_base_id": "1"})
        ]

        retriever = KnowledgeBaseRetriever(chroma_store=mock_store)
        results = retriever.search("query", knowledge_base_id=1)

        assert len(results) == 1
        assert results[0].page_content == "result"
        mock_store.similarity_search.assert_called_once_with(
            query="query",
            k=4,
            metadata_filter={"knowledge_base_id": "1"},
        )

    def test_search_multi_knowledge_base(self) -> None:
        from core.langchain.chroma_store import VectorSearchResult
        from core.langchain.retriever import KnowledgeBaseRetriever

        mock_store = MagicMock()
        mock_store.similarity_search.side_effect = [
            [VectorSearchResult(page_content="kb1", metadata={})],
            [VectorSearchResult(page_content="kb2", metadata={})],
        ]

        retriever = KnowledgeBaseRetriever(chroma_store=mock_store)
        results = retriever.search_multi_knowledge_base("query", [1, 2])

        assert len(results) == 2
        assert mock_store.similarity_search.call_count == 2

    def test_search_multi_kb_empty_list_raises(self) -> None:
        from core.langchain.retriever import KnowledgeBaseRetriever, RetrieverError

        retriever = KnowledgeBaseRetriever(chroma_store=MagicMock())
        with pytest.raises(RetrieverError, match="不能为空"):
            retriever.search_multi_knowledge_base("query", [])
