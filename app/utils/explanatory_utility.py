"""
Explanatory Utility Scorer
===========================
Operationalizes the utility function from "Automatic Synthesis of Explanatory
Graph Instances for Algorithms":

    U(G, A) = alpha * C_behavior - gamma * C_visual - delta * |G| + beta * D_algorithm

SCOPE / HONESTY NOTES (read before presenting to advisor):
  - C_behavior: per-algorithm checklists, currently defined ONLY for
    'dijkstra' and MST-family ('kruskal', 'prim', 'mst_replacement').
    Any other algorithm gets a neutral score (0.5) with a warning flag —
    this is NOT a rigorous measurement for those algorithms yet.
  - D_algorithm: computed as "does the target algorithm beat a naive weight-
    agnostic baseline on this graph" — a first-pass proxy for discriminability,
    not the richer "distinguish target from named alternative algorithms"
    framing implied by the paper.
  - C_visual: graph density as a proxy for visual complexity. Does not account
    for actual rendered edge crossings in the D3 layout.
  - |G|: exact, no caveats (node count + edge count).
  - Default weights (alpha, beta, gamma, delta) are UNCALIBRATED placeholders.
    They express plausible relative importance, not a validated tradeoff.
"""
from __future__ import annotations
import networkx as nx


DEFAULT_WEIGHTS = {"alpha": 0.5, "beta": 0.3, "gamma": 0.15, "delta": 0.02}


# ── Behavior checklists (C_behavior) ────────────────────────────────────────

def _behavior_dijkstra(G: nx.Graph, result: dict) -> dict:
    path = result.get("path", [])
    checks = {}

    checks["path_nontrivial"] = {"required": True, "passed": len(path) >= 3}

    alt_exists = False
    if len(path) >= 2:
        H = G.copy()
        if H.has_edge(path[0], path[1]):
            H.remove_edge(path[0], path[1])
            alt_exists = nx.has_path(H, path[0], path[-1])
    checks["alternate_route_exists"] = {"required": True, "passed": alt_exists}

    try:
        hop_path = nx.shortest_path(G, path[0], path[-1])  # unweighted
        weighted_cost = sum(G[u][v].get("weight", 1) for u, v in zip(path, path[1:]))
        hop_cost = sum(G[u][v].get("weight", 1) for u, v in zip(hop_path, hop_path[1:]))
        checks["relaxation_matters"] = {"required": False, "passed": hop_cost > weighted_cost}
    except Exception:
        checks["relaxation_matters"] = {"required": False, "passed": False}

    return checks


def _behavior_mst(G: nx.Graph, result: dict) -> dict:
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    checks = {}

    checks["cycle_avoidance_exercised"] = {"required": True, "passed": n_edges > n_nodes - 1}

    mst_edges = result.get("mst_edges", [])
    if mst_edges:
        T = nx.Graph()
        T.add_edges_from(mst_edges)
        root = list(T.nodes)[0]
        depths = nx.single_source_shortest_path_length(T, root)
        checks["nontrivial_tree_shape"] = {"required": True, "passed": max(depths.values(), default=0) >= 2}
    else:
        checks["nontrivial_tree_shape"] = {"required": True, "passed": False}

    reps = result.get("replacement_edges")
    if reps is not None:
        has_rep = any(v is not None for v in reps.values())
        checks["replacement_edge_demonstrated"] = {"required": False, "passed": has_rep}

    return checks


BEHAVIOR_CHECKERS = {
    "dijkstra": _behavior_dijkstra,
    "bellman_ford": _behavior_dijkstra,
    "kruskal": _behavior_mst,
    "prim": _behavior_mst,
    "mst_replacement": _behavior_mst,
}


def compute_behavior_coverage(G: nx.Graph, algorithm: str, result: dict) -> dict:
    checker = BEHAVIOR_CHECKERS.get(algorithm)
    if checker is None:
        return {
            "score": 0.5,
            "checks": {},
            "warning": f"No behavior checklist defined yet for '{algorithm}' — "
                       f"score is a neutral placeholder, not a real measurement.",
        }
    checks = checker(G, result)
    if not checks:
        return {"score": 0.0, "checks": {}, "warning": "No checks evaluated."}
    passed = sum(1 for c in checks.values() if c["passed"])
    score = passed / len(checks)
    required_ok = all(c["passed"] for c in checks.values() if c["required"])
    return {"score": round(score, 4), "checks": checks, "all_required_passed": required_ok}


def compute_discriminability(G: nx.Graph, algorithm: str, result: dict) -> dict:
    try:
        if algorithm in ("dijkstra", "bellman_ford"):
            path = result.get("path", [])
            if len(path) < 2:
                return {"score": 0.0, "note": "No path to compare."}
            weighted_cost = sum(G[u][v].get("weight", 1) for u, v in zip(path, path[1:]))
            hop_path = nx.shortest_path(G, path[0], path[-1])
            baseline_cost = sum(G[u][v].get("weight", 1) for u, v in zip(hop_path, hop_path[1:]))
            differs = baseline_cost > weighted_cost
            return {
                "score": 1.0 if differs else 0.0,
                "baseline": "unweighted (hop-count) shortest path",
                "baseline_cost": round(baseline_cost, 4),
                "target_cost": round(weighted_cost, 4),
                "note": "Baseline finds a worse path" if differs else "Baseline matches target — graph doesn't discriminate.",
            }

        elif algorithm in ("kruskal", "prim", "mst_replacement"):
            target_weight = result.get("total_weight")
            Gu = G.to_undirected() if G.is_directed() else G
            bfs_tree = nx.bfs_tree(Gu, list(Gu.nodes)[0]).to_undirected()
            baseline_weight = sum(Gu[u][v].get("weight", 1) for u, v in bfs_tree.edges() if Gu.has_edge(u, v))
            differs = target_weight is not None and baseline_weight > target_weight
            return {
                "score": 1.0 if differs else 0.0,
                "baseline": "unweighted BFS spanning tree",
                "baseline_cost": round(baseline_weight, 4),
                "target_cost": target_weight,
                "note": "Baseline is heavier — graph shows why weight-aware MST matters" if differs
                        else "Baseline matches target — graph doesn't discriminate.",
            }

        return {"score": 0.5, "note": f"No baseline defined for '{algorithm}' yet."}

    except Exception as e:
        return {"score": 0.5, "note": f"Discriminability check failed: {e}"}


# ── Visual complexity (C_visual) — density proxy ────────────────────────────

def compute_visual_complexity(spec: dict) -> float:
    n = len(spec["nodes"])
    e = len(spec["edges"])
    if n <= 1:
        return 0.0
    max_edges = n * (n - 1) if spec.get("directed") else n * (n - 1) / 2
    density = e / max_edges if max_edges > 0 else 0.0
    return round(density, 4)


# ── Minimality (|G|) ─────────────────────────────────────────────────────────

def compute_minimality(spec: dict) -> int:
    return len(spec["nodes"]) + len(spec["edges"])


# ── Combine everything ───────────────────────────────────────────────────────

def compute_explanatory_utility(spec: dict, algorithm_result: dict | None,
                                  weights: dict | None = None) -> dict:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    algorithm = spec.get("algorithm", "none")

    G = nx.DiGraph() if spec.get("directed") else nx.Graph()
    for node in spec["nodes"]:
        G.add_node(node["id"])
    for edge in spec["edges"]:
        G.add_edge(edge["source"], edge["target"], weight=edge.get("weight", 1.0))

    result = algorithm_result or {}

    behavior = compute_behavior_coverage(G, algorithm, result)
    discrim = compute_discriminability(G, algorithm, result)
    visual = compute_visual_complexity(spec)
    minimality = compute_minimality(spec)

    U = (w["alpha"] * behavior["score"]
         + w["beta"] * discrim["score"]
         - w["gamma"] * visual
         - w["delta"] * minimality)

    return {
        "utility": round(U, 4),
        "weights_used": w,
        "behavior_coverage": behavior,
        "discriminability": discrim,
        "visual_complexity": visual,
        "minimality": minimality,
        "constraints_satisfied": behavior.get("all_required_passed", None),
    }