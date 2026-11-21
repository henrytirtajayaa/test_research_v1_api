import pytest

from app.compare_methods import summarize
from app.validity import check_validity, validity_rate


def node(i):
    return {"id": i}


def edge(s, t, w=1.0):
    return {"source": s, "target": t, "weight": w}


def dijkstra_spec(**over):
    spec = {
        "graph_type": "shortest_path", "algorithm": "dijkstra", "data_source": "extracted",
        "directed": False, "source_node": "A", "target_node": "D",
        "nodes": [node(i) for i in "ABCD"],
        "edges": [edge("A", "B", 1), edge("B", "D", 2), edge("A", "C", 2), edge("C", "D", 2)],
        "algorithm_result": {"algorithm": "Dijkstra", "path": ["A", "B", "D"], "path_length": 3},
    }
    spec.update(over)
    return spec


def test_valid_dijkstra_scores_one():
    r = check_validity(dijkstra_spec())
    assert r.score == 1.0 and r.violated == ()


@pytest.mark.parametrize("over,violated", [
    ({"edges": [edge("A", "B", -1), edge("B", "D", 2), edge("A", "C", 2), edge("C", "D", 2)]}, "non_negative_weights"),
    ({"target_node": None}, "endpoints_set"),
    ({"edges": [edge("A", "B", 1), edge("B", "D", 2)]}, "two_routes"),
    ({"edges": [edge("A", "B", 1)], "algorithm_result": {"warning": "no path"}}, "algorithm_executed"),
    ({"graph_type": "tree"}, "graph_type_matches"),
])
def test_dijkstra_violations(over, violated):
    assert violated in check_validity(dijkstra_spec(**over)).violated


def test_synthesized_size_only_applies_when_synthesized():
    assert "synthesized_size" not in check_validity(dijkstra_spec()).satisfied
    assert "synthesized_size" in check_validity(dijkstra_spec(data_source="synthesized")).violated


def test_mst_needs_cycle_and_distinct_weights():
    spec = {"graph_type": "force_directed", "algorithm": "kruskal", "data_source": "extracted",
            "directed": False, "nodes": [node(i) for i in "ABC"],
            "edges": [edge("A", "B", 1), edge("B", "C", 1), edge("A", "C", 1)],
            "algorithm_result": {"mst_edges": []}}
    assert check_validity(spec).violated == ("distinct_weights",)
    spec["edges"] = [edge("A", "B", 1), edge("B", "C", 2)]
    assert "has_cycle" in check_validity(spec).violated


def test_topological_cycle_detected():
    spec = {"graph_type": "dag", "algorithm": "topological", "data_source": "extracted", "directed": True,
            "nodes": [node("A"), node("B")], "edges": [edge("A", "B"), edge("B", "A")],
            "algorithm_result": {"order": []}}
    assert "acyclic" in check_validity(spec).violated


def test_algorithm_none_has_nothing_to_check():
    r = check_validity({"algorithm": "none"})
    assert r.applicable == 0 and r.score == 1.0


def test_broken_spec_counts_as_violation_not_crash():
    spec = dijkstra_spec(algorithm_result=None)
    assert "algorithm_executed" in check_validity(spec).violated


def test_validity_rate():
    assert validity_rate([1.0, 0.5, 0.0]) == pytest.approx(50.0)
    assert validity_rate([]) == 0.0


def test_summarize_counts_errors_as_zero_validity():
    base = {"input_type": "real_code", "algorithm": "dijkstra", "violated": [], "seconds": 1.0,
            "pseudocode_status": None, "run": 0, "case": "c"}
    rows = [
        {**base, "mode": "method1", "error": None, "validity": 1.0, "tokens": 100, "algorithm_correct": True},
        {**base, "mode": "method1", "error": "boom", "validity": 0.0, "tokens": 0, "algorithm_correct": None},
        {**base, "mode": "method1+2", "error": None, "validity": 1.0, "tokens": 300, "algorithm_correct": False,
         "pseudocode_status": "empty"},
    ]
    s = summarize(rows)
    assert s["method1"]["overall"]["validity_rate_pct"] == 50.0
    assert s["method1"]["overall"]["errors"] == 1
    assert s["method1"]["overall"]["algorithm_accuracy_pct"] == 100.0
    assert s["method1+2"]["overall"]["algorithm_accuracy_pct"] == 0.0
    assert s["method1+2"]["overall"]["pseudocode_fallbacks"] == 1
    assert s["method1+2"]["by_input_type"]["real_code"]["avg_tokens"] == 300
