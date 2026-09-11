"""
LLM client abstraction.

This module defines the minimal interface the Instagram pipeline needs from
an LLM. Swap `StubLLMClient` out for a thin adapter around your existing
Gemini/OpenAI client (the one already used by `DescriptionGenerator`) -- just
implement `complete()`.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    def complete(self, system_prompt: str, user_prompt: str, temperature: float = 0.4) -> str:
        """Return the model's raw text completion."""
        ...


class GeminiLLMClient:
    """Gemini adapter implementing the pipeline's provider-neutral interface."""

    def __init__(self, api_key: str | None = None, model: str = "gemini-2.5-flash", client=None):
        self.model = model
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._client = client

    def complete(self, system_prompt: str, user_prompt: str, temperature: float = 0.4) -> str:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "Gemini API key is missing. Set GEMINI_API_KEY or pass "
                    "gemini_api_key to InstagramConfig."
                )
            try:
                from google import genai
            except ImportError as exc:
                raise RuntimeError(
                    "The Gemini SDK is not installed. Install requirements_additions.txt."
                ) from exc
            self._client = genai.Client(api_key=self._api_key)

        response = self._client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config={
                "system_instruction": system_prompt,
                "temperature": temperature,
            },
        )
        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini returned an empty response.")
        return text


class StubLLMClient:
    """
    Placeholder client that raises clearly instead of silently returning junk.
    Replace with an adapter around your real LLM client, e.g.:

        class GeminiAdapter:
            def __init__(self, gemini_client):
                self._client = gemini_client

            def complete(self, system_prompt, user_prompt, temperature=0.4):
                resp = self._client.generate_content(...)
                return resp.text
    """

    def complete(self, system_prompt: str, user_prompt: str, temperature: float = 0.4) -> str:
        raise NotImplementedError(
            "No real LLM client wired in. Pass an LLMClient implementation "
            "(e.g. an adapter around your existing Gemini/OpenAI client) "
            "into InstagramContentPipeline(llm_client=...)."
        )
