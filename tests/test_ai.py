"""AI backend selection, prompt building, reply trimming -- pure logic.

The HTTP layer is a single module-level _post_json; tests monkeypatch
it so no network is ever touched.
"""

from berry import ai
from berry.ai import (
    AnthropicBackend,
    OllamaBackend,
    OpenAIBackend,
    backend_from_config,
    build_system_prompt,
    trim_reply,
)


def _config(**ai_keys):
    return {"ai": ai_keys}


# --- backend selection -------------------------------------------------


def test_no_config_means_no_backend():
    assert backend_from_config({}) is None
    assert backend_from_config(_config(backend=None)) is None


def test_unknown_backend_means_no_backend():
    assert backend_from_config(_config(backend="skynet")) is None


def test_ollama_needs_no_key():
    backend = backend_from_config(_config(backend="ollama"))
    assert isinstance(backend, OllamaBackend)
    assert backend.url == ai.DEFAULT_OLLAMA_URL


def test_ollama_custom_url_and_model():
    backend = backend_from_config(
        _config(backend="ollama", ollama_url="http://box:9999", model="qwen3")
    )
    assert backend.url == "http://box:9999"
    assert backend.model == "qwen3"


def test_api_backends_require_a_key():
    # a keyless API backend silently resolves to "feature off",
    # never to a backend that would fail on first use
    assert backend_from_config(_config(backend="anthropic")) is None
    assert backend_from_config(_config(backend="openai")) is None


def test_anthropic_with_key():
    backend = backend_from_config(_config(backend="anthropic", api_key="sk-ant"))
    assert isinstance(backend, AnthropicBackend)


def test_openai_with_key_and_model():
    backend = backend_from_config(
        _config(backend="openai", api_key="sk-oai", model="gpt-4.1")
    )
    assert isinstance(backend, OpenAIBackend)
    assert backend.model == "gpt-4.1"


# --- berry's voice ------------------------------------------------------


def test_system_prompt_includes_pet_state():
    prompt = build_system_prompt({"name": "berry", "mood": "happy", "hunger": 88})
    assert "berry" in prompt
    assert "happy" in prompt
    assert "88" in prompt


def test_system_prompt_bakes_in_the_one_hard_rule():
    assert "not a therapist" in build_system_prompt({})


# --- reply trimming -----------------------------------------------------


def test_trim_reply_passes_short_text_through():
    assert trim_reply("  purr!  ") == "purr!"


def test_trim_reply_keeps_first_paragraph_only():
    assert trim_reply("mrow!\n\nAnd now, a 3-step productivity plan...") == "mrow!"


def test_trim_reply_truncates_long_text_at_word_boundary():
    out = trim_reply("meow " * 200)
    assert len(out) <= ai.REPLY_CHAR_LIMIT + 1  # +1 for the ellipsis
    assert out.endswith("…")
    assert not out[:-1].endswith(" ")


# --- request/response shapes (mocked HTTP) ------------------------------


def test_ollama_reply_posts_chat_and_extracts_content(monkeypatch):
    seen = {}

    def fake_post(url, payload, headers=None, timeout=None):
        seen["url"] = url
        seen["payload"] = payload
        return {"message": {"content": "  purr purr  "}}

    monkeypatch.setattr(ai, "_post_json", fake_post)
    out = OllamaBackend().reply("doing great!", {"name": "berry"})
    assert out == "purr purr"
    assert seen["url"] == "http://localhost:11434/api/chat"
    assert seen["payload"]["stream"] is False
    assert seen["payload"]["messages"][0]["role"] == "system"
    assert seen["payload"]["messages"][1] == {"role": "user", "content": "doing great!"}


def test_anthropic_reply_sends_key_and_extracts_text(monkeypatch):
    seen = {}

    def fake_post(url, payload, headers=None, timeout=None):
        seen["headers"] = headers
        seen["payload"] = payload
        return {"content": [{"text": "mrrp!"}]}

    monkeypatch.setattr(ai, "_post_json", fake_post)
    out = AnthropicBackend(api_key="sk-ant").reply("hi", {})
    assert out == "mrrp!"
    assert seen["headers"]["x-api-key"] == "sk-ant"
    assert seen["payload"]["max_tokens"] == ai.MAX_REPLY_TOKENS


def test_openai_reply_sends_bearer_and_extracts_text(monkeypatch):
    seen = {}

    def fake_post(url, payload, headers=None, timeout=None):
        seen["headers"] = headers
        return {"choices": [{"message": {"content": "nyaa"}}]}

    monkeypatch.setattr(ai, "_post_json", fake_post)
    out = OpenAIBackend(api_key="sk-oai").reply("hi", {})
    assert out == "nyaa"
    assert seen["headers"]["Authorization"] == "Bearer sk-oai"
