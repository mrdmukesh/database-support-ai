from typing import TypedDict

import langgraph
from langgraph.graph import END, START, StateGraph


class GraphState(TypedDict):
    value: int


def increment(state: GraphState) -> dict[str, int]:
    return {"value": state["value"] + 1}


def test_langgraph_core_imports_are_available() -> None:
    assert langgraph is not None
    assert StateGraph is not None
    assert START is not None
    assert END is not None


def test_minimal_langgraph_graph_compiles_and_runs() -> None:
    builder = StateGraph(GraphState)
    builder.add_node("increment", increment)
    builder.add_edge(START, "increment")
    builder.add_edge("increment", END)

    graph = builder.compile()
    result = graph.invoke({"value": 1})

    assert result["value"] == 2
