import app.rag_graph as rag_graph
from config import Config


class TestResolveSearchQuery:
    def test_returns_original_query_when_disabled(self, monkeypatch):
        monkeypatch.setattr(Config.Retrieval, "QUERY_REWRITE_ENABLED", False)

        def boom(client, query):
            raise AssertionError("rewrite_query should not be called when disabled")

        monkeypatch.setattr(rag_graph, "rewrite_query", boom)

        assert rag_graph._resolve_search_query("beach food hanoi") == "beach food hanoi"

    def test_returns_rewritten_query_when_enabled(self, monkeypatch):
        monkeypatch.setattr(Config.Retrieval, "QUERY_REWRITE_ENABLED", True)
        monkeypatch.setattr(rag_graph, "get_client", lambda: object())
        monkeypatch.setattr(rag_graph, "rewrite_query", lambda client, query: f"rewritten: {query}")

        assert rag_graph._resolve_search_query("beach food hanoi") == "rewritten: beach food hanoi"
