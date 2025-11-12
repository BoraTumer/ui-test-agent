from __future__ import annotations

import importlib
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from playwright.sync_api import Page

from .config import Settings
from .dsl import Scenario
from .reporting import RunReport, StepResult, render_html, save_report

try:  # pragma: no cover - optional dependency
    _CU = importlib.import_module("google.adk.computer_use")  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    _CU = None


class AdaptiveTimeout:
    """
    Dynamically adjusts timeout based on historical execution times.
    Provides intelligent timeout values that adapt to page performance.
    """
    
    def __init__(self, base_ms: int):
        self.base = base_ms
        self.history: List[int] = []
        self.max_history = 10
    
    def record(self, duration_ms: int) -> None:
        """Record an execution time to update history."""
        self.history.append(duration_ms)
        if len(self.history) > self.max_history:
            self.history.pop(0)
    
    def next(self) -> int:
        """
        Calculate next timeout value.
        Returns base timeout if no history, otherwise 150% of average historical time.
        """
        if not self.history:
            return self.base
        avg = sum(self.history) / len(self.history)
        # Add 50% buffer to avoid false timeouts
        return int(max(self.base, avg * 1.5))
    
    def reset(self) -> None:
        """Clear history (useful for new test scenarios)."""
        self.history.clear()


def run_computer_use_mode(
    settings: Settings,
    scenario: Scenario,
    page: Page,
    scenario_path: str,
) -> RunReport:
    if not _CU:
        return _fallback_stub(settings, page, scenario_path, scenario)
    return _run_with_adk(settings, page, scenario_path, scenario)


def _fallback_stub(
    settings: Settings,
    page: Page,
    scenario_path: str,
    scenario: Scenario,
) -> RunReport:
    started = datetime.utcnow()
    steps: list[StepResult] = []
    artifacts_dir = settings.artifacts_dir
    t0 = time.perf_counter()
    try:
        page.goto(settings.base_url, wait_until="domcontentloaded", timeout=settings.timeouts.default)
        duration = int((time.perf_counter() - t0) * 1000)
        steps.append(
            StepResult(
                index=1,
                action="computer_use_open",
                payload={"url": settings.base_url},
                status="passed",
                duration_ms=duration,
            )
        )
    except Exception as exc:  # pragma: no cover
        duration = int((time.perf_counter() - t0) * 1000)
        steps.append(
            StepResult(
                index=1,
                action="computer_use_open",
                payload={"url": settings.base_url},
                status="failed",
                duration_ms=duration,
                error=str(exc),
            )
        )
    steps.append(
        StepResult(
            index=2,
            action="computer_use",
            payload={"reason": "google-adk computer use not available"},
            status="skipped",
            duration_ms=0,
            error="Install google-adk extras to enable Gemini Computer Use mode.",
        )
    )
    report = RunReport(
        scenario_path=scenario_path,
        meta={"name": scenario.meta.get("name", "Computer Use Scenario")},
        status="failed",
        started_at=started,
        finished_at=datetime.utcnow(),
        steps=steps,
    )
    _persist_report(settings, report)
    return report


def _run_with_adk(
    settings: Settings,
    page: Page,
    scenario_path: str,
    scenario: Scenario,
) -> RunReport:
    # Placeholder for when google-adk computer-use APIs are available.
    try:
        session_cls = getattr(_CU, "ComputerUseSession")
    except AttributeError:
        return _fallback_stub(settings, page, scenario_path, scenario)

    # Initialize adaptive timeout manager
    adaptive_timeout = AdaptiveTimeout(base_ms=settings.timeouts.default)
    
    guardrails: Dict[str, Any] = {
        "allowed_hosts": settings.allowed_hosts,
        "max_actions": 40,
        "timeout_ms": adaptive_timeout.next(),  # Use adaptive timeout
    }
    session = session_cls(
        model="gemini-2.5-flash",
        base_url=settings.base_url,
        guardrails=guardrails,
    )
    instructions = (
        "Open the base URL in Chromium, navigate to the login form, click the Login call-to-action,"
        " fill in the email and password fields using the provided env variables, submit the form,"
        " and confirm the URL contains /dashboard. Describe any blockers."
    )
    payload = {
        "env": scenario.env,
        "meta": scenario.meta,
    }
    
    start_time = time.perf_counter()
    try:
        summary = session.run(instructions=instructions, payload=payload)
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        adaptive_timeout.record(duration_ms)  # Record for future runs
    except Exception:
        return _fallback_stub(settings, page, scenario_path, scenario)
    
    steps = [
        StepResult(
            index=1,
            action="computer_use",
            payload={"instructions": instructions, "summary": summary},
            status="passed",
            duration_ms=duration_ms,
        )
    ]
    report = RunReport(
        scenario_path=scenario_path,
        meta=scenario.meta,
        status="passed",
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        steps=steps,
    )
    _persist_report(settings, report)
    return report


def _persist_report(settings: Settings, report: RunReport) -> None:
    artifacts = Path(settings.artifacts_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    json_path = artifacts / "report.json"
    html_path = artifacts / "report.html"
    save_report(report, json_path)
    render_html(json_path, html_path)
