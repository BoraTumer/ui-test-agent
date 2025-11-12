from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml


TOKEN_PATTERN = re.compile(r"\$env(?:\.[A-Za-z0-9_]+)+")


@dataclass
class Scenario:
    meta: Dict[str, Any]
    env: Dict[str, Any]
    flow: List[Dict[str, Any]]


class ScenarioError(RuntimeError):
    """Raised when a scenario file is invalid."""


def load_scenario(path: str | Path, base_env: Dict[str, Any] | None = None) -> Scenario:
    scenario_path = Path(path)
    if not scenario_path.exists():
        raise ScenarioError(f"Scenario file not found: {scenario_path}")

    with scenario_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    if "flow" not in raw:
        raise ScenarioError("Scenario missing 'flow'")

    meta = dict(raw.get("meta", {}))
    env = {}
    if base_env:
        env = deep_merge(env, base_env)
    env = deep_merge(env, raw.get("env", {}))
    flow = _resolve_flow(raw.get("flow", []), env)

    return Scenario(meta=meta, env=env, flow=flow)


def _resolve_flow(flow: List[Dict[str, Any]], env: Dict[str, Any]) -> List[Dict[str, Any]]:
    resolved: List[Dict[str, Any]] = []
    for step in flow:
        resolved.append(_resolve_value(step, env))
    return resolved


def _resolve_value(value: Any, env: Dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {k: _resolve_value(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_value(v, env) for v in value]
    if isinstance(value, str):
        return _interpolate(value, env)
    return value


def _interpolate(text: str, env: Dict[str, Any]) -> str:
    def replacer(match: re.Match[str]) -> str:
        token = match.group(0)
        path = token.replace("$env.", "")
        try:
            value = _extract_env_value(path, env)
        except KeyError as exc:
            raise ScenarioError(f"Missing env value for {token}") from exc
        return str(value)

    return TOKEN_PATTERN.sub(replacer, text)


def _extract_env_value(path: str, env: Dict[str, Any]) -> Any:
    current: Any = env
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(part)
        current = current[part]
    return current


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result

