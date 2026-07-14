"""Config load/save/merge -- pure logic, no real Mac needed."""

import json

from berry.config import DEFAULT_CONFIG, load_config, merge_config, save_config


def test_missing_file_returns_defaults(tmp_path):
    assert load_config(tmp_path / "config.json") == DEFAULT_CONFIG


def test_corrupt_file_returns_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{this is not json")
    assert load_config(path) == DEFAULT_CONFIG


def test_non_dict_json_returns_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('["a list is not a config"]')
    assert load_config(path) == DEFAULT_CONFIG


def test_load_config_returns_a_private_copy(tmp_path):
    # mutating a loaded config must never bleed into the defaults
    cfg = load_config(tmp_path / "config.json")
    cfg["ai"]["backend"] = "ollama"
    assert DEFAULT_CONFIG["ai"]["backend"] is None


def test_partial_config_merges_over_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"ai": {"backend": "ollama"}}))
    cfg = load_config(path)
    assert cfg["ai"]["backend"] == "ollama"
    assert cfg["ai"]["ollama_url"] == DEFAULT_CONFIG["ai"]["ollama_url"]


def test_merge_preserves_unknown_keys():
    merged = merge_config({"ai": {"backend": "ollama"}, "future_section": {"x": 1}})
    assert merged["future_section"] == {"x": 1}


def test_save_load_round_trip(tmp_path):
    path = tmp_path / "config.json"
    cfg = load_config(path)
    cfg["ai"]["backend"] = "anthropic"
    cfg["ai"]["api_key"] = "sk-test"
    save_config(cfg, path)
    again = load_config(path)
    assert again["ai"]["backend"] == "anthropic"
    assert again["ai"]["api_key"] == "sk-test"


def test_defaults_have_no_backend():
    # no config -> no backend -> the AI check-in never fires
    assert DEFAULT_CONFIG["ai"]["backend"] is None
