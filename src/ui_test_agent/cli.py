from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .adk_agent import run_function_tools_mode
from .computer_use_agent import run_computer_use_mode
from .config import ConfigError, load_settings
from .dsl import Scenario, ScenarioError, load_scenario
from .dom_explorer import capture_dom_outline
from .nl_agent import NaturalLanguageOrchestrator, TranscriptEntry
from .playwright_ctx import PlaywrightManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ui_test_agent", description="AI-powered web UI test agent")
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run", help="Execute a scenario")
    run.add_argument("--scenario", help="Path to scenario YAML (required unless natural language prompt is provided)")
    run.add_argument("--config", default="config.yaml", help="Path to config file")
    run.add_argument("--mode", choices=["function_tools", "computer_use"], help="Override execution mode")
    run.add_argument("--headful", action="store_true", help="Launch browser with UI")
    run.add_argument("--slowmo", type=int, help="Playwright slow motion in milliseconds")
    run.add_argument("--nl", help="Inline natural language instructions for the scenario")
    run.add_argument("--nl-file", help="Path to a text file with natural language instructions")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "run":
        parser.print_help()
        return 0

    try:
        settings = load_settings(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}")
        return 2

    mode = args.mode or settings.mode
    base_env: Dict[str, Any] = {"baseUrl": settings.base_url}
    scenario: Scenario
    scenario_label: str

    nl_prompt = _read_nl_prompt(args.nl, args.nl_file)
    dom_context = None
    nl_builder: Optional[NaturalLanguageOrchestrator] = None
    nl_attempt = 0
    max_nl_attempts = 2

    if nl_prompt:
        builder = NaturalLanguageOrchestrator(settings)
        dom_context = _collect_dom_context(settings.base_url, nl_builder=builder)
        try:
            generated = builder.build(nl_prompt, base_env, dom_context=dom_context)
        except ScenarioError as exc:
            print(f"Natural language error: {exc}")
            return 2
        scenario = generated.scenario
        nl_builder = builder
        nl_attempt = 1
        scenario_label = _persist_generated_plan(
            plan=generated.raw_plan,
            transcript=generated.transcript,
            artifacts_dir=settings.artifacts_dir,
            explicit_path=args.scenario,
            suffix=f"v{nl_attempt}",
        )
    else:
        if not args.scenario:
            parser.error("--scenario is required when no natural language prompt is provided.")
        try:
            scenario = load_scenario(args.scenario, base_env=base_env)
        except ScenarioError as exc:
            print(f"Scenario error: {exc}")
            return 2
        scenario_label = args.scenario

    headful_override = True if args.headful else None
    slow_mo_override = args.slowmo

    attempt = 1
    success = False
    report = None
    scenario_name = scenario_label

    while True:
        success, report, scenario_name = _execute_run(
            settings=settings,
            scenario=scenario,
            scenario_path=scenario_label,
            mode=mode,
            headful=headful_override,
            slow_mo=slow_mo_override,
        )
        if success:
            break
        if not nl_builder or attempt >= max_nl_attempts:
            break
        feedback = _summarize_failure(report)
        print(f"[ui-test-agent] Attempt {attempt} failed, replanning with feedback...")
        attempt += 1
        
        # Use cached DOM context (will use cache if available)
        fresh_dom_context = _collect_dom_context(settings.base_url, nl_builder=nl_builder)
        
        try:
            regenerated = nl_builder.build(
                nl_prompt,
                base_env,
                dom_context=fresh_dom_context or dom_context,
                feedback=feedback,
            )
        except ScenarioError as exc:
            print(f"Natural language replanning failed: {exc}")
            break
        scenario = regenerated.scenario
        scenario_label = _persist_generated_plan(
            plan=regenerated.raw_plan,
            transcript=regenerated.transcript,
            artifacts_dir=settings.artifacts_dir,
            explicit_path=args.scenario,
            suffix=f"v{attempt}",
        )

    print(f"Scenario '{scenario_name}' -> {report.status.upper() if report else 'FAILED'}")
    return 0 if success else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


def _read_nl_prompt(inline: Optional[str], path: Optional[str]) -> Optional[str]:
    if path:
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(file_path)
        return file_path.read_text(encoding="utf-8")
    if inline:
        return inline
    return None


def _persist_generated_plan(
    plan: Dict[str, Any],
    transcript: List[TranscriptEntry],
    artifacts_dir: str,
    explicit_path: Optional[str],
    suffix: Optional[str] = None,
) -> str:
    artifacts = Path(artifacts_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    suffix_str = f"_{suffix}" if suffix else ""
    json_path = artifacts / f"nl_plan_{timestamp}{suffix_str}.json"
    json_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

    yaml_path = Path(explicit_path) if explicit_path else artifacts / f"nl_scenario_{timestamp}{suffix_str}.yml"
    with yaml_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(plan, handle, sort_keys=False, allow_unicode=True)

    transcript_path = artifacts / f"nl_transcript_{timestamp}{suffix_str}.md"
    with transcript_path.open("w", encoding="utf-8") as handle:
        for entry in transcript:
            handle.write(f"## [{entry.author}]\n{entry.text.strip()}\n\n")

    return str(yaml_path)


def _collect_dom_context(base_url: str, nl_builder=None) -> Optional[str]:
    """
    Collect DOM context with caching support.
    If nl_builder has caching support, use it to avoid redundant captures.
    """
    try:
        # Try to use cached DOM if available
        if nl_builder and hasattr(nl_builder, 'get_cached_dom'):
            cached = nl_builder.get_cached_dom(base_url)
            if cached:
                return cached
        
        # Capture fresh DOM snapshot
        context = capture_dom_outline(base_url)
        if context:
            # Cache it if builder supports caching
            if nl_builder and hasattr(nl_builder, 'cache_dom'):
                nl_builder.cache_dom(base_url, context)
            return context
    except Exception as exc:
        print(f"[ui-test-agent] DOM explorer failed: {exc}")
    return None


def _execute_run(
    settings,
    scenario: Scenario,
    scenario_path: str,
    mode: str,
    headful: Optional[bool],
    slow_mo: Optional[int],
):
    with PlaywrightManager(settings, headful=headful, slow_mo=slow_mo) as session:
        if mode == "computer_use":
            report = run_computer_use_mode(settings, scenario, session.page, scenario_path)
            success = report.status == "passed"
            scenario_name = report.meta.get("name", scenario_path)
        else:
            result = run_function_tools_mode(settings, scenario, session.page, scenario_path)
            report = result.report
            success = result.success
            scenario_name = report.meta.get("name", scenario_path)
    return success, report, scenario_name


def _summarize_failure(report) -> str:
    if not report:
        return "Scenario failed: unknown error."
    lines = [f"Scenario status: {getattr(report, 'status', 'failed')}"]
    steps = getattr(report, "steps", []) or []
    for step in steps:
        if getattr(step, "status", "") == "failed":
            error = getattr(step, "error", "Unknown error")
            lines.append(f"Step {step.index} ({step.action}) failed: {error}")
            context = getattr(step, "context", None)
            if context:
                lines.append(f"Page context snippet: {context[:200]}")
            break
    return "\n".join(lines)
