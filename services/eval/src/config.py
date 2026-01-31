"""Configuration loader for the evaluation suite."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass
class ThresholdConfig:
    """Threshold configuration for pass/fail determination."""

    ocr_character_accuracy: float = 0.95
    ocr_word_accuracy: float = 0.90
    recipe_field_accuracy: float = 0.90
    ingredient_match_rate: float = 0.85


@dataclass
class MetricsConfig:
    """Metrics configuration per suite."""

    ocr: list[str] = field(default_factory=lambda: [
        "character_accuracy",
        "word_accuracy",
        "levenshtein_distance",
        "bleu_score",
    ])
    recipe_extraction: list[str] = field(default_factory=lambda: [
        "field_accuracy",
        "ingredient_count_accuracy",
        "instruction_similarity",
        "cost_cents",
        "latency_ms",
    ])
    ingredient_matching: list[str] = field(default_factory=lambda: [
        "exact_match_rate",
        "fuzzy_match_rate",
        "false_positive_rate",
        "confidence_calibration",
    ])


@dataclass
class EvalConfig:
    """Main evaluation configuration."""

    # Environment settings
    openai_api_key: str = ""
    database_url: str = ""

    # Eval modes
    ocr_mode: str = "local"  # local | batch | mock
    mock_ai: bool = False
    cache_responses: bool = True
    parallel_workers: int = 4

    # Paths
    output_dir: Path = field(default_factory=lambda: Path("./results"))
    dataset_dir: Path = field(default_factory=lambda: Path("./datasets"))

    # Metrics and thresholds
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)

    # Runtime
    verbose: bool = False
    skip_tags: list[str] = field(default_factory=list)
    only_tags: list[str] = field(default_factory=list)


def load_env_file(env_file: str | None = None) -> None:
    """Load environment variables from file."""
    if env_file and Path(env_file).exists():
        load_dotenv(env_file)
    elif Path(".env.eval").exists():
        load_dotenv(".env.eval")
    elif Path(".env").exists():
        load_dotenv(".env")


def load_yaml_config(config_path: Path) -> dict[str, Any]:
    """Load YAML configuration file."""
    if not config_path.exists():
        return {}

    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def load_config(
    env_file: str | None = None,
    config_file: str | None = None,
) -> EvalConfig:
    """Load evaluation configuration from environment and config files.

    Args:
        env_file: Path to .env file (defaults to .env.eval)
        config_file: Path to YAML config file (defaults to eval.config.yaml)

    Returns:
        Populated EvalConfig instance.
    """
    # Load environment variables
    load_env_file(env_file)

    # Load YAML config
    config_path = Path(config_file) if config_file else Path("eval.config.yaml")
    yaml_config = load_yaml_config(config_path)

    # Build metrics config
    metrics_yaml = yaml_config.get("metrics", {})
    default_metrics = MetricsConfig()
    metrics = MetricsConfig(
        ocr=metrics_yaml.get("ocr", default_metrics.ocr),
        recipe_extraction=metrics_yaml.get("recipe_extraction", default_metrics.recipe_extraction),
        ingredient_matching=metrics_yaml.get("ingredient_matching", default_metrics.ingredient_matching),
    )

    # Build thresholds config
    thresholds_yaml = yaml_config.get("thresholds", {})
    thresholds = ThresholdConfig(
        ocr_character_accuracy=thresholds_yaml.get("ocr_character_accuracy", 0.95),
        ocr_word_accuracy=thresholds_yaml.get("ocr_word_accuracy", 0.90),
        recipe_field_accuracy=thresholds_yaml.get("recipe_field_accuracy", 0.90),
        ingredient_match_rate=thresholds_yaml.get("ingredient_match_rate", 0.85),
    )

    # Create config from environment
    config = EvalConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        database_url=os.getenv("DATABASE_URL", ""),
        ocr_mode=os.getenv("EVAL_OCR_MODE", "local"),
        mock_ai=os.getenv("EVAL_MOCK_AI", "false").lower() == "true",
        cache_responses=os.getenv("EVAL_CACHE_RESPONSES", "true").lower() == "true",
        parallel_workers=int(os.getenv("EVAL_PARALLEL_WORKERS", "4")),
        output_dir=Path(os.getenv("EVAL_OUTPUT_DIR", "./results")),
        dataset_dir=Path(os.getenv("EVAL_DATASET_DIR", "./datasets")),
        metrics=metrics,
        thresholds=thresholds,
        verbose=os.getenv("EVAL_VERBOSE", "false").lower() == "true",
    )

    return config


# Global config instance
_config: EvalConfig | None = None


def get_config() -> EvalConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: EvalConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
