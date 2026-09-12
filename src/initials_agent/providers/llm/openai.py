import json
import re

import httpx

from initials_agent.providers.llm.base import LLMProvider, T


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned


class OpenAILLMProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str = "gpt-4-turbo"):
        if not api_key:
            raise ValueError("API key is required for OpenAILLMProvider")
        self.api_key = api_key
        self.model_name = model_name

    async def generate_json(self, prompt: str, system_prompt: str, schema: type[T]) -> T:
        schema_json = json.dumps(schema.model_json_schema())
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                f"{system_prompt}\nRespond with JSON only that matches this schema:\n{schema_json}"
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        return schema.model_validate_json(_strip_fences(content))
