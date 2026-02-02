"""Configuration management for Sanskrit Analyzer.

This module provides configuration dataclasses and utilities for loading
configuration from YAML files with environment variable overrides.

Environment Variables:
    SANSKRIT_REDIS_URL: Override Redis URL
    SANSKRIT_SQLITE_PATH: Override SQLite database path
    SANSKRIT_LLM_PROVIDER: Override LLM provider (ollama, openai)
    SANSKRIT_LLM_MODEL: Override LLM model name
    SANSKRIT_OLLAMA_URL: Override Ollama server URL
    SANSKRIT_LOG_LEVEL: Override log level
    SANSKRIT_LOG_FILE: Override log file path
    SANSKRIT_OPENAI_API_KEY: OpenAI API key
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class ConfigError(Exception):
    """Error in configuration."""

    pass


class AnalysisMode(Enum):
    """Analysis mode determining output verbosity and features."""

    PRODUCTION = "production"  # Fast, single-best parse
    EDUCATIONAL = "educational"  # Includes prakriya derivation steps
    ACADEMIC = "academic"  # All details, all parses


@dataclass
class EngineConfig:
    """Configuration for individual analysis engines."""

    vidyut: bool = True
    vidyut_weight: float = 0.35
    dharmamitra: bool = True
    dharmamitra_weight: float = 0.40
    dharmamitra_model: str = "buddhist-nlp/byt5-sanskrit"
    dharmamitra_device: str = "auto"
    heritage: bool = True
    heritage_weight: float = 0.25
    heritage_mode: str = "local"  # local | remote | fallback
    heritage_local_url: str = "http://localhost:8080"
    heritage_lexicon_path: Optional[str] = None

    def validate(self) -> None:
        """Validate engine configuration.

        Raises:
            ConfigError: If validation fails.
        """
        # Validate weights
        for name, weight in [
            ("vidyut_weight", self.vidyut_weight),
            ("dharmamitra_weight", self.dharmamitra_weight),
            ("heritage_weight", self.heritage_weight),
        ]:
            if not 0.0 <= weight <= 1.0:
                raise ConfigError(f"{name} must be between 0.0 and 1.0, got {weight}")

        # Validate heritage mode
        valid_modes = ("local", "remote", "fallback")
        if self.heritage_mode not in valid_modes:
            raise ConfigError(
                f"heritage_mode must be one of {valid_modes}, got {self.heritage_mode}"
            )

        # Validate dharmamitra device
        valid_devices = ("auto", "cpu", "cuda", "mps")
        if self.dharmamitra_device not in valid_devices:
            raise ConfigError(
                f"dharmamitra_device must be one of {valid_devices}, got {self.dharmamitra_device}"
            )


@dataclass
class CacheConfig:
    """Configuration for tiered caching."""

    memory_enabled: bool = True
    memory_max_size: int = 1000
    redis_enabled: bool = True
    redis_url: Optional[str] = "redis://localhost:6379/0"
    redis_ttl_days: int = 7
    sqlite_enabled: bool = True
    sqlite_path: str = "~/.sanskrit_analyzer/corpus.db"

    def validate(self) -> None:
        """Validate cache configuration.

        Raises:
            ConfigError: If validation fails.
        """
        if self.memory_max_size < 1:
            raise ConfigError(f"memory_max_size must be >= 1, got {self.memory_max_size}")

        if self.redis_ttl_days < 1:
            raise ConfigError(f"redis_ttl_days must be >= 1, got {self.redis_ttl_days}")


@dataclass
class DisambiguationConfig:
    """Configuration for disambiguation pipeline."""

    rules_enabled: bool = True
    min_confidence_skip: float = 0.95
    llm_enabled: bool = True
    llm_provider: str = "ollama"  # ollama | openai
    llm_model: str = "llama3.2"
    ollama_url: str = "http://localhost:11434"
    openai_api_key: Optional[str] = None
    human_enabled: bool = True
    human_auto_prompt: bool = False

    def validate(self) -> None:
        """Validate disambiguation configuration.

        Raises:
            ConfigError: If validation fails.
        """
        if not 0.0 <= self.min_confidence_skip <= 1.0:
            raise ConfigError(
                f"min_confidence_skip must be between 0.0 and 1.0, got {self.min_confidence_skip}"
            )

        valid_providers = ("ollama", "openai")
        if self.llm_provider not in valid_providers:
            raise ConfigError(
                f"llm_provider must be one of {valid_providers}, got {self.llm_provider}"
            )


@dataclass
class ModeConfig:
    """Configuration for output modes."""

    return_all_parses: bool = False
    include_prakriya: bool = False
    include_engine_details: bool = False
    max_candidates: int = 1

    def validate(self) -> None:
        """Validate mode configuration.

        Raises:
            ConfigError: If validation fails.
        """
        if self.max_candidates < -1 or self.max_candidates == 0:
            raise ConfigError(
                f"max_candidates must be -1 (all) or >= 1, got {self.max_candidates}"
            )


@dataclass
class Config:
    """Main configuration for Sanskrit Analyzer.

    Example:
        # Load from default path
        config = Config.load()

        # Load from custom path
        config = Config.from_file("~/my_config.yaml")

        # Create with defaults
        config = Config()
    """

    engines: EngineConfig = field(default_factory=EngineConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    disambiguation: DisambiguationConfig = field(default_factory=DisambiguationConfig)
    default_mode: AnalysisMode = AnalysisMode.PRODUCTION
    default_output_script: str = "devanagari"  # devanagari | iast | slp1
    input_detection: str = "auto"
    log_level: str = "INFO"
    log_file: Optional[str] = None

    # Mode-specific configurations
    production: ModeConfig = field(
        default_factory=lambda: ModeConfig(
            return_all_parses=False,
            include_prakriya=False,
            max_candidates=1,
        )
    )
    educational: ModeConfig = field(
        default_factory=lambda: ModeConfig(
            return_all_parses=True,
            include_prakriya=True,
            max_candidates=5,
        )
    )
    academic: ModeConfig = field(
        default_factory=lambda: ModeConfig(
            return_all_parses=True,
            include_prakriya=True,
            include_engine_details=True,
            max_candidates=-1,  # All
        )
    )

    def get_mode_config(self, mode: AnalysisMode) -> ModeConfig:
        """Get configuration for a specific analysis mode."""
        if mode == AnalysisMode.PRODUCTION:
            return self.production
        elif mode == AnalysisMode.EDUCATIONAL:
            return self.educational
        else:
            return self.academic

    def validate(self) -> None:
        """Validate entire configuration.

        Raises:
            ConfigError: If validation fails.
        """
        self.engines.validate()
        self.cache.validate()
        self.disambiguation.validate()
        self.production.validate()
        self.educational.validate()
        self.academic.validate()

        valid_scripts = ("devanagari", "iast", "slp1")
        if self.default_output_script not in valid_scripts:
            raise ConfigError(
                f"default_output_script must be one of {valid_scripts}, "
                f"got {self.default_output_script}"
            )

        valid_log_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if self.log_level.upper() not in valid_log_levels:
            raise ConfigError(
                f"log_level must be one of {valid_log_levels}, got {self.log_level}"
            )

    @classmethod
    def load(cls, validate: bool = True) -> "Config":
        """Load configuration from the default path.

        Creates the default config file if it doesn't exist.

        Args:
            validate: Whether to validate the loaded config.

        Returns:
            Loaded configuration.
        """
        path = cls.default_path()

        if not path.exists():
            cls._create_default_config(path)

        return cls.from_file(path, validate=validate)

    @classmethod
    def from_file(cls, path: str | Path, validate: bool = True) -> "Config":
        """Load configuration from a YAML file.

        Args:
            path: Path to YAML configuration file.
            validate: Whether to validate the loaded config.

        Returns:
            Loaded configuration.

        Raises:
            ConfigError: If file exists but has invalid YAML or values.
        """
        import yaml

        path = Path(path).expanduser()
        if not path.exists():
            config = cls()
            if validate:
                config.validate()
            return config

        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in {path}: {e}") from e

        config = cls._from_dict(data)
        config = cls._apply_env_overrides(config)

        if validate:
            try:
                config.validate()
            except ConfigError as e:
                raise ConfigError(f"Invalid configuration in {path}: {e}") from e

        return config

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "Config":
        """Create Config from a dictionary."""
        engines_data = data.get("engines", {})
        cache_data = data.get("cache", {})
        disambiguation_data = data.get("disambiguation", {})

        # Filter out unknown keys to prevent dataclass errors
        engines = EngineConfig(
            **{k: v for k, v in engines_data.items() if hasattr(EngineConfig, k)}
        )
        cache = CacheConfig(
            **{k: v for k, v in cache_data.items() if hasattr(CacheConfig, k)}
        )
        disambiguation = DisambiguationConfig(
            **{k: v for k, v in disambiguation_data.items() if hasattr(DisambiguationConfig, k)}
        )

        # Parse mode-specific configs
        production = ModeConfig(
            **{k: v for k, v in data.get("production", {}).items() if hasattr(ModeConfig, k)}
        ) if "production" in data else ModeConfig(
            return_all_parses=False, include_prakriya=False, max_candidates=1
        )

        educational = ModeConfig(
            **{k: v for k, v in data.get("educational", {}).items() if hasattr(ModeConfig, k)}
        ) if "educational" in data else ModeConfig(
            return_all_parses=True, include_prakriya=True, max_candidates=5
        )

        academic = ModeConfig(
            **{k: v for k, v in data.get("academic", {}).items() if hasattr(ModeConfig, k)}
        ) if "academic" in data else ModeConfig(
            return_all_parses=True, include_prakriya=True, include_engine_details=True, max_candidates=-1
        )

        # Parse default mode
        default_mode_str = data.get("default_mode", "production")
        try:
            default_mode = AnalysisMode(default_mode_str)
        except ValueError:
            raise ConfigError(
                f"Invalid default_mode: {default_mode_str}. "
                f"Must be one of: production, educational, academic"
            )

        return cls(
            engines=engines,
            cache=cache,
            disambiguation=disambiguation,
            default_mode=default_mode,
            default_output_script=data.get("default_output_script", "devanagari"),
            input_detection=data.get("input_detection", "auto"),
            log_level=data.get("log_level", "INFO"),
            log_file=data.get("log_file"),
            production=production,
            educational=educational,
            academic=academic,
        )

    @classmethod
    def _apply_env_overrides(cls, config: "Config") -> "Config":
        """Apply environment variable overrides to configuration.

        Args:
            config: Base configuration.

        Returns:
            Configuration with environment overrides applied.
        """
        # Cache overrides
        if redis_url := os.environ.get("SANSKRIT_REDIS_URL"):
            config.cache.redis_url = redis_url

        if sqlite_path := os.environ.get("SANSKRIT_SQLITE_PATH"):
            config.cache.sqlite_path = sqlite_path

        # Disambiguation/LLM overrides
        if llm_provider := os.environ.get("SANSKRIT_LLM_PROVIDER"):
            config.disambiguation.llm_provider = llm_provider.lower()

        if llm_model := os.environ.get("SANSKRIT_LLM_MODEL"):
            config.disambiguation.llm_model = llm_model

        if ollama_url := os.environ.get("SANSKRIT_OLLAMA_URL"):
            config.disambiguation.ollama_url = ollama_url

        if openai_key := os.environ.get("SANSKRIT_OPENAI_API_KEY"):
            config.disambiguation.openai_api_key = openai_key

        # Logging overrides
        if log_level := os.environ.get("SANSKRIT_LOG_LEVEL"):
            config.log_level = log_level.upper()

        if log_file := os.environ.get("SANSKRIT_LOG_FILE"):
            config.log_file = log_file

        return config

    @classmethod
    def _create_default_config(cls, path: Path) -> None:
        """Create the default configuration file.

        Args:
            path: Path where to create the config file.
        """
        default_config = """\
# Sanskrit Analyzer Configuration
# See: https://github.com/narenmudivarthy/sanskrit_analyzer

# Analysis mode: production, educational, academic
default_mode: production

# Output script: devanagari, iast, slp1
default_output_script: devanagari

# Input detection: auto
input_detection: auto

# Logging
log_level: INFO
# log_file: ~/.sanskrit_analyzer/analyzer.log

# Engine configuration
engines:
  vidyut: true
  vidyut_weight: 0.35
  dharmamitra: true
  dharmamitra_weight: 0.40
  dharmamitra_model: buddhist-nlp/byt5-sanskrit
  dharmamitra_device: auto
  heritage: true
  heritage_weight: 0.25
  heritage_mode: local  # local | remote | fallback
  heritage_local_url: http://localhost:8080

# Cache configuration
cache:
  memory_enabled: true
  memory_max_size: 1000
  redis_enabled: true
  redis_url: redis://localhost:6379/0
  redis_ttl_days: 7
  sqlite_enabled: true
  sqlite_path: ~/.sanskrit_analyzer/corpus.db

# Disambiguation configuration
disambiguation:
  rules_enabled: true
  min_confidence_skip: 0.95
  llm_enabled: true
  llm_provider: ollama  # ollama | openai
  llm_model: llama3.2
  ollama_url: http://localhost:11434
  human_enabled: true
  human_auto_prompt: false

# Mode-specific settings
production:
  return_all_parses: false
  include_prakriya: false
  max_candidates: 1

educational:
  return_all_parses: true
  include_prakriya: true
  max_candidates: 5

academic:
  return_all_parses: true
  include_prakriya: true
  include_engine_details: true
  max_candidates: -1  # All
"""
        # Create parent directory if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            f.write(default_config)

    @classmethod
    def default_path(cls) -> Path:
        """Get the default configuration file path."""
        return Path("~/.sanskrit_analyzer/config.yaml").expanduser()

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dictionary representation of the configuration.
        """
        return {
            "default_mode": self.default_mode.value,
            "default_output_script": self.default_output_script,
            "input_detection": self.input_detection,
            "log_level": self.log_level,
            "log_file": self.log_file,
            "engines": {
                "vidyut": self.engines.vidyut,
                "vidyut_weight": self.engines.vidyut_weight,
                "dharmamitra": self.engines.dharmamitra,
                "dharmamitra_weight": self.engines.dharmamitra_weight,
                "dharmamitra_model": self.engines.dharmamitra_model,
                "dharmamitra_device": self.engines.dharmamitra_device,
                "heritage": self.engines.heritage,
                "heritage_weight": self.engines.heritage_weight,
                "heritage_mode": self.engines.heritage_mode,
                "heritage_local_url": self.engines.heritage_local_url,
            },
            "cache": {
                "memory_enabled": self.cache.memory_enabled,
                "memory_max_size": self.cache.memory_max_size,
                "redis_enabled": self.cache.redis_enabled,
                "redis_url": self.cache.redis_url,
                "redis_ttl_days": self.cache.redis_ttl_days,
                "sqlite_enabled": self.cache.sqlite_enabled,
                "sqlite_path": self.cache.sqlite_path,
            },
            "disambiguation": {
                "rules_enabled": self.disambiguation.rules_enabled,
                "min_confidence_skip": self.disambiguation.min_confidence_skip,
                "llm_enabled": self.disambiguation.llm_enabled,
                "llm_provider": self.disambiguation.llm_provider,
                "llm_model": self.disambiguation.llm_model,
                "ollama_url": self.disambiguation.ollama_url,
                "human_enabled": self.disambiguation.human_enabled,
            },
        }

    def save(self, path: Optional[str | Path] = None) -> None:
        """Save configuration to a YAML file.

        Args:
            path: Path to save to. Uses default path if not specified.
        """
        import yaml

        if path is None:
            path = self.default_path()
        else:
            path = Path(path).expanduser()

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
