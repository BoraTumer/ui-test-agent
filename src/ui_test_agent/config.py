from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List
from urllib.parse import urlparse

import yaml
from dotenv import load_dotenv


@dataclass
class TimeoutConfig:
    default: int = 8000
    url: int = 15000
    api: int = 20000


@dataclass
class RetryConfig:
    step: int = 1
    scenario: int = 0


@dataclass
class Settings:
    mode: str
    base_url: str
    headless: bool
    slow_mo: int
    timeouts: TimeoutConfig
    retry: RetryConfig
    record_video: bool
    collect_har: bool
    allowed_hosts: List[str]
    artifacts_dir: str
    gemini_api_key: str | None


class ConfigError(RuntimeError):
    """Raised when configuration cannot be loaded."""


def load_settings(config_path: str | os.PathLike[str]) -> Settings:
    load_dotenv(override=False)
    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    try:
        timeouts_raw = raw.get("timeouts", {})
        retry_raw = raw.get("retry", {})
        settings = Settings(
            mode=raw.get("mode", "function_tools"),
            base_url=raw["baseUrl"],
            headless=bool(raw.get("headless", True)),
            slow_mo=int(raw.get("slowMo", 0)),
            timeouts=TimeoutConfig(
                default=int(timeouts_raw.get("default", 8000)),
                url=int(timeouts_raw.get("url", 15000)),
                api=int(timeouts_raw.get("api", 20000)),
            ),
            retry=RetryConfig(
                step=int(retry_raw.get("step", 1)),
                scenario=int(retry_raw.get("scenario", 0)),
            ),
            record_video=bool(raw.get("recordVideo", False)),
            collect_har=bool(raw.get("collectHAR", False)),
            allowed_hosts=list(raw.get("allowedHosts", [])),
            artifacts_dir=str(raw.get("artifactsDir", "artifacts")),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
        )
    except KeyError as exc:
        raise ConfigError(f"Missing required config key: {exc}") from exc

    if not settings.allowed_hosts:
        parsed = urlparse(settings.base_url)
        if parsed.hostname:
            settings.allowed_hosts = [parsed.hostname]

    return settings
