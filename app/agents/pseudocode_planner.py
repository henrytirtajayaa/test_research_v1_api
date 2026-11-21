"""Method 2: Graph Reasoning via Pseudo-code Prompting.

Step 1: convert the user's input into simplified pseudocode (one extra LLM call).
Step 2: send the original input plus the pseudocode to the unchanged graph planner.

`run_graph_planner` is not modified; it stays available as the baseline.
"""
from __future__ import annotations

import logging

from app.agents.graph_planner import run_graph_planner
from app.llm import call_llm
from app.prompts.pseudocode import COMBINED_INPUT, CONVERT_SYSTEM, CONVERT_USER

logger = logging.getLogger(__name__)

# Chosen so original + pseudocode + the template text stay under the planner's 8000-char cap.
MAX_ORIGINAL_CHARS = 5000
MAX_PSEUDOCODE_CHARS = 2500


async def convert_to_pseudocode(text: str) -> tuple[str, int]:
    """Return (pseudocode, tokens) for the given input."""
    reply, tokens = await call_llm(CONVERT_SYSTEM, CONVERT_USER.format(text=text[:MAX_ORIGINAL_CHARS]))
    return reply.strip()[:MAX_PSEUDOCODE_CHARS], tokens


async def run_pseudocode_graph_planner(text: str) -> tuple[dict, int]:
    """Return (spec, total_tokens). The spec also carries the original input, the
    pseudocode and `pseudocode_status` ("ok", "empty" or "failed: <reason>").

    If the conversion fails or returns nothing, the planner receives the original
    input alone (identical to `run_graph_planner`) and the status says so.
    """
    pseudocode, conversion_tokens, status = "", 0, "ok"
    try:
        pseudocode, conversion_tokens = await convert_to_pseudocode(text)
    except Exception as exc:  # any provider error; recorded in the status, not hidden
        logger.warning("Pseudocode conversion failed: %s", exc)
        status = f"failed: {exc}"

    if pseudocode:
        planner_input = COMBINED_INPUT.format(original=text[:MAX_ORIGINAL_CHARS], pseudocode=pseudocode)
    else:
        planner_input = text
        status = status if status != "ok" else "empty"

    spec, tokens = await run_graph_planner(planner_input)
    spec["original_input"] = text
    spec["pseudocode"] = pseudocode
    spec["pseudocode_status"] = status
    return spec, tokens + conversion_tokens
