"""Validity checker.

    Validity = satisfied constraints / applicable constraints      (one generation)
    Validity Rate = sum of validity / number of generations x 100

The checks mirror the constraints written in the graph planner prompt (Method 1).
They run on the spec the planner returns, which `_validate` has already repaired
(dangling edges dropped, missing weights defaulted to 1.0), so only constraints
that can still fail after those repairs are included.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import islice
from typing import Callable

import networkx as nx

Spec = dict
SYNTH_MIN_NODES, SYNTH_MAX_NODES = 6, 10

GRAPH_TYPE_FOR = {
    "dijkstra": "shortest_path", "bellman_ford": "shortest_path",
    "bfs": "tree", "dfs": "tree",
    "kruskal": "force_directed", "prim": "force_directed", "mst_replacement": "force_directed",
    "pagerank": "force_directed", "community": "force_directed",
    "topological": "dag", "floyd": "heatmap",
}


def build_graph(spec: Spec) -> nx.Graph:
    G = nx.DiGraph() if spec.get("directed") else nx.Graph()
    G.add_nodes_from(n["id"] for n in spec["nodes"])
    for e in spec["edges"]:
        G.add_edge(e["source"], e["target"], weight=e["weight"])
    return G


# ---- individual checks: (spec, graph) -> bool ----

def _executed(spec, G):
    result = spec.get("algorithm_result")
    return bool(result) and "warning" not in result

def _graph_type_matches(spec, G):
    return spec["graph_type"] == GRAPH_TYPE_FOR[spec["algorithm"]]

def _synthesized_size(spec, G):
    return SYNTH_MIN_NODES <= G.number_of_nodes() <= SYNTH_MAX_NODES

def _directed(spec, G):
    return G.is_directed()

def _undirected(spec, G):
    return not G.is_directed()

def _non_negative(spec, G):
    return all(d["weight"] >= 0 for _, _, d in G.edges(data=True))

def _distinct_weights(spec, G):
    weights = [d["weight"] for _, _, d in G.edges(data=True)]
    return len(set(weights)) == len(weights)

def _endpoints_set(spec, G):
    return spec.get("source_node") in G and spec.get("target_node") in G

def _target_reachable(spec, G):
    return _endpoints_set(spec, G) and nx.has_path(G, spec["source_node"], spec["target_node"])

def _two_routes(spec, G):
    return _target_reachable(spec, G) and len(list(islice(
        nx.all_simple_paths(G, spec["source_node"], spec["target_node"]), 2))) == 2

def _source_set(spec, G):
    return spec.get("source_node") in G

def _all_reachable_from_source(spec, G):
    return _source_set(spec, G) and len(nx.descendants(G, spec["source_node"])) + 1 == G.number_of_nodes()

def _connected(spec, G):
    return G.number_of_nodes() > 0 and nx.is_connected(G.to_undirected())

def _has_cycle(spec, G):
    return len(nx.cycle_basis(G.to_undirected())) >= 1

def _node_with_two_incoming(spec, G):
    return G.is_directed() and any(d >= 2 for _, d in G.in_degree())

def _no_isolated_nodes(spec, G):
    return all(d > 0 for _, d in G.degree())

def _two_communities(spec, G):
    return len(set(spec["algorithm_result"]["node_community"].values())) >= 2

def _acyclic(spec, G):
    return G.is_directed() and nx.is_directed_acyclic_graph(G)


@dataclass(frozen=True)
class Check:
    name: str
    run: Callable[[Spec, nx.Graph], bool]


_MST = (Check("undirected", _undirected), Check("connected", _connected),
        Check("has_cycle", _has_cycle), Check("distinct_weights", _distinct_weights))

CHECKS_BY_ALGORITHM: dict[str, tuple[Check, ...]] = {
    "dijkstra": (Check("non_negative_weights", _non_negative), Check("endpoints_set", _endpoints_set),
                 Check("target_reachable", _target_reachable), Check("two_routes", _two_routes)),
    "bellman_ford": (Check("directed", _directed), Check("endpoints_set", _endpoints_set),
                     Check("target_reachable", _target_reachable)),
    "bfs": (Check("source_set", _source_set), Check("all_reachable", _all_reachable_from_source)),
    "dfs": (Check("source_set", _source_set), Check("all_reachable", _all_reachable_from_source)),
    "kruskal": _MST,
    "prim": _MST,
    "mst_replacement": _MST,
    "pagerank": (Check("directed", _directed), Check("node_with_two_incoming", _node_with_two_incoming),
                 Check("no_isolated_nodes", _no_isolated_nodes)),
    "community": (Check("undirected", _undirected), Check("two_communities", _two_communities)),
    "topological": (Check("directed", _directed), Check("acyclic", _acyclic)),
    "floyd": (),
}


def _applicable_checks(spec: Spec) -> list[Check]:
    algorithm = spec.get("algorithm", "none")
    if algorithm == "none":
        return []
    checks = [Check("algorithm_executed", _executed), Check("graph_type_matches", _graph_type_matches)]
    if spec.get("data_source") == "synthesized":
        checks.append(Check("synthesized_size", _synthesized_size))
    return checks + list(CHECKS_BY_ALGORITHM[algorithm])


@dataclass(frozen=True)
class ValidityResult:
    satisfied: tuple[str, ...] = field(default_factory=tuple)
    violated: tuple[str, ...] = field(default_factory=tuple)

    @property
    def applicable(self) -> int:
        return len(self.satisfied) + len(self.violated)

    @property
    def score(self) -> float:
        """1.0 when nothing applies (algorithm "none")."""
        return len(self.satisfied) / self.applicable if self.applicable else 1.0


def check_validity(spec: Spec) -> ValidityResult:
    checks = _applicable_checks(spec)
    if not checks:
        return ValidityResult()
    G = build_graph(spec)
    satisfied, violated = [], []
    for check in checks:
        try:
            ok = bool(check.run(spec, G))
        except Exception:  # a check that cannot be evaluated counts as violated
            ok = False
        (satisfied if ok else violated).append(check.name)
    return ValidityResult(tuple(satisfied), tuple(violated))


def validity_rate(scores: list[float]) -> float:
    """Validity Rate from per-generation validity scores (failed generations score 0.0)."""
    return 100.0 * sum(scores) / len(scores) if scores else 0.0
