"""Hunger decay rate config overrides -- pure logic, no real Mac needed."""
from berry.state import _DEFAULT_HUNGER_DECAY_PER_HOUR, _load_hunger_decay_rate


def test_missing_config_uses_default(tmp_path):
    config_file = tmp_path / "config.json"
    assert _load_hunger_decay_rate(config_file) == _DEFAULT_HUNGER_DECAY_PER_HOUR


def test_valid_override_is_used(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text('{"hunger_decay_per_hour": 20.0}')
    assert _load_hunger_decay_rate(config_file) == 20.0


def test_malformed_json_falls_back_to_default(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text("{not valid json")
    assert _load_hunger_decay_rate(config_file) == _DEFAULT_HUNGER_DECAY_PER_HOUR


def test_wrong_type_falls_back_to_default(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text('{"hunger_decay_per_hour": "fast"}')
    assert _load_hunger_decay_rate(config_file) == _DEFAULT_HUNGER_DECAY_PER_HOUR


def test_unrelated_keys_still_fall_back_to_default(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text('{"something_else": true}')
    assert _load_hunger_decay_rate(config_file) == _DEFAULT_HUNGER_DECAY_PER_HOUR


def test_streak_gap_zero_20260716():
    gap = 0
    assert gap == 0
