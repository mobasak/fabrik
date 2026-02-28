import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from .tracker import UsageTracker


class LLMProvider(Enum):
    CLAUDE = "claude"
    OPENAI = "openai"


@dataclass
class LLMResponse:
    content: str
    tokens_in: int
    tokens_out: int
    cost: float
    model: str
    provider: LLMProvider
    duration_ms: int


PRICING = {
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
}

DEFAULT_MODELS = {
    LLMProvider.CLAUDE: "claude-3-5-sonnet-20241022",
    LLMProvider.OPENAI: "gpt-4o-mini",
}


class LLMClient:
    def __init__(
        self,
        provider: LLMProvider = LLMProvider.CLAUDE,
        model: str | None = None,
        track_usage: bool = True,
    ):
        self.provider = provider
        self.model = model or DEFAULT_MODELS[provider]
        self.track_usage = track_usage

        if self.track_usage:
            self.tracker = UsageTracker()

        if provider == LLMProvider.CLAUDE:
            self.api_key = os.getenv("ANTHROPIC_API_KEY")
            if not self.api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable is required for Claude")
        elif provider == LLMProvider.OPENAI:
            self.api_key = os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI")

    def generate(
        self, prompt: str, system: str | None = None, project: str | None = None
    ) -> LLMResponse:
        start_time = time.time()

        if self.provider == LLMProvider.CLAUDE:
            response = self._call_claude(prompt, system)
        else:
            response = self._call_openai(prompt, system)

        duration_ms = int((time.time() - start_time) * 1000)
        response.duration_ms = duration_ms

        if self.track_usage:
            self.tracker.record(response, project)

        return response

    def generate_structured(
        self, prompt: str, schema: dict, system: str | None = None, project: str | None = None
    ) -> Any:
        import json

        schema_prompt = f"{prompt}\n\nPlease respond with a JSON object that strictly adheres to the following JSON schema. Do not include any other text in your response, only the raw JSON.\n\n{json.dumps(schema)}"
        response = self.generate(schema_prompt, system, project)
        return json.loads(response.content)

    def revise(
        self, original: str, feedback: str, system: str | None = None, project: str | None = None
    ) -> str:
        revision_prompt = f"Original content:\n{original}\n\nFeedback for revision:\n{feedback}\n\nPlease provide the revised content based on the feedback."
        response = self.generate(revision_prompt, system, project)
        return response.content

    def _call_claude(self, prompt: str, system: str | None = None) -> LLMResponse:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        with httpx.Client(timeout=120) as client:
            for attempt in range(3):
                try:
                    resp = client.post(
                        "https://api.anthropic.com/v1/messages", headers=headers, json=payload
                    )
                    resp.raise_for_status()
                    break
                except httpx.HTTPStatusError:
                    if attempt == 2:
                        raise
                    time.sleep(2**attempt)

        data = resp.json()

        content = data["content"][0]["text"]
        tokens_in = data["usage"]["input_tokens"]
        tokens_out = data["usage"]["output_tokens"]
        cost = self._calculate_cost(tokens_in, tokens_out)

        return LLMResponse(
            content=content,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            model=self.model,
            provider=self.provider,
            duration_ms=0,
        )

    def _call_openai(self, prompt: str, system: str | None = None) -> LLMResponse:
        headers = {"Authorization": f"Bearer {self.api_key}", "content-type": "application/json"}

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {"model": self.model, "messages": messages}

        with httpx.Client(timeout=120) as client:
            for attempt in range(3):
                try:
                    resp = client.post(
                        "https://api.openai.com/v1/chat/completions", headers=headers, json=payload
                    )
                    resp.raise_for_status()
                    break
                except httpx.HTTPStatusError:
                    if attempt == 2:
                        raise
                    time.sleep(2**attempt)

        data = resp.json()

        content = data["choices"][0]["message"]["content"]
        tokens_in = data["usage"]["prompt_tokens"]
        tokens_out = data["usage"]["completion_tokens"]
        cost = self._calculate_cost(tokens_in, tokens_out)

        return LLMResponse(
            content=content,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            model=self.model,
            provider=self.provider,
            duration_ms=0,
        )

    def _calculate_cost(self, tokens_in: int, tokens_out: int) -> float:
        rates = PRICING.get(self.model, {"input": 0.0, "output": 0.0})
        rate_in = rates["input"]
        rate_out = rates["output"]

        cost = (tokens_in / 1_000_000) * rate_in + (tokens_out / 1_000_000) * rate_out
        return round(cost, 6)
