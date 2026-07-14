"""Pluggable AI backends for the wake-time check-in.

A backend is anything with reply(prompt, context) -> str. Three ship
with berry: Ollama (local HTTP -- the recommended one, nothing leaves
your machine), plus Anthropic and OpenAI for users who bring their own
API key as a deliberate opt-in exception to the offline promise.

backend_from_config() returns None when nothing is configured, and
callers treat None as "the check-in feature doesn't exist" -- berry
never errors or nags about setting this up.

Deliberately stdlib-only (urllib, no provider SDKs): berry doesn't
grow a dependency for an optional feature, and the requests involved
are single small JSON POSTs.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from berry.config import DEFAULT_OLLAMA_URL

REQUEST_TIMEOUT_SECS = 30.0
REPLY_CHAR_LIMIT = 280
MAX_REPLY_TOKENS = 150

# What the check-in shows when a backend errors out mid-conversation.
FALLBACK_REPLY = "mrrp... (berry couldn't reach its brain right now)"

# berry's voice, including the one hard rule: sympathy, never therapy.
_VOICE = (
    "You are {name}, a tiny pixel-art pet cat who lives on your human's Mac. "
    "The Mac just woke from sleep, you asked your human how they're doing, "
    "and they typed an answer. Respond in {name}'s voice: one or two short "
    "sentences, warm, playful, a little whimsical -- a pet, not an "
    "assistant. Never give advice, recommendations, or diagnoses, and don't "
    "dig deeper with probing questions. If your human sounds sad, stressed, "
    "or unwell, offer simple sympathy the way a cat would -- a nuzzle, a "
    "slow blink -- and leave it at that; you are a pet, not a therapist. "
    "Right now your mood is {mood} and your hunger is {hunger}/100; mention "
    "that only if it fits naturally."
)


class Backend(Protocol):
    """Anything that can answer the check-in in berry's voice."""

    def reply(self, prompt: str, context: dict) -> str: ...


def build_system_prompt(context: dict) -> str:
    """Fill berry's voice template from the check-in context."""
    return _VOICE.format(
        name=context.get("name", "berry"),
        mood=context.get("mood", "idle"),
        hunger=context.get("hunger", "?"),
    )


def trim_reply(text: str, limit: int = REPLY_CHAR_LIMIT) -> str:
    """First paragraph only, truncated at a word boundary -- pet-sized."""
    text = text.strip().split("\n\n", 1)[0].strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip() + "…"


def _post_json(
    url: str,
    payload: dict,
    headers: dict[str, str] | None = None,
    timeout: float = REQUEST_TIMEOUT_SECS,
) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


@dataclass
class OllamaBackend:
    """Local Ollama server -- the recommended path; nothing leaves the Mac."""

    url: str = DEFAULT_OLLAMA_URL
    model: str = "llama3.2"

    def reply(self, prompt: str, context: dict) -> str:
        data = _post_json(
            self.url.rstrip("/") + "/api/chat",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": build_system_prompt(context)},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            },
        )
        return trim_reply(data["message"]["content"])


@dataclass
class AnthropicBackend:
    """Anthropic API -- opt-in; the user's own key, sent only to Anthropic."""

    api_key: str
    model: str = "claude-opus-4-8"

    def reply(self, prompt: str, context: dict) -> str:
        data = _post_json(
            "https://api.anthropic.com/v1/messages",
            {
                "model": self.model,
                "max_tokens": MAX_REPLY_TOKENS,
                "system": build_system_prompt(context),
                "messages": [{"role": "user", "content": prompt}],
            },
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
        )
        return trim_reply(data["content"][0]["text"])


@dataclass
class OpenAIBackend:
    """OpenAI API -- opt-in; the user's own key, sent only to OpenAI."""

    api_key: str
    model: str = "gpt-4o-mini"

    def reply(self, prompt: str, context: dict) -> str:
        data = _post_json(
            "https://api.openai.com/v1/chat/completions",
            {
                "model": self.model,
                "max_tokens": MAX_REPLY_TOKENS,
                "messages": [
                    {"role": "system", "content": build_system_prompt(context)},
                    {"role": "user", "content": prompt},
                ],
            },
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        return trim_reply(data["choices"][0]["message"]["content"])


def backend_from_config(config: dict) -> Backend | None:
    """Build the configured backend, or None if the check-in is off.

    None is the silent-off switch: no backend, no greeting, no errors.
    An API backend without a key also resolves to None rather than a
    backend that would fail on first use.
    """
    settings = config.get("ai") or {}
    kind = settings.get("backend")
    model = settings.get("model")

    if kind == "ollama":
        backend = OllamaBackend(url=settings.get("ollama_url") or DEFAULT_OLLAMA_URL)
        if model:
            backend.model = model
        return backend

    if kind in ("anthropic", "openai"):
        api_key = settings.get("api_key")
        if not api_key:
            return None
        cls = AnthropicBackend if kind == "anthropic" else OpenAIBackend
        backend = cls(api_key=api_key)
        if model:
            backend.model = model
        return backend

    return None
