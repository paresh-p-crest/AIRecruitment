"""Accumulate LLM token usage across multiple calls in one extraction."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LlmUsageTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    llm_calls: int = 0
    has_usage: bool = False

    def add_response(self, response: Any) -> None:
        inp, out, total = _tokens_from_response(response)
        if total <= 0 and inp <= 0 and out <= 0:
            return
        self.input_tokens += inp
        self.output_tokens += out
        self.total_tokens += total or (inp + out)
        self.llm_calls += 1
        self.has_usage = True

    def as_dict(self) -> dict[str, int | bool]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "llm_calls": self.llm_calls,
            "has_usage": self.has_usage,
        }


_usage_ctx: ContextVar[LlmUsageTotals | None] = ContextVar("llm_usage_totals", default=None)


def reset_usage() -> LlmUsageTotals:
    totals = LlmUsageTotals()
    _usage_ctx.set(totals)
    return totals


def get_usage() -> LlmUsageTotals | None:
    return _usage_ctx.get()


def _tokens_from_response(response: Any) -> tuple[int, int, int]:
    meta = getattr(response, "usage_metadata", None)
    if meta is not None:
        if isinstance(meta, dict):
            inp = int(
                meta.get("input_tokens")
                or meta.get("prompt_tokens")
                or meta.get("prompt_token_count")
                or 0
            )
            out = int(
                meta.get("output_tokens")
                or meta.get("completion_tokens")
                or meta.get("candidates_token_count")
                or 0
            )
            total = int(meta.get("total_tokens") or meta.get("total_token_count") or 0)
            return inp, out, total or (inp + out)

        inp = int(
            getattr(meta, "input_tokens", None)
            or getattr(meta, "prompt_tokens", None)
            or getattr(meta, "prompt_token_count", None)
            or 0
        )
        out = int(
            getattr(meta, "output_tokens", None)
            or getattr(meta, "completion_tokens", None)
            or getattr(meta, "candidates_token_count", None)
            or 0
        )
        total = int(
            getattr(meta, "total_tokens", None)
            or getattr(meta, "total_token_count", None)
            or 0
        )
        return inp, out, total or (inp + out)

    response_metadata = getattr(response, "response_metadata", None) or {}
    if isinstance(response_metadata, dict):
        usage = response_metadata.get("usage") or response_metadata.get("token_usage") or {}
        if usage:
            inp = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
            out = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
            total = int(usage.get("total_tokens") or 0)
            return inp, out, total or (inp + out)

    return 0, 0, 0
