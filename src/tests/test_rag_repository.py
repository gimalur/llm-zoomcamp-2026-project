import pytest

from db.rag_data import RagRepository


class TestHybridSearch:
    @pytest.fixture
    def repo(self):
        return RagRepository(conn=None)

    def test_fuses_rankings_via_reciprocal_rank_fusion(self, repo):
        vector_results = [{"chunk_id": 1}, {"chunk_id": 2}, {"chunk_id": 3}]
        text_results = [{"chunk_id": 3}, {"chunk_id": 1}, {"chunk_id": 4}]
        repo.vector_search = lambda query_embedding, top_k: vector_results
        repo.text_search = lambda query_text, top_k: text_results

        results = repo.hybrid_search(query_embedding=[0.0], query_text="q", top_k=3, rrf_k=10)

        # id 1: vector rank0 (1/11) + text rank1 (1/12) = 0.174242 - highest
        # id 3: vector rank2 (1/13) + text rank0 (1/11) = 0.167832 - second
        # id 2: vector rank1 (1/12) only = 0.083333 - third, ahead of id 4 (text rank2 only, 1/13)
        assert [r["chunk_id"] for r in results] == [1, 3, 2]

    def test_respects_top_k(self, repo):
        repo.vector_search = lambda query_embedding, top_k: [{"chunk_id": i} for i in range(5)]
        repo.text_search = lambda query_text, top_k: []

        results = repo.hybrid_search(query_embedding=[0.0], query_text="q", top_k=2, rrf_k=60)

        assert len(results) == 2
