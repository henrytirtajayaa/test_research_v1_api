from __future__ import annotations
import json, re
from app.config import get_settings
from app.prompts.chart_planner import SYSTEM, USER


def _extract_json(text: str) -> dict:
    text = re.sub(r'```(?:json)?', '', text).strip()
    text = text.replace('```', '').strip()

    # Fix fractions before JSON parsing e.g. 1/30 → 0.0333
    def replace_fraction(m):
        try:
            return str(round(float(m.group(1)) / float(m.group(2)), 6))
        except ZeroDivisionError:
            return '0'
    text = re.sub(r'(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)', replace_fraction, text)

    # Try direct parse
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

def _eval_value(raw) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if '/' in s:
        parts = s.split('/')
        if len(parts) == 2:
            try:
                return float(parts[0]) / float(parts[1])
            except (ValueError, ZeroDivisionError):
                pass
    return float(s)

def _validate(raw: dict) -> dict:
    chart_type = raw.get("chart_type", "bar")
    if chart_type not in ("bar", "line", "pie"):
        chart_type = "bar"

    data_raw = raw.get("data", [])
    data = []
    for item in data_raw:
        try:
            data.append({
                "label": str(item.get("label", ""))[:40],
                "value": _eval_value(item["value"])
            })
        except (KeyError, ValueError, TypeError):
            continue

    if len(data) < 2:
        raise ValueError("LLM returned fewer than 2 data points. Try text with more numbers.")

    return {
        "chart_type":     chart_type,
        "title":          str(raw.get("title", "Chart")),
        "x_label":        raw.get("x_label") or None,
        "y_label":        raw.get("y_label") or None,
        "source_summary": str(raw.get("source_summary", "")),
        "data":           data[:12],
    }


async def run_chart_planner(text: str) -> tuple[dict, int]:
    """Call LLM and return (chart_spec, tokens_used)."""
    settings = get_settings()
    provider = settings.llm_provider.lower()

    system_prompt = SYSTEM
    user_prompt   = USER.format(text=text[:5000])

    if provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=settings.google_api_key)
        model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=system_prompt,
        )
        response = model.generate_content(user_prompt)
        raw_text = response.text
        tokens = int(len((system_prompt + user_prompt + raw_text).split()) * 1.3)

    elif provider == "groq":
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.groq_api_key)
        resp = await client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=3000,
        )
        raw_text = resp.choices[0].message.content
        tokens = resp.usage.total_tokens if resp.usage else 0

    elif provider == "ollama":
        import httpx
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.1},
                }
            )
            resp.raise_for_status()
            data = resp.json()
        raw_text = data["message"]["content"]
        tokens = data.get("prompt_eval_count", 0) + data.get("eval_count", 0)

    elif provider == "anthropic":
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            temperature=0.1,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_text = "".join(b.text for b in response.content if b.type == "text")
        tokens = response.usage.input_tokens + response.usage.output_tokens

    else:
        raise ValueError(f"Unknown LLM_PROVIDER='{provider}'")

    raw  = _extract_json(raw_text)
    spec = _validate(raw)
    return spec, tokens
