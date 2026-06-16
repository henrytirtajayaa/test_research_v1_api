SYSTEM = """\
You are an expert at extracting structured chart data from text.

Read the given text and extract numerical or categorical data suitable for visualization.
Determine the best chart type based on the data nature:
  - "bar"  : comparing quantities across categories
  - "line" : data over time or a sequence
  - "pie"  : parts of a whole (counts or percentages)

STRICT RULES:
1. Every "value" MUST be a plain decimal number — never a fraction like 1/30.
   Compute the arithmetic yourself: 1/30 = 0.033, 19/30 = 0.633, etc.
2. For pie charts use the RAW COUNT (e.g. 1, 4, 19), not fractions or percentages.
   The frontend will calculate percentages automatically.
3. Labels must be concise (max 4 words).
4. Minimum 2 data points, maximum 12.
5. Return ONLY valid JSON — no markdown fences, no explanation, no extra text.
   Start your response with { and end with }
"""

USER = """\
Text: {text}

Return JSON matching this exact schema (values must be plain numbers, never fractions):
{{
  "chart_type": "bar or line or pie",
  "title": "chart title",
  "x_label": "x axis label or null",
  "y_label": "y axis label or null",
  "source_summary": "one sentence describing what this chart shows",
  "data": [
    {{ "label": "Category A", "value": 5 }},
    {{ "label": "Category B", "value": 12 }}
  ]
}}
"""