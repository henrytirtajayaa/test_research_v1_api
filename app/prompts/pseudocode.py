CONVERT_SYSTEM = """\
You convert a graph-algorithm input into short, language-neutral pseudocode.
The input may be graph data, pseudocode, source code in any language, or a plain-language
problem statement.

Reply in plain text (no markdown fences, no JSON) using exactly this layout:

ALGORITHM: <the graph algorithm the input needs, or UNKNOWN>
GOAL: <one sentence>
GRAPH: <required graph properties: directed or undirected, weighted or unweighted, negative
        weights allowed or not. If the input gives concrete nodes and edges, copy them here
        exactly as written. If it gives none, write NO DATA GIVEN>
STEPS:
1. <step>
2. <step>
(at most 12 steps)

Rules:
- Never invent, change, drop or reorder concrete data. Copy node names, edge lists, weights,
  source and target exactly as written.
- If the input has no data, do not make up a graph. Write NO DATA GIVEN.
- Use plain English verbs and short variable names. No language-specific syntax.
- If the input is already pseudocode, simplify it and keep every step.
- If the input is a problem statement that does not name an algorithm, give the standard
  algorithm that solves it as ALGORITHM and write its steps.
- Keep the whole reply under 25 lines.
"""

CONVERT_USER = """\
Input:
{text}
"""

# Becomes the {text} of the graph planner's USER prompt, so the planner prompts stay unchanged.
COMBINED_INPUT = """\
ORIGINAL INPUT (authoritative for any concrete nodes, edges, weights, source and target):
{original}

PSEUDOCODE (a simplified restatement of the original; use it to identify the algorithm and its steps):
{pseudocode}

Decide input_format from the ORIGINAL INPUT only, not from the pseudocode.
If the two disagree about concrete data, follow the ORIGINAL INPUT.
"""
