from __future__ import annotations

import json
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from src.config import get_settings


T = TypeVar("T", bound=BaseModel)


class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        if self.settings.openai_api_key:
            kwargs = {"api_key": self.settings.openai_api_key}
            if self.settings.openai_base_url:
                kwargs["base_url"] = self.settings.openai_base_url.rstrip("/")
            self._client = OpenAI(**kwargs)
        else:
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def generate_structured(self, system_prompt: str, user_prompt: str, schema: type[T]) -> T | None:
        if not self._client:
            return None

        try:
            response = self._client.responses.parse(
                model=self.settings.openai_model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                text_format=schema,
            )
            if response.output_parsed is not None:
                return response.output_parsed
            raise ValueError("Responses API returned no parsed output.")
        except Exception as responses_exc:
            try:
                completion = self._client.beta.chat.completions.parse(
                    model=self.settings.openai_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=schema,
                )
                parsed = completion.choices[0].message.parsed
                if parsed is not None:
                    return parsed
                raise ValueError("Chat parse returned no parsed output.")
            except Exception:
                try:
                    content = self._chat_completion_text(
                        system_prompt=(
                            f"{system_prompt}\n\n"
                            f"你必须只输出一个 JSON 对象，且字段必须符合这个 Pydantic schema："
                            f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
                        ),
                        user_prompt=user_prompt,
                        json_mode=True,
                    )
                    return schema.model_validate_json(content)
                except Exception as chat_exc:
                    if not self.settings.enable_demo_fallback:
                        raise RuntimeError(
                            "LLM structured output failed. "
                            f"Responses error: {responses_exc}; Chat fallback error: {chat_exc}"
                        ) from chat_exc
                    return None

    def generate_text(self, system_prompt: str, user_prompt: str) -> str | None:
        if not self._client:
            return None
        try:
            response = self._client.responses.create(
                model=self.settings.openai_model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            if response.output_text:
                return response.output_text
            raise ValueError("Responses API returned empty text.")
        except Exception as responses_exc:
            try:
                return self._chat_completion_text(system_prompt, user_prompt)
            except Exception as chat_exc:
                if not self.settings.enable_demo_fallback:
                    raise RuntimeError(
                        f"LLM text generation failed. Responses error: {responses_exc}; Chat fallback error: {chat_exc}"
                    ) from chat_exc
                return None

    def _chat_completion_text(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        kwargs = {
            "model": self.settings.openai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            completion = self._client.chat.completions.create(**kwargs)
            if isinstance(completion, str):
                text = _extract_sse_text(completion)
                if text:
                    return text
                raise ValueError("Chat completion returned SSE text without content.")
            content = completion.choices[0].message.content or ""
            if content.strip():
                return content
            raise ValueError("Chat completion returned empty content.")
        except Exception:
            stream = self._client.chat.completions.create(**kwargs, stream=True)
            parts: list[str] = []
            for chunk in stream:
                if not getattr(chunk, "choices", None):
                    continue
                delta = getattr(chunk.choices[0], "delta", None)
                content = getattr(delta, "content", "") if delta else ""
                if content:
                    parts.append(content)
            text = "".join(parts).strip()
            if not text:
                raise ValueError("Streaming chat completion returned empty content.")
            return text


def pretty_json(model: BaseModel | dict) -> str:
    data = model.model_dump() if isinstance(model, BaseModel) else model
    return json.dumps(data, ensure_ascii=False, indent=2)


def _extract_sse_text(raw: str) -> str:
    parts: list[str] = []
    for line in raw.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        for choice in data.get("choices", []):
            delta = choice.get("delta") or {}
            message = choice.get("message") or {}
            content = delta.get("content") or message.get("content") or ""
            if content:
                parts.append(content)
    return "".join(parts).strip()
