from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Locator, Page

from .config import Settings
from .dsl import Scenario
from .locators import locator_candidates, parse_role
from .oracle import OracleError, run_axe, see_text, see_url, wait_api
from .semantic_eval import semantic_match
from .reporting import RunReport, StepResult, render_html, save_report


@dataclass
class RunnerResult:
    report: RunReport
    success: bool


class ScenarioRunner:
    def __init__(self, settings: Settings, scenario: Scenario, page: Page):
        self.settings = settings
        self.scenario = scenario
        self.page = page
        self.artifacts_dir = Path(self.settings.artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.step_retries = max(1, self.settings.retry.step)

    def run(self, scenario_path: str) -> RunnerResult:
        started = datetime.utcnow()
        results: List[StepResult] = []
        status = "passed"
        for index, step in enumerate(self.scenario.flow, start=1):
            action, payload = self._normalize_step(step)
            attempt_error = None
            screenshot_path = None
            success = False
            for attempt in range(1, self.step_retries + 1):
                started_at = time.perf_counter()
                try:
                    self._execute(action, payload)
                    duration = int((time.perf_counter() - started_at) * 1000)
                    results.append(
                        StepResult(
                            index=index,
                            action=action,
                            payload=payload,
                            status="passed",
                            duration_ms=duration,
                        )
                    )
                    success = True
                    break
                except Exception as exc:  # pragma: no cover - runtime errors
                    attempt_error = str(exc)
                    if attempt >= self.step_retries:
                        duration = int((time.perf_counter() - started_at) * 1000)
                        screenshot_path = self._capture_failure(index)
                        context_text = self._collect_context(action)
                        results.append(
                            StepResult(
                                index=index,
                                action=action,
                                payload=payload,
                                status="failed",
                                duration_ms=duration,
                                error=attempt_error,
                                screenshot=screenshot_path,
                                context=context_text,
                            )
                        )
                        status = "failed"
                    else:
                        continue
            if not success:
                break
        finished = datetime.utcnow()
        report = RunReport(
            scenario_path=scenario_path,
            meta=self.scenario.meta,
            status=status,
            started_at=started,
            finished_at=finished,
            steps=results,
        )
        json_path = self.artifacts_dir / "report.json"
        html_path = self.artifacts_dir / "report.html"
        save_report(report, json_path)
        render_html(json_path, html_path)
        return RunnerResult(report=report, success=status == "passed")

    def _execute(self, action: str, payload: Any) -> None:
        if action == "go":
            if isinstance(payload, str):
                path = payload
            else:
                path = payload.get("path", "/")
            self._navigate(path)
        elif action == "see":
            text_target = None
            meaning = None
            if isinstance(payload, str):
                text_target = payload
            elif isinstance(payload, dict):
                text_target = payload.get("text")
                meaning = payload.get("meaning") or payload.get("expected") or payload.get("description")
            else:
                raise RuntimeError("see step expects string or mapping")
            last_error: Exception | None = None
            if text_target:
                try:
                    see_text(self.page, text_target, self.settings.timeouts.default)
                    return
                except OracleError as exc:
                    last_error = exc
            expectation = meaning or text_target
            if expectation:
                body_text = self.page.inner_text("body")
                selector_hint = payload.get("selector") if isinstance(payload, dict) else None
                probe_text = payload.get("text") if isinstance(payload, dict) else None
                if semantic_match(body_text, expectation, selector=selector_hint, probe_text=probe_text):
                    return
                raise RuntimeError(f"Semantic expectation not met: {expectation}")
            raise last_error or RuntimeError("see step missing expectation")
        elif action == "type":
            if not isinstance(payload, dict):
                raise RuntimeError("type step expects mapping")
            self._type(payload["into"], payload["text"])
        elif action == "click":
            locator = payload if isinstance(payload, str) else payload.get("on")
            if not locator:
                raise RuntimeError("click step missing 'on'")
            self._click(locator)
        elif action == "seeUrl":
            if isinstance(payload, str):
                fragment = payload
            else:
                fragment = payload.get("fragment") or payload.get("value") or payload.get("path")
            if not fragment:
                raise RuntimeError("seeUrl step missing fragment")
            see_url(self.page, fragment, self.settings.timeouts.url)
        elif action == "waitApi":
            wait_api(
                self.page,
                payload["url"],
                payload.get("code", 200),
                payload.get("schema"),
                self.settings.timeouts.api,
            )
        elif action == "a11y":
            if isinstance(payload, dict):
                exclude = payload.get("exclude")
            elif isinstance(payload, list):
                exclude = payload
            else:
                exclude = None
            run_axe(self.page, exclude)
        else:
            raise RuntimeError(f"Unknown action: {action}")

    def _navigate(self, path: str) -> None:
        target = urljoin(self.settings.base_url, path)
        parsed = urlparse(target)
        if parsed.hostname not in self.settings.allowed_hosts:
            raise RuntimeError(f"Blocked navigation to host {parsed.hostname}")
        self.page.goto(target, wait_until="domcontentloaded", timeout=self.settings.timeouts.default)

    def _type(self, selector_str: str, text: str) -> None:
        locator = self._resolve_locator(selector_str)
        locator.fill(text, timeout=self.settings.timeouts.default)

    def _click(self, selector_str: str) -> None:
        locator = self._resolve_locator(selector_str)
        locator.click(timeout=self.settings.timeouts.default)

    def _resolve_locator(self, selector_str: str) -> Locator:
        last_error: Exception | None = None
        for candidate in locator_candidates(selector_str):
            candidate = candidate.strip()
            try:
                locator = self._build_locator(candidate).first
                locator.wait_for(state="visible", timeout=self.settings.timeouts.default)
                locator.scroll_into_view_if_needed()
                return locator
            except Exception as exc:  # pragma: no cover
                last_error = exc
                continue
        raise RuntimeError(f"Failed to resolve locator {selector_str}: {last_error}")

    def _build_locator(self, selector: str) -> Locator:
        if selector.startswith("role="):
            role, attrs = parse_role(selector)
            return self.page.get_by_role(role, **attrs)
        if selector.startswith("text="):
            return self.page.get_by_text(selector.replace("text=", ""), exact=True)
        if selector.startswith("[data-testid="):
            return self.page.get_by_test_id(selector.split("=", 1)[1].strip("[]'\""))
        return self.page.locator(selector)

    def _normalize_step(self, step: Dict[str, Any]) -> Tuple[str, Any]:
        if len(step) != 1:
            raise RuntimeError(f"Invalid step: {step}")
        action, payload = next(iter(step.items()))
        return action, payload

    def _capture_failure(self, index: int) -> str:
        path = self.artifacts_dir / f"failure_{index}.png"
        self.page.screenshot(path=path)
        return str(path)

    def _collect_context(self, action: str) -> Optional[str]:
        try:
            body_text = self.page.inner_text("body")
            snippet = " ".join(body_text.split())
            if not snippet:
                return None
            if action == "see":
                return snippet[:500]
            return snippet[:200]
        except Exception:  # pragma: no cover - best effort
            return None
