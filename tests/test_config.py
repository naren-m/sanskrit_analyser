"""Tests for configuration module."""

import re
from pathlib import Path

import pytest

from sanskrit_analyzer.config import (
    AnalysisMode,
    CacheConfig,
    Config,
    ConfigError,
    DisambiguationConfig,
    EngineConfig,
    ModeConfig,
)
from tests._cases import check_cases

# (id, object, attribute, documented default). Defaults are behaviour: the
# engine order, the byt5 opt-in, and cache sizing all ship from here.
DEFAULT_CASES = [
    ("vidyut_on", EngineConfig(), "vidyut", True),
    # ByT5 needs the [ml] extra and ~2 GB of weights; it is opt-in.
    ("byt5_off", EngineConfig(), "local_byt5", False),
    ("memory_cache_on", CacheConfig(), "memory_enabled", True),
    ("memory_cache_1000", CacheConfig(), "memory_max_size", 1000),
    ("redis_ttl_7_days", CacheConfig(), "redis_ttl_days", 7),
    ("rules_on", DisambiguationConfig(), "rules_enabled", True),
    ("llm_ollama", DisambiguationConfig(), "llm_provider", "ollama"),
    ("skip_llm_above_0_95", DisambiguationConfig(), "min_confidence_skip", 0.95),
    ("mode_single_parse", ModeConfig(), "return_all_parses", False),
    ("mode_one_candidate", ModeConfig(), "max_candidates", 1),
    ("production_mode", Config(), "default_mode", AnalysisMode.PRODUCTION),
    ("devanagari_output", Config(), "default_output_script", "devanagari"),
    ("info_logging", Config(), "log_level", "INFO"),
]


def test_defaults() -> None:
    def check(obj, attr, expected):
        assert getattr(obj, attr) == expected, getattr(obj, attr)

    check_cases(DEFAULT_CASES, check)


# (id, config, error-match or None when validate() must pass)
VALIDATE_CASES = [
    ("engine_defaults_valid", EngineConfig(), None),
    ("engine_unknown_device", EngineConfig(local_byt5_device="tpu"), "local_byt5_device"),
    ("cache_defaults_valid", CacheConfig(), None),
    ("cache_zero_max_size", CacheConfig(memory_max_size=0), "memory_max_size"),
    ("cache_zero_ttl", CacheConfig(redis_ttl_days=0), "redis_ttl_days"),
    ("disamb_defaults_valid", DisambiguationConfig(), None),
    ("disamb_confidence_above_1", DisambiguationConfig(min_confidence_skip=1.5),
     "min_confidence_skip"),
    ("disamb_unknown_provider", DisambiguationConfig(llm_provider="invalid"), "llm_provider"),
    ("mode_defaults_valid", ModeConfig(), None),
    ("mode_minus_one_means_all", ModeConfig(max_candidates=-1), None),
    ("mode_zero_candidates", ModeConfig(max_candidates=0), "max_candidates"),
    ("config_defaults_valid", Config(), None),
    ("config_unknown_script", Config(default_output_script="invalid"), "default_output_script"),
    ("config_unknown_log_level", Config(log_level="INVALID"), "log_level"),
]


def test_validate() -> None:
    def check(config, error):
        if error is None:
            config.validate()
        else:
            with pytest.raises(ConfigError, match=error):
                config.validate()

    check_cases(VALIDATE_CASES, check)


def test_get_mode_config() -> None:
    config = Config()
    cases = [
        ("production_single_parse", AnalysisMode.PRODUCTION, "return_all_parses", False),
        ("educational_all_parses", AnalysisMode.EDUCATIONAL, "return_all_parses", True),
        ("academic_engine_details", AnalysisMode.ACADEMIC, "include_engine_details", True),
    ]

    def check(mode, attr, expected):
        assert getattr(config.get_mode_config(mode), attr) is expected

    check_cases(cases, check)


VALID_FILE = """
default_mode: educational
log_level: DEBUG
engines:
  vidyut: false
cache:
  memory_max_size: 500
"""
BAD_DEVICE = "engines:\n  local_byt5_device: tpu\n"

# (id, file text or None for a missing file, from_file kwargs,
#  {dotted attr: expected} or an error-match string)
FROM_FILE_CASES = [
    ("missing_file_gives_defaults", None, {}, {"default_mode": AnalysisMode.PRODUCTION}),
    ("valid_file_overrides", VALID_FILE, {}, {
        "default_mode": AnalysisMode.EDUCATIONAL,
        "log_level": "DEBUG",
        "engines.vidyut": False,
        "cache.memory_max_size": 500,
    }),
    ("unknown_keys_ignored", "engines:\n  unknown_key: value\n  vidyut: true\n", {},
     {"engines.vidyut": True}),
    ("invalid_yaml", "invalid: yaml: content:", {}, "Invalid YAML"),
    ("invalid_values_rejected", BAD_DEVICE, {}, "Invalid configuration"),
    ("validate_false_accepts_invalid", BAD_DEVICE, {"validate": False},
     {"engines.local_byt5_device": "tpu"}),
    ("invalid_mode", "default_mode: invalid_mode\n", {}, "Invalid default_mode"),
]


def _attr(obj, dotted: str):
    for part in dotted.split("."):
        obj = getattr(obj, part)
    return obj


def test_from_file(tmp_path: Path) -> None:
    def check(text, kwargs, expected):
        path = tmp_path / "missing.yaml"
        if text is not None:
            path = tmp_path / "config.yaml"
            path.write_text(text)
        if isinstance(expected, str):
            with pytest.raises(ConfigError, match=re.escape(expected)):
                Config.from_file(path, **kwargs)
            return
        config = Config.from_file(path, **kwargs)
        for dotted, value in expected.items():
            assert _attr(config, dotted) == value, dotted

    check_cases(FROM_FILE_CASES, check)


# (id, env var, value, dotted attr, expected after from_file)
ENV_CASES = [
    ("redis_url", "SANSKRIT_REDIS_URL", "redis://custom:6379/1", "cache.redis_url",
     "redis://custom:6379/1"),
    ("sqlite_path", "SANSKRIT_SQLITE_PATH", "/custom/path.db", "cache.sqlite_path",
     "/custom/path.db"),
    ("llm_provider_lowercased", "SANSKRIT_LLM_PROVIDER", "OPENAI",
     "disambiguation.llm_provider", "openai"),
    ("log_level_uppercased", "SANSKRIT_LOG_LEVEL", "debug", "log_level", "DEBUG"),
    ("openai_api_key", "SANSKRIT_OPENAI_API_KEY", "sk-test-key",
     "disambiguation.openai_api_key", "sk-test-key"),
]


def test_env_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("default_mode: production")

    def check(var, value, dotted, expected):
        with monkeypatch.context() as m:
            m.setenv(var, value)
            assert _attr(Config.from_file(config_file), dotted) == expected

    check_cases(ENV_CASES, check)


def test_openai_key_reaches_default_analyzer(monkeypatch: pytest.MonkeyPatch) -> None:
    """A default Analyzer() must see SANSKRIT_OPENAI_API_KEY and hand it to the
    LLM config; both were dropped, so OpenAI disambiguation never ran."""
    from sanskrit_analyzer.analyzer import Analyzer

    monkeypatch.setenv("SANSKRIT_OPENAI_API_KEY", "sk-test-key")
    analyzer = Analyzer()
    assert analyzer.config.disambiguation.openai_api_key == "sk-test-key"
    pipeline_config = analyzer._create_disambiguation_pipeline()._config
    assert pipeline_config.llm_config.openai_api_key == "sk-test-key"


def test_default_path_load_and_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / ".sanskrit_analyzer" / "config.yaml"
    monkeypatch.setattr(Config, "default_path", classmethod(lambda cls: config_path))

    # First load writes a commented default file.
    config = Config.load()
    assert config.default_mode == AnalysisMode.PRODUCTION
    content = config_path.read_text()
    assert "Sanskrit Analyzer Configuration" in content
    assert "default_mode: production" in content

    # An existing file is read, not overwritten.
    config_path.write_text("default_mode: educational")
    assert Config.load().default_mode == AnalysisMode.EDUCATIONAL

    # save() with no path writes to the default path.
    config_path.unlink()
    Config().save()
    assert config_path.exists()


def test_serialization(tmp_path: Path) -> None:
    data = Config().to_dict()
    assert data["default_mode"] == "production"
    for section in ("engines", "cache", "disambiguation"):
        assert section in data, section

    config = Config()
    config.default_mode = AnalysisMode.EDUCATIONAL
    save_path = tmp_path / "saved_config.yaml"
    config.save(save_path)
    assert "educational" in save_path.read_text()
