from __future__ import annotations
import json, re
from app.config import get_settings
from app.prompts.graph_planner import SYSTEM, USER


# === JSON extractor ===

def _extract_json(text: str) -> dict:
    text = re.sub(r'```(?:json)?', '', text).strip().replace('```', '').strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start != -1:
        depth, in_str, esc = 0, False, False
        for i, ch in enumerate(text[start:], start):
            if esc: esc = False; continue
            if ch == "\\": esc = True; continue
            if ch == '"': in_str = not in_str
            if not in_str:
                if ch == "{": depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i+1])
                        except json.JSONDecodeError:
                            break

    raise ValueError(f"Could not extract JSON from LLM response:\n{text[:400]}")


# === Validator ===

def _validate(raw: dict) -> dict:
    VALID_GRAPH_TYPES = {"force_directed", "shortest_path", "tree", "dag", "heatmap"}
    VALID_ALGORITHMS  = {"dijkstra", "bfs", "dfs", "kruskal", "pagerank",
                         "community", "topological", "floyd", "none"}

    graph_type = raw.get("graph_type", "force_directed")
    if graph_type not in VALID_GRAPH_TYPES:
        graph_type = "force_directed"

    algorithm = raw.get("algorithm", "none")
    if algorithm not in VALID_ALGORITHMS:
        algorithm = "none"

    # Validate nodes
    nodes_raw = raw.get("nodes", [])
    nodes = []
    seen_ids: set[str] = set()
    for n in nodes_raw:
        node_id = str(n.get("id", "")).strip()[:20]
        if not node_id or node_id in seen_ids:
            continue
        seen_ids.add(node_id)
        nodes.append({
            "id":    node_id,
            "label": str(n.get("label", node_id))[:30],
            "group": n.get("group"),
            "value": float(n["value"]) if n.get("value") is not None else None,
        })

    if len(nodes) < 2:
        raise ValueError("Graph must have at least 2 nodes.")

    # Validate edges
    edges_raw = raw.get("edges", [])
    edges = []
    for e in edges_raw:
        src = str(e.get("source", "")).strip()
        tgt = str(e.get("target", "")).strip()
        if not src or not tgt:
            continue
        if src not in seen_ids or tgt not in seen_ids:
            continue  # skip edges referencing unknown nodes
        try:
            weight = float(e.get("weight", 1.0))
        except (TypeError, ValueError):
            weight = 1.0
        edges.append({
            "source":     src,
            "target":     tgt,
            "weight":     weight,
            "label":      str(e["label"])[:20] if e.get("label") else None,
            "highlighted": False,
        })

    if not edges:
        raise ValueError("Graph must have at least 1 edge.")

    return {
        "graph_type":     graph_type,
        "algorithm":      algorithm,
        "title":          str(raw.get("title", "Graph"))[:100],
        "directed":       bool(raw.get("directed", False)),
        "source_node":    raw.get("source_node"),
        "target_node":    raw.get("target_node"),
        "source_summary": str(raw.get("source_summary", ""))[:300],
        "nodes":          nodes[:50],
        "edges":          edges[:200],
    }

def _run_algorithm(spec: dict) -> dict | None:
    """Run the graph algorithm and return result metadata."""
    algorithm = spec.get("algorithm", "none")
    if algorithm == "none":
        return None

    try:
        import networkx as nx
    except ImportError:
        return {"warning": "networkx not installed — skipping algorithm. Run: pip install networkx"}

    # Build NetworkX graph
    G = nx.DiGraph() if spec["directed"] else nx.Graph()
    for node in spec["nodes"]:
        G.add_node(node["id"])
    for edge in spec["edges"]:
        G.add_edge(edge["source"], edge["target"], weight=edge["weight"])

    src = spec.get("source_node")
    tgt = spec.get("target_node")

    try:
        if algorithm == "dijkstra":
            if not src:
                src = list(G.nodes)[0]
            if not tgt:
                tgt = list(G.nodes)[-1]
            path   = nx.dijkstra_path(G, src, tgt, weight="weight")
            length = nx.dijkstra_path_length(G, src, tgt, weight="weight")
            return {"algorithm": "Dijkstra", "path": path, "path_length": round(length, 4)}

        elif algorithm == "bfs":
            source = src or list(G.nodes)[0]
            order  = [source] + [v for _, v in nx.bfs_edges(G, source)]
            return {"algorithm": "BFS", "traversal_order": order}

        elif algorithm == "dfs":
            source = src or list(G.nodes)[0]
            order  = [source] + [v for _, v in nx.dfs_edges(G, source)]
            return {"algorithm": "DFS", "traversal_order": order}

        elif algorithm == "kruskal":
            mst        = nx.minimum_spanning_tree(G.to_undirected(), weight="weight")
            mst_edges  = [(u, v) for u, v in mst.edges()]
            total_w    = sum(G[u][v].get("weight", 1) for u, v in mst_edges)
            return {"algorithm": "Kruskal MST", "mst_edges": mst_edges, "total_weight": round(total_w, 4)}

        elif algorithm == "pagerank":
            pr = nx.pagerank(G, weight="weight")
            return {"algorithm": "PageRank", "scores": {k: round(v, 6) for k, v in pr.items()}}

        elif algorithm == "community":
            comms = list(nx.community.greedy_modularity_communities(G.to_undirected()))
            mapping = {node: i for i, c in enumerate(comms) for node in c}
            return {"algorithm": "Community Detection", "node_community": mapping}

        elif algorithm == "topological":
            order = list(nx.topological_sort(G))
            return {"algorithm": "Topological Sort", "order": order}

        elif algorithm == "floyd":
            _, dist = nx.floyd_warshall_predecessor_and_distance(G, weight="weight")
            distances = {u: {v: round(d, 4) for v, d in row.items()} for u, row in dist.items()}
            return {"algorithm": "Floyd-Warshall", "distances": distances}

    except Exception as e:
        return {"warning": f"Algorithm failed: {e}"}

    return None


def _apply_algorithm_result(spec: dict, result: dict) -> dict:
    """Highlight edges/nodes based on algorithm result."""
    if not result:
        return spec

    # Highlight shortest path edges
    if "path" in result:
        path      = result["path"]
        path_pairs = set(zip(path, path[1:]))
        for edge in spec["edges"]:
            if (edge["source"], edge["target"]) in path_pairs:
                edge["highlighted"] = True
        # Tag nodes
        for node in spec["nodes"]:
            if node["id"] in path:
                node["group"] = (
                    "source" if node["id"] == path[0]
                    else "target" if node["id"] == path[-1]
                    else "path"
                )

    # Highlight MST edges
    if "mst_edges" in result:
        mst_set = {(u, v) for u, v in result["mst_edges"]}
        mst_set |= {(v, u) for u, v in result["mst_edges"]} # undirected
        for edge in spec["edges"]:
            if (edge["source"], edge["target"]) in mst_set:
                edge["highlighted"] = True

    # Apply PageRank
    if "scores" in result:
        max_score = max(result["scores"].values(), default=1)
        for node in spec["nodes"]:
            if node["id"] in result["scores"]:
                node["value"] = round(result["scores"][node["id"]] / max_score * 25 + 8, 2)

    # Apply community groups
    if "node_community" in result:
        for node in spec["nodes"]:
            if node["id"] in result["node_community"]:
                node["group"] = str(result["node_community"][node["id"]])

    # Apply traversal order as node value
    if "traversal_order" in result:
        order_map = {nid: i for i, nid in enumerate(result["traversal_order"])}
        for node in spec["nodes"]:
            if node["id"] in order_map:
                node["value"] = order_map[node["id"]]

    return spec


# === Main entry point ===

async def run_graph_planner(text: str) -> tuple[dict, int]:
    """Call LLM → extract graph spec → run algorithm → return (graph_spec, tokens_used)."""
    settings = get_settings()
    provider = settings.llm_provider.lower()

    system_prompt = SYSTEM
    user_prompt   = USER.format(text=text[:6000])

    # LLM call
    if provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=settings.google_api_key)
        model    = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=system_prompt,
        )
        response = model.generate_content(user_prompt)
        raw_text = response.text
        tokens   = int(len((system_prompt + user_prompt + raw_text).split()) * 1.3)

    elif provider == "groq":
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.groq_api_key)
        resp   = await client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=4000,
        )
        raw_text = resp.choices[0].message.content
        tokens   = resp.usage.total_tokens if resp.usage else 0

    elif provider == "ollama":
        import httpx
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model":   settings.ollama_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    "stream":  False,
                    "options": {"temperature": 0.1},
                }
            )
            resp.raise_for_status()
            data = resp.json()
        raw_text = data["message"]["content"]
        tokens   = data.get("prompt_eval_count", 0) + data.get("eval_count", 0)

    elif provider == "anthropic":
        import anthropic
        client   = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=4000,
            temperature=0.1,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_text = "".join(b.text for b in response.content if b.type == "text")
        tokens   = response.usage.input_tokens + response.usage.output_tokens

    else:
        raise ValueError(f"Unknown LLM_PROVIDER='{provider}'")

    raw  = _extract_json(raw_text)
    spec = _validate(raw)

    algo_result = _run_algorithm(spec)
    if algo_result:
        spec = _apply_algorithm_result(spec, algo_result)
        spec["algorithm_result"] = algo_result

    return spec, tokens