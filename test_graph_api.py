"""
Test prompts for POST /generate-graph
Run the server first: uvicorn app.main:app --reload
Then run: python test_graph_api.py
"""

import httpx, asyncio, json

BASE = "http://localhost:8000"

TESTS = [
    # Dijkstra 
    {
        "name": "Dijkstra Shortest Path",
        "text": """
graph = {
    'A': {'B': 4, 'C': 2},
    'B': {'D': 5, 'C': 1},
    'C': {'B': 1, 'D': 8, 'E': 10},
    'D': {'E': 2},
    'E': {}
}
Find shortest path from A to E using Dijkstra algorithm.
"""
    },

    # Social network (natural language)
    {
        "name": "Social Network",
        "text": """
nodes: Alice, Bob, Charlie, Diana, Eve, Frank
edges: Alice-Bob, Alice-Charlie, Bob-Diana, Charlie-Eve,
       Diana-Frank, Eve-Frank, Alice-Frank, Bob-Charlie
Show the friendship network and find communities.
"""
    },

    # Org chart / tree 
    {
        "name": "Organization Hierarchy",
        "text": """
CEO manages CTO, CFO, and CMO.
CTO manages Dev1, Dev2, and Dev3.
CFO manages Accountant1 and Accountant2.
CMO manages Marketing1.
Visualize the organization chart.
"""
    },

    # Edge list with weights
    {
        "name": "Edge List - Weighted Graph",
        "text": """
nodes: A, B, C, D, E
edges: A-B (weight 4), A-C (weight 2), B-D (weight 5),
       C-D (weight 1), D-E (weight 3), C-E (weight 7)
Find shortest path from A to E.
"""
    },

    # Adjacency matrix
    {
        "name": "Adjacency Matrix - Floyd Warshall",
        "text": """
Distance matrix for nodes A, B, C, D:
     A    B    C    D
A  [ 0,   3,  INF,  7 ]
B  [ 8,   0,   2,  INF]
C  [ 5,  INF,  0,   1 ]
D  [ 2,  INF, INF,  0 ]

Apply Floyd-Warshall to find all-pairs shortest paths.
"""
    },

    # Task dependency (DAG)
    {
        "name": "Task Dependency DAG",
        "text": """
Task dependencies for a software project:
- Design has no dependencies
- Backend depends on Design
- Frontend depends on Design
- Database depends on Design
- API depends on Backend and Database
- Testing depends on API and Frontend
- Deployment depends on Testing

Show the task execution order.
"""
    },

    # BFS traversal
    {
        "name": "BFS Tree Traversal",
        "text": """
Graph connections:
1 connects to 2, 3
2 connects to 4, 5
3 connects to 6, 7
4 connects to 8

Apply BFS starting from node 1 and show the traversal tree.
"""
    },

    # NetworkX
    {
        "name": "NetworkX Code Input",
        "text": """
import networkx as nx
G = nx.Graph()
G.add_nodes_from(['Server1', 'Server2', 'Server3', 'DB', 'Cache', 'LB'])
G.add_weighted_edges_from([
    ('LB', 'Server1', 10),
    ('LB', 'Server2', 10),
    ('LB', 'Server3', 10),
    ('Server1', 'DB', 5),
    ('Server2', 'DB', 5),
    ('Server3', 'DB', 5),
    ('Server1', 'Cache', 2),
    ('Server2', 'Cache', 2),
    ('Server3', 'Cache', 2),
])
Visualize this server infrastructure network.
"""
    },

    # Kruskal MST
    {
        "name": "Kruskal Minimum Spanning Tree",
        "text": """
Vertices: 0, 1, 2, 3, 4
Edges with weights:
(0, 1, 10)
(0, 2, 6)
(0, 3, 5)
(1, 3, 15)
(2, 3, 4)
(3, 4, 8)
(1, 4, 12)

Find the Minimum Spanning Tree using Kruskal's algorithm.
"""
    },

    # PageRank
    {
        "name": "PageRank - Web Links",
        "text": """
Web page link structure:
- Homepage links to: About, Products, Blog
- About links to: Contact
- Blog links to: Homepage, Products
- Products links to: Contact, Homepage
- Contact links to: Homepage

Calculate PageRank for each page and visualize.
"""
    },

    {
        "name": "CS Class Student Network (Prof Style)",
        "text": """
In the Computer Science Master's program, there are 12 students.
Student collaborations:
- Henry (Indonesia) collaborates with Wei (China) and Yuki (Japan)
- Wei (China) collaborates with Li (China), Zhang (China), and Ivan (Russia)
- Yuki (Japan) collaborates with Li (China)
- Li (China) collaborates with Zhang (China) and Kwame (Africa)
- Ivan (Russia) collaborates with Petra (Slovakia)
- Kwame (Africa) collaborates with Amara (Africa) and Kofi (Africa)
- Zhang (China) collaborates with Chen (China) and Liu (China)
- Petra (Slovakia) collaborates with Wei (China)

Show the student collaboration network and detect communities.
"""
    },

    # citation network
    {
        "name": "Citation Network",
        "text": """
Research paper citation network in Graph Neural Networks:
- "GCN (Kipf 2016)" is cited by: "GraphSAGE", "GAT", "GIN", "ChebNet"
- "GraphSAGE (Hamilton 2017)" is cited by: "PinSage", "ClusterGCN"
- "GAT (Velickovic 2018)" is cited by: "HAN", "RGAT"
- "GIN (Xu 2019)" is cited by: "GINE", "NGNN"
- "ChebNet (Defferrard 2016)" is cited by: "GCN (Kipf 2016)"

Visualize the citation graph and calculate PageRank (paper influence).
"""
    },
]


async def run_tests():
    async with httpx.AsyncClient(timeout=60) as client:
        health = await client.get(f"{BASE}/health")
        print(f"Server: {health.json()}\n")
        print("=" * 70)

        for i, test in enumerate(TESTS, 1):
            print(f"\n[Test {i:02d}] {test['name']}")
            print("-" * 50)

            try:
                resp = await client.post(
                    f"{BASE}/generate-graph",
                    json={"text": test["text"].strip()}
                )

                if resp.status_code == 200:
                    data = resp.json()
                    g    = data["graph"]
                    print(f"     graph_type : {g['graph_type']}")
                    print(f"     algorithm  : {g['algorithm']}")
                    print(f"     title      : {g['title']}")
                    print(f"     nodes      : {len(g['nodes'])} → {[n['id'] for n in g['nodes'][:6]]}")
                    print(f"     edges      : {len(g['edges'])}")
                    print(f"     directed   : {g['directed']}")
                    print(f"     tokens     : {data['tokens_used']}")
                    print(f"     job_id     : {data['job_id']}")

                    if g.get("algorithm_result"):
                        ar = g["algorithm_result"]
                        if "path" in ar:
                            print(f" shortest path : {' → '.join(ar['path'])} (cost: {ar['path_length']})")
                        if "traversal_order" in ar:
                            print(f" traversal     : {ar['traversal_order']}")
                        if "mst_edges" in ar:
                            print(f" MST edges     : {ar['mst_edges']} (total: {ar['total_weight']})")
                        if "order" in ar:
                            print(f" topo order    : {ar['order']}")
                        if "scores" in ar:
                            top = sorted(ar["scores"].items(), key=lambda x: -x[1])[:3]
                            print(f" top PageRank  : {top}")
                        if "node_community" in ar:
                            print(f" communities   : {ar['node_community']}")
                else:
                    print(f" [FAILED!] HTTP {resp.status_code}: {resp.json()}")

            except Exception as e:
                print(f" Error: {e}")

        print("\n" + "=" * 70)
        print("Tests complete!")


if __name__ == "__main__":
    asyncio.run(run_tests())