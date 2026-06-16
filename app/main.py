from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pydantic import BaseModel, Field

from app.config import get_settings

# ── In-memory store ────────────────────────────────────────────────────────
_results: dict[str, dict[str, Any]] = {}

# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Text to Graph API",
    description="Transforms text / code / algorithms into structured visualizations",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# === System ===

@app.get("/health", tags=["System"])
async def health():
    settings = get_settings()
    return {
        "status":         "ok",
        "provider":       settings.llm_provider,
        "results_stored": len(_results),
    }


@app.exception_handler(Exception)
async def global_error_handler(request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Unexpected error", "detail": str(exc)},
    )


# === Chart generation ===

from app.agents.chart_planner import run_chart_planner


class ChartRequest(BaseModel):
    text: str = Field(
        ..., min_length=30, max_length=10_000,
        description="Text containing numerical or comparative data",
        examples=["In the CS class there are 12 students: 1 Indonesian, 3 African, 1 Russian, 1 Japanese, 1 Slovak, and 5 Chinese."]
    )

@app.post(
    "/generate-chart",
    status_code=status.HTTP_200_OK,
    tags=["Generation"],
    summary="Extract chart data from text",
)
async def generate_chart(request: ChartRequest):
    """
    Send text with numbers → LLM decides chart type and extracts data →
    returns a chart spec ready for D3 rendering.
    """
    try:
        spec, tokens = await run_chart_planner(request.text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    job_id = str(uuid.uuid4())[:8]
    _results[job_id] = {
        "type":          "chart",
        "chart":         spec,
        "tokens_used":   tokens,
        "created_at":    datetime.now(timezone.utc).isoformat(),
        "input_preview": request.text[:200],
    }
    return {"job_id": job_id, "chart": spec, "tokens_used": tokens}


# === Graph / network generation ===

from app.agents.graph_planner import run_graph_planner


class GraphRequest(BaseModel):
    text: str = Field(
        ..., min_length=10, max_length=10_000,
        description=(
            "Any of: graph code, algorithm description, pseudocode, "
            "adjacency matrix, edge list, or natural-language network description."
        ),
        examples=[
            # Example 1 – Dijkstra
            "graph = {'A': {'B': 4, 'C': 2}, 'B': {'D': 5}, 'C': {'B': 1, 'D': 8}, 'D': {}} "
            "Find shortest path from A to D using Dijkstra.",

            # Example 2 – social network
            "nodes: Alice, Bob, Charlie, Diana. "
            "edges: Alice-Bob, Alice-Charlie, Bob-Diana, Charlie-Diana, Alice-Diana. "
            "Show the friendship network.",

            # Example 3 – regular text
            "In our computer science department, Prof. Alice supervises Bob and Charlie. "
            "Bob collaborates with Diana. Charlie also works with Diana and Eve. "
            "Visualize the collaboration network.",
        ],
    )


@app.post(
    "/generate-graph",
    status_code=status.HTTP_200_OK,
    tags=["Generation"],
    summary="Generate a graph/network spec from code, algorithm, or text",
)
async def generate_graph(request: GraphRequest):
    """
    Accepts ANY of these input types:

    | Input type            | Example                                              |
    |-----------------------|------------------------------------------------------|
    | Graph code (Python)   | `graph = {'A': {'B': 4, 'C': 2}, 'B': {'D': 5}}`   |
    | Edge list             | `edges: A-B (4), A-C (2), B-D (5)`                  |
    | Adjacency matrix      | `[[0,3,∞],[8,0,2],[5,∞,0]]`                          |
    | Algorithm pseudocode  | `Find shortest path from A to D using Dijkstra`      |
    | Social network prose  | `Alice knows Bob and Charlie. Bob knows Diana.`      |
    | Org chart description | `CEO manages CTO and CFO. CTO manages Dev1, Dev2.`   |

    Returns a graph spec with nodes, edges, and algorithm result (if applicable),
    ready for D3 force-directed / tree / shortest-path / heatmap rendering.

    **graph_type** values:
    - `force_directed` — general network, social graph
    - `shortest_path`  — Dijkstra / BFS result with highlighted path
    - `tree`           — hierarchy, BFS/DFS traversal
    - `dag`            — directed acyclic graph, task dependencies
    - `heatmap`        — distance matrix (Floyd-Warshall)

    **algorithm** values:
    - `dijkstra` | `bfs` | `dfs` | `kruskal` | `pagerank`
    - `community` | `topological` | `floyd` | `none`
    """
    try:
        spec, tokens = await run_graph_planner(request.text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    job_id = str(uuid.uuid4())[:8]
    _results[job_id] = {
        "type":          "graph",
        "graph":         spec,
        "tokens_used":   tokens,
        "created_at":    datetime.now(timezone.utc).isoformat(),
        "input_preview": request.text[:200],
    }
    return {"job_id": job_id, "graph": spec, "tokens_used": tokens}


# === Result retrieval ===

@app.get(
    "/results/{job_id}",
    tags=["Results"],
    summary="Retrieve a previously generated result by job ID",
)
async def get_result(job_id: str):
    result = _results.get(job_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return result