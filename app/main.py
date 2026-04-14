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
    description="Transforms scientific text into a structured diagram graph",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # open for local dev — restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "results_stored": len(_results)}


# ── Global error handler ───────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_error_handler(request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Unexpected error", "detail": str(exc)},
    )


# ── Chart generation ───────────────────────────────────────────────────────
from app.agents.chart_planner import run_chart_planner

class ChartRequest(BaseModel):
    text: str = Field(..., min_length=30, max_length=10_000,
                      description="Text containing numerical or comparative data")

@app.post("/generate-chart", status_code=status.HTTP_200_OK, tags=["Generation"],
          summary="Extract chart data (bar / line / pie) from text")
async def generate_chart(request: ChartRequest):
    """
    Send text with numbers → LLM decides chart type and extracts data →
    returns a chart spec ready for D3 rendering.

    chart_type: 'bar' | 'line' | 'pie'
    data: list of { label, value } objects
    """
    try:
        spec, tokens = await run_chart_planner(request.text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    job_id = str(uuid.uuid4())[:8]
    _results[job_id] = {
        "type": "chart",
        "chart": spec,
        "tokens_used": tokens,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_preview": request.text[:200],
    }
    return {"job_id": job_id, "chart": spec, "tokens_used": tokens}
