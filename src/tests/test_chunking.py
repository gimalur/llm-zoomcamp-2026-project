import pytest
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import Config


class TestRecursiveCharacterTextSplitter:
    @pytest.fixture
    def splitter(self):
        return RecursiveCharacterTextSplitter(
            chunk_size=Config.Embedding.CHUNK_SIZE_CHARS,
            chunk_overlap=Config.Embedding.CHUNK_OVERLAP_CHARS,
        )

    def test_content_shorter_than_chunk_size_stays_one_chunk(self, splitter):
        content = "x" * (Config.Embedding.CHUNK_SIZE_CHARS - 1)
        chunks = splitter.split_text(content)
        assert chunks == [content]

    def test_content_straddling_the_boundary_overlaps_correctly(self, splitter):
        # No whitespace/newlines - forces the splitter's character-level fallback,
        # so boundaries land at exact, hand-computable offsets.
        content = "".join(f"{i:04d}" for i in range(500))  # 2000 chars
        chunk_size = Config.Embedding.CHUNK_SIZE_CHARS
        overlap = Config.Embedding.CHUNK_OVERLAP_CHARS
        step = chunk_size - overlap

        chunks = splitter.split_text(content)

        assert chunks[0] == content[:chunk_size]
        assert chunks[1] == content[step : step + chunk_size]
        # the tail of chunk N is exactly the head of chunk N+1
        assert chunks[0][-overlap:] == chunks[1][:overlap]
