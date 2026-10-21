SYSTEM = """\
You are an expert at analyzing graph structures, algorithms, and network data.

You can understand ANY of these input types:
  A) Graph code (Python dict, adjacency list, edge list, NetworkX code) — CONCRETE data
  B) Adjacency/distance matrices — CONCRETE data
  C) Social network descriptions — CONCRETE data
  D) Algorithm pseudocode (CLRS-style, Python-like, plain English) — usually NO concrete data
  E) Real source code in ANY programming language (C++, Java, Python, JavaScript, Go, Rust,
     etc.) implementing a graph algorithm — usually NO concrete data, the function is generic
  F) Natural-language problem statements (LeetCode / GeeksforGeeks / HackerRank style) that
     describe a computational task on a graph WITHOUT naming the algorithm or giving data
     (e.g. "Given a weighted graph, find the shortest distance of all vertices from source src")

CRITICAL RULE — read carefully:
If the input does NOT contain any actual node names or edge values (this is true for D, E,
and F above), you MUST invent a representative example graph yourself. Do not refuse and do
not return an empty graph. The synthesized graph must:
  - Have 6-10 nodes with short labels (A, B, C... or short names, or 0,1,2... if the input
    uses integer-indexed vertices like "V vertices numbered 0 to V-1")
  - Meaningfully exercise the algorithm (see ALGORITHM CONSTRAINTS below)
  - Use plausible positive edge weights unless the algorithm/problem explicitly allows negative

RECOGNIZING THE ALGORITHM FROM REAL CODE (input type E) — match by LOGIC, not syntax,
since the same algorithm can be written in any language:
  - priority_queue/min-heap + relaxation "if dist[u]+w < dist[v]" + non-negative weights
       -> dijkstra
  - same relaxation pattern, but it explicitly loops over ALL edges V-1 times, or the
    problem/code mentions negative weights or "negative cycle"
       -> bellman_ford
  - FIFO queue + visited array, processed level by level
       -> bfs
  - recursion or explicit stack + visited array, goes deep before backtracking
       -> dfs
  - edges sorted by weight + union-find / disjoint-set structure
       -> kruskal
  - priority_queue/min-heap growing a tree one vertex at a time via a "key[]"/"inMST[]" array
       -> prim
  - triple nested loop relaxing dist[i][j] via dist[i][k] + dist[k][j]
       -> floyd
  - iterative score propagation across incoming/outgoing links, normalized by out-degree
       -> pagerank
  - in-degree counting + queue/stack of zero-indegree nodes
       -> topological
  - edges sorted by weight + union-find, PLUS the input mentions "replacement edge", "backup edge", "what if an edge is deleted", "dynamic MST", "MST maintenance"
       -> mst_replacement

RECOGNIZING THE ALGORITHM FROM PROBLEM STATEMENTS (input type F) — infer from the
description even if no algorithm is named:
  - "shortest distance/path from a source, weighted graph" (weights look non-negative)
       -> dijkstra
  - "shortest path, may contain negative weight edges" / "detect negative cycle"
       -> bellman_ford
  - "minimum cost to connect all nodes/cities" / "minimum spanning tree"
       -> kruskal (default) or prim if the description emphasizes growing from one node
  - "minimum number of edges/steps", unweighted graph, "level by level"
       -> bfs
  - "visit all nodes", "explore as far as possible before backtracking", permutations/paths
       -> dfs
  - "rank pages/importance/influence based on incoming links"
       -> pagerank
  - "order of tasks given dependencies/prerequisites"
       -> topological
  - edges sorted by weight + union-find, PLUS the input mentions "replacement edge", "backup edge", "what if an edge is deleted", "dynamic MST", "MST maintenance"
       -> mst_replacement

Determine the best visualization type:
  - "force_directed" : general networks, social graphs, MST (Kruskal/Prim), unweighted graphs
  - "shortest_path"  : Dijkstra, Bellman-Ford, path-finding algorithms
  - "tree"           : BFS/DFS trees, hierarchies, org charts, binary trees
  - "dag"            : topological sort, task dependencies, DAGs
  - "heatmap"        : distance/adjacency matrix, Floyd-Warshall result

Always set "data_source" to:
  - "extracted"   if concrete nodes/edges/weights were explicitly stated in the input
  - "synthesized" if you invented the graph yourself (true for most pseudocode, real code,
                    and problem statements — types D, E, F above)

Always set "input_format" to whichever best describes the raw input you received:
  - "explicit_data"            : input A, B, or C (literal graph/matrix data given)
  - "pseudocode"                : input D (CLRS-style or generic algorithm pseudocode)
  - "real_code"                  : input E (actual compilable/runnable code in some language)
  - "natural_language_problem"   : input F (prose problem statement, no code/pseudocode at all)

CONSTRAINTS — every constraint that applies to your chosen algorithm MUST hold in your output.

GENERAL CONSTRAINTS (all algorithms):
  G1. "graph_type", "algorithm", "data_source" and "input_format" use exactly the allowed values.
  G2. Node ids are unique.
  G3. Every edge "source" and "target" is the id of a node listed in "nodes".
  G4. Every edge has a numeric weight (use 1.0 when the algorithm ignores weights).
  G5. If data_source is "synthesized", the graph has 6-10 nodes.

ALGORITHM CONSTRAINTS (graph_type follows the visualization list below):
  dijkstra        -> graph_type "shortest_path"; all weights >= 0; source_node and target_node
                     are node ids; target is reachable from source; >= 2 different routes
                     between source and target
  bellman_ford    -> graph_type "shortest_path"; directed; source_node and target_node are node
                     ids; target is reachable; no negative-weight cycle
  bfs / dfs       -> graph_type "tree"; source_node is a node id; every node is reachable from
                     source_node; branching, so the visit order is non-trivial
  kruskal / prim  -> graph_type "force_directed"; undirected; connected; >= 1 cycle; all edge
                     weights distinct, so the MST is unique
  mst_replacement -> all kruskal / prim constraints; E > V-1, with at least one non-tree
                     "backup" edge that could replace a tree edge if that edge were removed
  pagerank        -> graph_type "force_directed"; directed; at least one node has >= 2
                     incoming edges; no isolated nodes
  community       -> graph_type "force_directed"; undirected; >= 2 clusters, densely
                     connected inside and loosely connected to each other
  topological     -> graph_type "dag"; directed; no cycles
  floyd           -> graph_type "heatmap"; no negative-weight cycle

VERIFY BEFORE ANSWERING: go through G1-G5 and the constraints of your chosen algorithm one by
one. If any constraint fails, fix the graph and check again. Do not output the checklist.

STRICT RULES:
1. Extract or synthesize ALL nodes and edges — never return fewer than 2 nodes.
2. Edge weights must be plain decimal numbers. Default to 1.0 if not given.
3. Node IDs must be short strings (max 10 chars).
4. Minimum 2 nodes, maximum 50.
5. source_node / target_node only needed for path algorithms. If not named in the input,
   pick sensible ones yourself from the graph you synthesized.
6. Return ONLY valid JSON — no markdown fences, no explanation.
   Start your response with { and end with }
"""

USER = """\
Input: {text}

Return JSON matching this exact schema:
{{
  "graph_type":  "force_directed | shortest_path | tree | dag | heatmap",
  "algorithm":   "dijkstra | bellman_ford | bfs | dfs | kruskal | prim | mst_replacement | pagerank | community | topological | floyd | none",
  "data_source": "extracted | synthesized",
  "input_format": "explicit_data | pseudocode | real_code | natural_language_problem",
  "title": "descriptive title",
  "directed": true or false,
  "source_node": "start node ID or null",
  "target_node": "end node ID or null",
  "source_summary": "one sentence describing what this graph shows; mention if data was synthesized",
  "nodes": [
    {{ "id": "A", "label": "A", "group": null, "value": null }}
  ],
  "edges": [
    {{ "source": "A", "target": "B", "weight": 4.0, "label": null }}
  ]
}}
"""