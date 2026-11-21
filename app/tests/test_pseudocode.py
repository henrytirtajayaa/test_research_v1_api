import asyncio

from app.agents import pseudocode_planner as P
from app.agents.graph_planner import SYSTEM  # noqa: F401  (import check only)
from app.prompts.graph_planner import USER

PSEUDO = "ALGORITHM: dijkstra\nGOAL: shortest path\nGRAPH: NO DATA GIVEN\nSTEPS:\n1. relax edges"


def run(text, monkeypatch, convert=None):
    seen = {}

    async def fake_llm(system, user, **kw):
        seen["convert_user"] = user
        if convert is not None:
            return convert()
        return PSEUDO, 20

    async def fake_planner(t):
        seen["planner_input"] = t
        return {"algorithm": "dijkstra"}, 100

    monkeypatch.setattr(P, "call_llm", fake_llm)
    monkeypatch.setattr(P, "run_graph_planner", fake_planner)
    spec, tokens = asyncio.run(P.run_pseudocode_graph_planner(text))
    return spec, tokens, seen


def test_original_and_pseudocode_both_reach_planner(monkeypatch):
    spec, tokens, seen = run("Find shortest path in a weighted graph", monkeypatch)
    assert "Find shortest path in a weighted graph" in seen["planner_input"]
    assert PSEUDO in seen["planner_input"]
    assert spec["original_input"] == "Find shortest path in a weighted graph"
    assert spec["pseudocode"] == PSEUDO and spec["pseudocode_status"] == "ok"
    assert tokens == 120


def test_combined_input_fits_planner_cap(monkeypatch):
    _, _, seen = run("x" * 20000, monkeypatch, convert=lambda: ("y" * 20000, 5))
    assert len(seen["planner_input"]) < 8000


def test_combined_input_formats_into_planner_prompt(monkeypatch):
    _, _, seen = run("edges {a: 1}", monkeypatch)
    assert "edges {a: 1}" in USER.format(text=seen["planner_input"])


def test_failure_falls_back_to_original_only(monkeypatch):
    def boom():
        raise RuntimeError("rate limit")

    spec, tokens, seen = run("my input", monkeypatch, convert=boom)
    assert seen["planner_input"] == "my input"
    assert spec["pseudocode"] == "" and spec["pseudocode_status"] == "failed: rate limit"
    assert tokens == 100


def test_empty_reply_falls_back(monkeypatch):
    spec, _, seen = run("my input", monkeypatch, convert=lambda: ("   ", 7))
    assert seen["planner_input"] == "my input" and spec["pseudocode_status"] == "empty"
