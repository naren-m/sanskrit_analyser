"""Configuration management for Sanskrit Analyzer."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


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


@dataclass
class DisambiguationConfig:
    """Configuration for disambiguation pipeline."""

    rules_enabled: bool = True
    min_confidence_skip: float = 0.95
    llm_enabled: bool = True
    llm_provider: str = "ollama"  # ollama | anthropic | openai
    llm_model: str = "llama3.2"
    ollama_url: str = "http://localhost:11434"
    human_enabled: bool = True
    human_auto_prompt: bool = False


@dataclass
class ModeConfig:
    """Configuration for output modes."""

    return_all_parses: bool = False
    include_prakriya: bool = False
    include_engine_details: bool = False
    max_candidates: int = 1


@dataclass
class Config:
    """Main configuration for Sanskrit Analyzer."""

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

    @classmethod
    def from_file(cls, path: str | Path) -> "Config":
        """Load configuration from a YAML file."""
        import yaml

        path = Path(path).expanduser()
        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> "Config":
        """Create Config from a dictionary."""
        engines = EngineConfig(**data.get("engines", {})) if "engines" in data else EngineConfig()
        cache = CacheConfig(**data.get("cache", {})) if "cache" in data else CacheConfig()
        disambiguation = (
            DisambiguationConfig(**data.get("disambiguation", {}))
            if "disambiguation" in data
            else DisambiguationConfig()
        )

        return cls(
            engines=engines,
            cache=cache,
            disambiguation=disambiguation,
            default_mode=AnalysisMode(data.get("default_mode", "production")),
            default_output_script=data.get("default_output_script", "devanagari"),
            input_detection=data.get("input_detection", "auto"),
            log_level=data.get("log_level", "INFO"),
            log_file=data.get("log_file"),
        )

    @classmethod
    def default_path(cls) -> Path:
        """Get the default configuration file path."""
        return Path("~/.sanskrit_analyzer/config.yaml").expanduser()
