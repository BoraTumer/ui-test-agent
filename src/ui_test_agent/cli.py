from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .config import ConfigError, load_settings
from .dom_indexer import DOMSemanticIndexer
from .nl_agent import NaturalLanguageOrchestrator, TranscriptEntry
from .playwright_ctx import PlaywrightManager
from .runner import ScenarioRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ui_test_agent", description="AI-powered Natural Language UI test agent")
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run", help="Execute a test from natural language")
    run.add_argument("--config", default="config.yaml", help="Path to config file")
    run.add_argument("--headful", action="store_true", help="Launch browser with UI")
    run.add_argument("--slowmo", type=int, help="Playwright slow motion in milliseconds")
    run.add_argument("--nl", help="Inline natural language instructions")
    run.add_argument("--nl-file", help="Path to a text file with natural language instructions")
    run.add_argument("--dynamic", action="store_true", help="Use dynamic NL agent (step-by-step decision making)")
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

    base_env: Dict[str, Any] = {"baseUrl": settings.base_url}
    
    # Read natural language prompt
    nl_prompt = _read_nl_prompt(args.nl, args.nl_file)
    
    if not nl_prompt:
        parser.error("Natural language prompt required (use --nl or --nl-file)")
    
    dom_context = None
    nl_builder: Optional[NaturalLanguageOrchestrator] = None
    nl_attempt = 0
    max_nl_attempts = 2

    # NEW: Dynamic NL mode - agent makes step-by-step decisions
    if args.dynamic:
        if not nl_prompt:
            parser.error("--dynamic mode requires --nl or --nl-file")
        
        headful_override = True if args.headful else None
        slow_mo_override = args.slowmo
        
        from .dynamic_nl_agent import DynamicNLAgent
        
        try:
            with PlaywrightManager(settings, headful=headful_override, slow_mo=slow_mo_override) as session:
                # Navigate to base URL first
                session.page.goto(settings.base_url, wait_until="networkidle")
                
                # Let agent execute goal dynamically
                agent = DynamicNLAgent(settings, session.page)
                result = agent.execute_goal(nl_prompt)
                
                print(f"\n[ui-test-agent] Dynamic execution: {result['status'].upper()}")
                print(f"[ui-test-agent] Steps taken: {len(result['steps'])}")
                
                for step in result['steps']:
                    status_emoji = "✅" if step['status'] == 'success' else "❌"
                    print(f"  {status_emoji} Step {step['step']}: {step['action']}")
                
                return 0 if result['status'] == 'success' else 1
        except Exception as exc:
            print(f"\n[ui-test-agent] Dynamic mode error: {exc}")
            import traceback
            traceback.print_exc()
            return 2

    # Static NL mode - generate full scenario upfront, then execute
    print(f"[ui-test-agent] Static NL mode: generating scenario from instructions...")
    builder = NaturalLanguageOrchestrator(settings)
    
    # Extract target URL from user instructions (if specified)
    target_url = _extract_target_url(nl_prompt, settings.base_url)
    dom_context = _collect_dom_context(target_url, nl_builder=builder)
    
    try:
        generated = builder.build(nl_prompt, base_env, dom_context=dom_context)
    except Exception as exc:
        print(f"Scenario generation failed: {exc}")
        return 2
    
    # Persist the generated plan to artifacts
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    scenario_label = _persist_generated_plan(
        plan=generated.raw_plan,
        transcript=generated.transcript,
        artifacts_dir=settings.artifacts_dir,
        explicit_path=None,
        suffix="v1",
    )
    
    print(f"[ui-test-agent] Scenario generated and saved to: {scenario_label}")
    print(f"[ui-test-agent] Executing {len(generated.scenario.flow)} steps...")
    
    # Execute the generated scenario
    headful_override = True if args.headful else None
    slow_mo_override = args.slowmo
    
    with PlaywrightManager(settings, headful=headful_override, slow_mo=slow_mo_override) as session:
        runner = ScenarioRunner(settings, generated.scenario, session.page)
        result = runner.run(scenario_label)
        success = result.success
        report = result.report
    
    scenario_name = report.meta.get("name", scenario_label)
    print(f"\n[ui-test-agent] Scenario '{scenario_name}' -> {report.status.upper()}")
    
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


def _extract_target_url(nl_prompt: str, base_url: str) -> str:
    """
    Extract target URL from natural language instructions.
    
    Looks for patterns like:
    - "Open http://localhost:8000/demo_login.html" → Full URL
    - "Navigate to /login.html" → Absolute path
    - "Go to demo_login.html" → Relative filename
    - "Visit the login page" → Falls back to base_url
    
    Args:
        nl_prompt: Natural language instructions from user
        base_url: Base URL from config.yaml (e.g., http://localhost:8000)
    
    Returns:
        Full URL to extract DOM from
    """
    import re
    
    # Pattern 1: Full URL (http://... or https://...)
    # Matches: http://localhost:8000/page.html, https://example.com/login
    full_url_match = re.search(r'https?://[^\s\)\"\']+', nl_prompt)
    if full_url_match:
        url = full_url_match.group(0)
        # Clean trailing punctuation
        url = re.sub(r'[,\.!?]+$', '', url)
        print(f"[ui-test-agent] Found full URL in instructions: {url}")
        return url
    
    # Pattern 2: Absolute path starting with / (/demo_login.html, /app/login)
    path_match = re.search(r'/[\w\-/\.]+\.html', nl_prompt)
    if path_match:
        path = path_match.group(0)
        url = base_url.rstrip('/') + path
        print(f"[ui-test-agent] Found path in instructions: {path} → {url}")
        return url
    
    # Pattern 3: Relative filename (demo_login.html, index.html, login.html)
    filename_match = re.search(r'\b[\w\-]+\.html\b', nl_prompt)
    if filename_match:
        filename = filename_match.group(0)
        url = base_url.rstrip('/') + '/' + filename
        print(f"[ui-test-agent] Found filename in instructions: {filename} → {url}")
        return url
    
    # Fallback: Use base_url (for cases like "test the homepage" or "login to the app")
    print(f"[ui-test-agent] No specific page found in instructions, using base URL: {base_url}")
    return base_url


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
    Collect DOM context using DOMSemanticIndexer for better accuracy.
    Supports caching to avoid redundant captures.
    """
    try:
        # Try to use cached DOM if available
        if nl_builder and hasattr(nl_builder, 'get_cached_dom'):
            cached = nl_builder.get_cached_dom(base_url)
            if cached:
                print("[ui-test-agent] Using cached DOM context")
                return cached
        
        print(f"[ui-test-agent] Extracting DOM from: {base_url}")
        # Use playwright directly for DOM extraction
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(base_url, wait_until="networkidle", timeout=10000)
            
            indexer = DOMSemanticIndexer(page)
            elements = indexer.build_index(max_elements=150)
            context = indexer.to_context_string()
            
            browser.close()
            
            print(f"[ui-test-agent] Found {len(elements)} interactive elements")
            
            # Cache it if builder supports caching
            if nl_builder and hasattr(nl_builder, 'cache_dom'):
                nl_builder.cache_dom(base_url, context)
            
            return context
    except Exception as exc:
        print(f"[ui-test-agent] DOM extraction failed: {exc}")
        return None


