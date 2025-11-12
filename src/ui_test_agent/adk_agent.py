from __future__ import annotations

import asyncio
import importlib
import json
import os
import threading
from typing import Any, Dict


def _run_coroutine(coro):
    result: list[Any] = []
    errors: list[BaseException] = []

    def _target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result.append(loop.run_until_complete(coro))
        except BaseException as exc:  # pragma: no cover - helper
            errors.append(exc)
        finally:
            loop.close()

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join()
    if errors:
        raise errors[0]
    return result[0] if result else None


from pathlib import Path

from . import adk_tools
from .adk_tools import bind_runner, get_planned_calls
from .config import Settings
from .dsl import Scenario
from .runner import RunnerResult, ScenarioRunner

try:  # pragma: no cover - optional dependency
    _ADK = importlib.import_module("google.adk")
except ImportError:  # pragma: no cover
    _ADK = None


def run_function_tools_mode(
    settings: Settings,
    scenario: Scenario,
    page,
    scenario_path: str,
) -> RunnerResult:
    runner = ScenarioRunner(settings, scenario, page)
    bind_runner(runner)
    if not _ADK or not settings.gemini_api_key:
        print("[ui-test-agent] google-adk unavailable or GEMINI_API_KEY missing; using deterministic executor.")
        return runner.run(scenario_path)
    return _run_with_adk(settings, runner, scenario, scenario_path)


def _run_with_adk(
    settings: Settings,
    runner: ScenarioRunner,
    scenario: Scenario,
    scenario_path: str,
) -> RunnerResult:
    agent_cls = getattr(_ADK, "Agent", None)
    if agent_cls is None:
        print("[ui-test-agent] google-adk.Agent missing; falling back to deterministic executor.")
        return runner.run(scenario_path)

    instruction = (
        "You are a deterministic UI test agent. Given a scenario JSON (meta/env/flow),"
        " plan the minimal set of tool calls to execute every step in order."
        " Honour selector order, stay on the provided baseUrl host, and stop immediately"
        " on failure. Respond only with tool calls."
    )
    tools = [
        adk_tools.browser_go,
        adk_tools.browser_type,
        adk_tools.browser_click,
        adk_tools.browser_see,
        adk_tools.browser_see_url,
        adk_tools.browser_wait_api,
        adk_tools.browser_a11y,
    ]

    try:
        agent = agent_cls(
            name="ui_function_agent",
            description="Plans browser tool invocations for deterministic UI tests.",
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            instruction=instruction,
            tools=tools,
        )

        from google.adk.runners import InMemoryRunner  # type: ignore
        from google.genai import types  # type: ignore

        runner_ctx = InMemoryRunner(agent=agent, app_name="agents")
        session = _run_coroutine(
            runner_ctx.session_service.create_session(
                app_name=runner_ctx.app_name,
                user_id="local-user",
            )
        )
        payload = json.dumps(
            {"meta": scenario.meta, "env": scenario.env, "flow": scenario.flow},
            ensure_ascii=False,
        )
        message = types.Content(role="user", parts=[types.Part(text=payload)])

        async def _consume():
            async for _ in runner_ctx.run_async(
                user_id="local-user",
                session_id=session.id,
                new_message=message,
            ):
                pass

        try:
            _run_coroutine(_consume())
        finally:
            _run_coroutine(runner_ctx.close())

        plan = get_planned_calls()
        if plan:
            artifacts = Path(runner.settings.artifacts_dir)
            artifacts.mkdir(parents=True, exist_ok=True)
            plan_path = artifacts / "adk_plan.json"
            plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    except Exception as exc:  # pragma: no cover - depends on ADK internals
        print(f"[ui-test-agent] ADK execution failed: {exc}. Falling back to deterministic executor.")
        return runner.run(scenario_path)

    # Continue with deterministic runner for actual Playwright execution.
    return runner.run(scenario_path)
