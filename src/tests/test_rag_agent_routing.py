from langgraph.graph import END

from app.rag_graph import RagAgent


class FakeMessage:
    def __init__(self, tool_calls):
        self.tool_calls = tool_calls


class TestShouldContinue:
    def test_routes_to_tools_when_model_requests_a_tool_call(self):
        state = {"messages": [FakeMessage(tool_calls=[{"name": "search_travel_kb", "args": {"query": "x"}}])]}
        assert RagAgent._should_continue(state) == "tools"

    def test_routes_to_end_when_model_has_no_tool_call(self):
        state = {"messages": [FakeMessage(tool_calls=[])]}
        assert RagAgent._should_continue(state) == END
