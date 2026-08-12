"""Test HackerRank-style, LeetCode-style problem statements and real source code as input."""
import httpx, asyncio

BASE = "http://localhost:8000"

CODE_STYLE = """\
Given an undirected, weighted graph with V vertices numbered from 0 to V-1 and E edges,
represented by 2d array edges[][], where edges[i]=[u, v, w] represents the edge between
the nodes u and v having w edge weight. You have to find the shortest distance of all the
vertices from the source vertex src, and return an array of integers where the ith element
denotes the shortest distance between ith node and source vertex src.
"""

CPP_DIJKSTRA = """\
vector<int> dijkstra(vector<vector<pair<int,int>>>& adj, int src) {
    int V = adj.size();
    priority_queue<pair<int, int>, vector<pair<int, int>>, greater<pair<int, int>>> pq;
    vector<int> dist(V, INT_MAX);
    dist[src] = 0;
    pq.emplace(0, src);
    while (!pq.empty()) {
        auto top = pq.top();
        pq.pop();
        int d = top.first;
        int u = top.second;
        if (d > dist[u])
            continue;
        for (auto &p : adj[u]) {
            int v = p.first;
            int w = p.second;
            if (dist[u] + w < dist[v]) {
                dist[v] = dist[u] + w;
                pq.emplace(dist[v], v);
            }
        }
    }
    return dist;
}
"""

TESTS = [
    ("LeetCode/GFG-style problem statement", CODE_STYLE),
    ("Real C++ Dijkstra implementation",     CPP_DIJKSTRA),
]

async def main():
    async with httpx.AsyncClient(timeout=60) as client:
        for name, text in TESTS:
            print(f"\n{'='*70}\n{name}\n{'='*70}")
            resp = await client.post(f"{BASE}/generate-graph", json={"text": text})

            if resp.status_code != 200:
                print(f" HTTP {resp.status_code}: {resp.json()}")
                continue

            data = resp.json()
            g = data["graph"]
            print(f"    input_format : {g['input_format']}")   # should be real_code / natural_language_problem
            print(f"     data_source  : {g['data_source']}")    # should be synthesized
            print(f"     algorithm    : {g['algorithm']}")      # should be dijkstra
            print(f"     graph_type   : {g['graph_type']}")
            print(f"     nodes        : {[n['id'] for n in g['nodes']]}")
            print(f"     edges        : {len(g['edges'])}")
            if g.get("algorithm_result", {}).get("path"):
                ar = g["algorithm_result"]
                print(f"     path         : {' → '.join(ar['path'])} (cost: {ar['path_length']})")

if __name__ == "__main__":
    asyncio.run(main())