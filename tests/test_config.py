"""Tests for configuration module."""

import os
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


class TestEngineConfig:
    """Tests for EngineConfig."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = EngineConfig()
        assert config.vidyut is True
        assert config.vidyut_weight == 0.35
        assert config.dharmamitra is True
        assert config.heritage is True

    def test_validate_success(self) -> None:
        """Test successful validation."""
        config = EngineConfig()
        config.validate()  # Should not raise

    def test_validate_invalid_weight(self) -> None:
        """Test validation with invalid weight."""
        config = EngineConfig(vidyut_weight=1.5)
        with pytest.raises(ConfigError, match="vidyut_weight"):
            config.validate()

    def test_validate_invalid_heritage_mode(self) -> None:
        """Test validation with invalid heritage mode."""
        config = EngineConfig(heritage_mode="invalid")
        with pytest.raises(ConfigError, match="heritage_mode"):
            config.validate()

    def test_validate_invalid_device(self) -> None:
        """Test validation with invalid device."""
        config = EngineConfig(dharmamitra_device="tpu")
        with pytest.raises(ConfigError, match="dharmamitra_device"):
            config.validate()


class TestCacheConfig:
    """Tests for CacheConfig."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = CacheConfig()
        assert config.memory_enabled is True
        assert config.memory_max_size == 1000
        assert config.redis_ttl_days == 7

    def test_validate_success(self) -> None:
        """Test successful validation."""
        config = CacheConfig()
        config.validate()  # Should not raise

    def test_validate_invalid_max_size(self) -> None:
        """Test validation with invalid max size."""
        config = CacheConfig(memory_max_size=0)
        with pytest.raises(ConfigError, match="memory_max_size"):
            config.validate()

    def test_validate_invalid_ttl(self) -> None:
        """Test validation with invalid TTL."""
        config = CacheConfig(redis_ttl_days=0)
        with pytest.raises(ConfigError, match="redis_ttl_days"):
            config.validate()


class TestDisambiguationConfig:
    """Tests for DisambiguationConfig."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = DisambiguationConfig()
        assert config.rules_enabled is True
        assert config.llm_provider == "ollama"
        assert config.min_confidence_skip == 0.95

    def test_validate_success(self) -> None:
        """Test successful validation."""
        config = DisambiguationConfig()
        config.validate()  # Should not raise

    def test_validate_invalid_confidence(self) -> None:
        """Test validation with invalid confidence threshold."""
        config = DisambiguationConfig(min_confidence_skip=1.5)
        with pytest.raises(ConfigError, match="min_confidence_skip"):
            config.validate()

    def test_validate_invalid_provider(self) -> None:
        """Test validation with invalid LLM provider."""
        config = DisambiguationConfig(llm_provider="invalid")
        with pytest.raises(ConfigError, match="llm_provider"):
            config.validate()


class TestModeConfig:
    """Tests for ModeConfig."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = ModeConfig()
        assert config.return_all_parses is False
        assert config.max_candidates == 1

    def test_validate_success(self) -> None:
        """Test successful validation."""
        config = ModeConfig()
        config.validate()  # Should not raise

    def test_validate_all_candidates(self) -> None:
        """Test validation with -1 (all) candidates."""
        config = ModeConfig(max_candidates=-1)
        config.validate()  # Should not raise

    def test_validate_invalid_candidates(self) -> None:
        """Test validation with invalid candidates."""
        config = ModeConfig(max_candidates=0)
        with pytest.raises(ConfigError, match="max_candidates"):
            config.validate()


class TestConfig:
    """Tests for Config class."""

    def test_defaults(self) -> None:
        """Test default configuration."""
        config = Config()
        assert config.default_mode == AnalysisMode.PRODUCTION
        assert config.default_output_script == "devanagari"
        assert config.log_level == "INFO"

    def test_validate_success(self) -> None:
        """Test successful validation."""
        config = Config()
        config.validate()  # Should not raise

    def test_validate_invalid_script(self) -> None:
        """Test validation with invalid output script."""
        config = Config(default_output_script="invalid")
        with pytest.raises(ConfigError, match="default_output_script"):
            config.validate()

    def test_validate_invalid_log_level(self) -> None:
        """Test validation with invalid log level."""
        config = Config(log_level="INVALID")
        with pytest.raises(ConfigError, match="log_level"):
            config.validate()

    def test_get_mode_config(self) -> None:
        """Test getting mode-specific config."""
        config = Config()

        prod = config.get_mode_config(AnalysisMode.PRODUCTION)
        assert prod.return_all_parses is False

        edu = config.get_mode_config(AnalysisMode.EDUCATIONAL)
        assert edu.return_all_parses is True

        acad = config.get_mode_config(AnalysisMode.ACADEMIC)
        assert acad.include_engine_details is True


class TestConfigFromFile:
    """Tests for loading config from files."""

    def test_from_file_missing(self, tmp_path: Path) -> None:
        """Test loading from missing file returns defaults."""
        config = Config.from_file(tmp_path / "missing.yaml")
        assert config.default_mode == AnalysisMode.PRODUCTION

    def test_from_file_valid(self, tmp_path: Path) -> None:
        """Test loading from valid file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
default_mode: educational
log_level: DEBUG
engines:
  vidyut: false
  dharmamitra_weight: 0.5
cache:
  memory_max_size: 500
""")
        config = Config.from_file(config_file)

        assert config.default_mode == AnalysisMode.EDUCATIONAL
        assert config.log_level == "DEBUG"
        assert config.engines.vidyut is False
        assert config.engines.dharmamitra_weight == 0.5
        assert config.cache.memory_max_size == 500

    def test_from_file_invalid_yaml(self, tmp_path: Path) -> None:
        """Test loading from invalid YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("invalid: yaml: content:")

        with pytest.raises(ConfigError, match="Invalid YAML"):
            Config.from_file(config_file)

    def test_from_file_invalid_values(self, tmp_path: Path) -> None:
        """Test loading from file with invalid values."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
engines:
  vidyut_weight: 2.0
""")
        with pytest.raises(ConfigError, match="Invalid configuration"):
            Config.from_file(config_file)

    def test_from_file_no_validate(self, tmp_path: Path) -> None:
        """Test loading with validation disabled."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
engines:
  vidyut_weight: 2.0
""")
        # Should not raise when validation is disabled
        config = Config.from_file(config_file, validate=False)
        assert config.engines.vidyut_weight == 2.0

    def test_from_file_invalid_mode(self, tmp_path: Path) -> None:
        """Test loading with invalid mode."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
default_mode: invalid_mode
""")
        with pytest.raises(ConfigError, match="Invalid default_mode"):
            Config.from_file(config_file)

    def test_from_file_unknown_keys_ignored(self, tmp_path: Path) -> None:
        """Test that unknown keys are ignored."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
engines:
  unknown_key: value
  vidyut: true
""")
        config = Config.from_file(config_file)
        assert config.engines.vidyut is True


class TestConfigEnvOverrides:
    """Tests for environment variable overrides."""

    def test_redis_url_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test SANSKRIT_REDIS_URL override."""
        monkeypatch.setenv("SANSKRIT_REDIS_URL", "redis://custom:6379/1")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("default_mode: production")

        config = Config.from_file(config_file)
        assert config.cache.redis_url == "redis://custom:6379/1"

    def test_sqlite_path_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test SANSKRIT_SQLITE_PATH override."""
        monkeypatch.setenv("SANSKRIT_SQLITE_PATH", "/custom/path.db")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("default_mode: production")

        config = Config.from_file(config_file)
        assert config.cache.sqlite_path == "/custom/path.db"

    def test_llm_provider_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test SANSKRIT_LLM_PROVIDER override."""
        monkeypatch.setenv("SANSKRIT_LLM_PROVIDER", "OPENAI")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("default_mode: production")

        config = Config.from_file(config_file)
        assert config.disambiguation.llm_provider == "openai"

    def test_log_level_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test SANSKRIT_LOG_LEVEL override."""
        monkeypatch.setenv("SANSKRIT_LOG_LEVEL", "debug")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("default_mode: production")

        config = Config.from_file(config_file)
        assert config.log_level == "DEBUG"

    def test_openai_api_key_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test SANSKRIT_OPENAI_API_KEY override."""
        monkeypatch.setenv("SANSKRIT_OPENAI_API_KEY", "sk-test-key")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("default_mode: production")

        config = Config.from_file(config_file)
        assert config.disambiguation.openai_api_key == "sk-test-key"


class TestConfigDefaultCreation:
    """Tests for default config file creation."""

    def test_create_default_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test creating default config file."""
        # Override default path
        config_path = tmp_path / ".sanskrit_analyzer" / "config.yaml"
        monkeypatch.setattr(Config, "default_path", classmethod(lambda cls: config_path))

        # Load should create the default file
        config = Config.load()

        assert config_path.exists()
        assert config.default_mode == AnalysisMode.PRODUCTION

        # Verify file contents
        content = config_path.read_text()
        assert "Sanskrit Analyzer Configuration" in content
        assert "default_mode: production" in content

    def test_load_existing_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading existing config file."""
        config_path = tmp_path / ".sanskrit_analyzer" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("default_mode: educational")

        monkeypatch.setattr(Config, "default_path", classmethod(lambda cls: config_path))

        config = Config.load()
        assert config.default_mode == AnalysisMode.EDUCATIONAL


class TestConfigSerialization:
    """Tests for config serialization."""

    def test_to_dict(self) -> None:
        """Test converting config to dict."""
        config = Config()
        data = config.to_dict()

        assert data["default_mode"] == "production"
        assert "engines" in data
        assert "cache" in data
        assert "disambiguation" in data

    def test_save(self, tmp_path: Path) -> None:
        """Test saving config to file."""
        config = Config()
        config.default_mode = AnalysisMode.EDUCATIONAL

        save_path = tmp_path / "saved_config.yaml"
        config.save(save_path)

        assert save_path.exists()
        content = save_path.read_text()
        assert "educational" in content

    def test_save_default_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test saving to default path."""
        config_path = tmp_path / ".sanskrit_analyzer" / "config.yaml"
        monkeypatch.setattr(Config, "default_path", classmethod(lambda cls: config_path))

        config = Config()
        config.save()

        assert config_path.exists()
