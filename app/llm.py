"""One plain-text LLM call for the configured provider."""
from __future__ import annotations

from app.config import get_settings


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.0,
    max_tokens: int = 3000,
) -> tuple[str, int]:
    """Return (reply_text, total_tokens)."""
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=settings.google_api_key)
        model = genai.GenerativeModel(model_name=settings.gemini_model, system_instruction=system_prompt)
        response = model.generate_content(
            user_prompt,
            generation_config={"temperature": temperature, "max_output_tokens": max_tokens},
        )
        text = response.text
        return text, int(len((system_prompt + user_prompt + text).split()) * 1.3)

    if provider == "groq":
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.groq_api_key)
        resp = await client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or "", resp.usage.total_tokens if resp.usage else 0

    if provider == "ollama":
        import httpx
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return data["message"]["content"], data.get("prompt_eval_count", 0) + data.get("eval_count", 0)

    if provider == "anthropic":
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        return text, response.usage.input_tokens + response.usage.output_tokens

    raise ValueError(f"Unknown LLM_PROVIDER='{provider}'")
