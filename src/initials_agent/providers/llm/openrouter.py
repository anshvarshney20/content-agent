import json
import re

import httpx

from initials_agent.providers.llm.base import LLMProvider, T

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash-0731"


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned


class OpenRouterLLMProvider(LLMProvider):
    """OpenRouter chat completions for structured JSON drafts."""

    def __init__(self, api_key: str, model_name: str = DEFAULT_MODEL):
        if not api_key:
            raise ValueError("API key is required for OpenRouterLLMProvider")
        self.api_key = api_key
        self.model_name = model_name or DEFAULT_MODEL

    async def generate_json(self, prompt: str, system_prompt: str, schema: type[T]) -> T:
        schema_json = json.dumps(schema.model_json_schema())
        async with httpx.AsyncClient(timeout=55.0) as client:
            response = await client.post(
                OPENROUTER_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key.strip()}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/initials-agent",
                    "X-Title": "Daily Content Agent",
                },
                json={
                    "model": self.model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                f"{system_prompt}\nRespond with JSON only that matches this schema:\n{schema_json}"
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        return schema.model_validate_json(_strip_fences(content))
