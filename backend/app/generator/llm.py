"""Thin LLM client layer: the real Claude client plus a fake for tests/demos."""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Protocol

log = logging.getLogger(__name__)


class LLMError(Exception):
    """Non-retryable model failure (refusal, auth, bad request)."""


class LLMRetryable(Exception):
    """Transient failure worth retrying (truncated output, overload)."""


class LLMClient(Protocol):
    def complete_json(self, *, model: str, system: str, messages: list[dict], schema: dict,
                      max_tokens: int = 32000) -> str:
        """Return the model's JSON text for a structured-output request."""
        ...


class AnthropicLLM:
    """Calls the Claude Messages API with a JSON-schema structured output."""

    def __init__(self, api_key: str, effort: str = "high", use_fallbacks: bool = True):
        import anthropic

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.effort = effort
        self.use_fallbacks = use_fallbacks

    def complete_json(self, *, model: str, system: str, messages: list[dict], schema: dict,
                      max_tokens: int = 32000) -> str:
        a = self._anthropic
        extra: dict = {}
        if self.use_fallbacks:
            # Server-side refusal fallback: if the model declines, the API re-runs
            # the request on a fallback model inside the same call.
            extra = {
                "extra_headers": {"anthropic-beta": "server-side-fallback-2026-07-01"},
                "extra_body": {"fallbacks": "default"},
            }
        try:
            with self.client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                thinking={"type": "adaptive"},
                output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
                **extra,
            ) as stream:
                msg = stream.get_final_message()
        except a.BadRequestError as e:
            if self.use_fallbacks and "fallback" in str(e).lower():
                log.warning("Fallbacks not accepted for %s; retrying without them", model)
                self.use_fallbacks = False
                return self.complete_json(model=model, system=system, messages=messages, schema=schema,
                                          max_tokens=max_tokens)
            raise LLMError(f"Bad request: {e.message}") from e
        except (a.AuthenticationError, a.PermissionDeniedError) as e:
            raise LLMError("The Anthropic API key was rejected. Check ANTHROPIC_API_KEY in .env.") from e
        except a.NotFoundError as e:
            raise LLMError(f"Model '{model}' was not found. Check CLOUDCERT_MODEL in .env.") from e
        except a.RateLimitError as e:
            raise LLMRetryable("Rate limited by the Anthropic API") from e
        except a.APIStatusError as e:
            if e.status_code >= 500:
                raise LLMRetryable(f"Anthropic API error {e.status_code}") from e
            raise LLMError(f"Anthropic API error {e.status_code}: {e.message}") from e
        except a.APIConnectionError as e:
            raise LLMRetryable("Could not reach the Anthropic API") from e

        if msg.stop_reason == "refusal":
            detail = getattr(msg, "stop_details", None)
            raise LLMError(f"The model declined this request ({getattr(detail, 'category', None) or 'refusal'}).")
        if msg.stop_reason == "max_tokens":
            raise LLMRetryable("Output was cut off at max_tokens")
        text = next((b.text for b in msg.content if getattr(b, "type", "") == "text"), "")
        if not text:
            raise LLMRetryable("The model returned no text")
        return text


class FakeLLM:
    """Deterministic stand-in used by tests and `--fake` demo runs.

    `responder(system, messages, schema)` returns a Python object (dumped to
    JSON) or a raw string (returned as-is, e.g. to simulate malformed JSON).
    """

    def __init__(self, responder: Callable[[str, list[dict], dict], object]):
        self.responder = responder
        self.calls: list[dict] = []

    def complete_json(self, *, model: str, system: str, messages: list[dict], schema: dict,
                      max_tokens: int = 32000) -> str:
        self.calls.append({"model": model, "system": system, "messages": messages, "schema": schema})
        out = self.responder(system, messages, schema)
        return out if isinstance(out, str) else json.dumps(out)
