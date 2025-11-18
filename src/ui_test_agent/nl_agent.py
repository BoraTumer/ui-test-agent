from __future__ import annotations

import json
import logging
import os
import re
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import Settings
from .dom_indexer import DOMSemanticIndexer
from .context_builder import ContextBuilder

# Suppress all Google ADK/Genai warnings about non-text parts
warnings.filterwarnings("ignore", category=UserWarning, module="google")
warnings.filterwarnings("ignore", message=".*non-text parts.*")

# Suppress Google SDK logging
for logger_name in ["google", "google.genai", "google.adk", "google.api_core"]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)
    logging.getLogger(logger_name).propagate = False

try:  # pragma: no cover - optional dependency
    from google.adk import Agent  # type: ignore
    from google.adk.runners import InMemoryRunner  # type: ignore
    from google.genai import types  # type: ignore
except ImportError:  # pragma: no cover
    Agent = None  # type: ignore
    InMemoryRunner = None  # type: ignore
    types = None  # type: ignore


# ===== Scenario Dataclass (previously in dsl.py) =====

@dataclass
class Scenario:
    """Test scenario with metadata, environment variables, and action flow."""
    meta: Dict[str, Any]
    env: Dict[str, Any]
    flow: List[Dict[str, Any]]


class ScenarioError(RuntimeError):
    """Raised when scenario generation or validation fails."""


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dictionaries, with override taking precedence."""
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


@dataclass
class TranscriptEntry:
    author: str
    text: str


@dataclass
class GeneratedScenario:
    scenario: Scenario
    raw_plan: Dict[str, Any]
    transcript: List[TranscriptEntry]


class NaturalLanguageOrchestrator:
    """Turns natural language prompts into executable scenarios using hybrid approach."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._adk_available = Agent is not None and InMemoryRunner is not None and types is not None
        self.context_builder = ContextBuilder()  # NEW: Stage 2 context builder
        # DOM cache: url -> (snapshot, timestamp)
        self._dom_cache: Dict[str, Tuple[str, float]] = {}
        self._dom_cache_ttl: int = 300  # 5 minutes TTL

    def get_cached_dom(self, url: str) -> Optional[str]:
        """
        Get cached DOM snapshot if available and not expired.
        Returns None if cache miss or expired.
        """
        if url in self._dom_cache:
            snapshot, timestamp = self._dom_cache[url]
            if time.time() - timestamp < self._dom_cache_ttl:
                return snapshot
            # Expired, remove from cache
            del self._dom_cache[url]
        return None
    
    def cache_dom(self, url: str, snapshot: str) -> None:
        """Store DOM snapshot in cache with current timestamp."""
        self._dom_cache[url] = (snapshot, time.time())

    def build(
        self,
        prompt: str,
        base_env: Dict[str, Any],
        dom_context: Optional[str] = None,
        feedback: Optional[str] = None,
    ) -> GeneratedScenario:
        prompt = prompt.strip()
        if not prompt:
            raise ScenarioError("Natural language prompt is empty")
        if self._adk_available:
            try:
                scenario = self._build_via_adk(prompt, base_env, dom_context, feedback)
                return scenario
            except Exception as exc:  # pragma: no cover - diagnostics only
                import traceback
                print(f"[ui-test-agent] ADK NL orchestrator failed: {exc}")
                print(f"[ui-test-agent] Exception traceback:")
                traceback.print_exc()
                print(f"[ui-test-agent] Falling back to heuristic plan.")
        return self._build_via_rules(prompt, base_env, dom_context, feedback)

    # --- ADK multi-agent path -------------------------------------------------

    def _build_via_adk(
        self,
        prompt: str,
        base_env: Dict[str, Any],
        dom_context: Optional[str],
        feedback: Optional[str],
    ) -> GeneratedScenario:
        assert Agent and InMemoryRunner and types  # for type checkers

        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        # HYBRID APPROACH: Single agent with rich context from ContextBuilder
        # No multi-agent orchestration - simpler, faster, more reliable
        
        single_agent = Agent(
            name="scenario_builder",
            description="Builds complete test scenarios from natural language with rich context",
            instruction="""
You are an expert test scenario builder. You receive structured context including:
  1. User's intent analysis (detected patterns)
  2. Available page elements with priority-sorted selectors
  3. Few-shot examples matching the use case
  4. Best practices and rules

Your task: Generate a JSON test scenario using the PROVIDED selectors.

CRITICAL RULES:
- Use EXACT selectors from "Available Page Elements" section
- DON'T guess or invent selectors not in the list
- Prefer #id > [data-testid] > text= > [name]
- Keep scenarios under 10 steps (simpler is better)
- Return ONLY valid JSON (no markdown, no explanations, no code fences)

OUTPUT FORMAT:
{
  "meta": {"name": "...", "description": "..."},
  "env": {"baseUrl": "..."},
  "flow": [
    {"action": "go", "url": "/page.html"},
    {"action": "type", "selector": "#input-id", "value": "text"},
    {"action": "click", "selector": "text=Button"},
    {"action": "see", "text": "Success", "meaning": "Verification"}
  ]
}

Remember: Use selectors from the provided list, don't invent new ones!
""",
            model=model_name,
        )

        runner = InMemoryRunner(agent=single_agent, app_name="agents")
        
        # Use async session creation (create_session_sync is deprecated)
        async def _create_session():
            return await runner.session_service.create_session(
                app_name=runner.app_name,
                user_id="local-user",
            )
        
        session = _run_sync(_create_session())

        # HYBRID: Build rich context with DOM elements
        # dom_context is already formatted string from DOMSemanticIndexer
        # Pass it directly as raw context since context_builder expects ElementInfo list
        # TODO: Future enhancement - parse dom_context back to ElementInfo list
        dom_index = []  # Empty for structured format
        
        # Build rich context with intent analysis + examples + best practices
        instructions = self.context_builder.build_context(
            user_instructions=prompt,
            dom_index=dom_index,
            base_env=base_env,
            feedback=feedback
        )
        
        # Append formatted DOM context from indexer
        if dom_context:
            instructions += f"\n\n---\n\n{dom_context}"
        
        message = types.Content(role="user", parts=[types.Part(text=instructions)])
        transcript: List[TranscriptEntry] = []

        async def _consume():
            """
            Consume ADK agent events and build transcript.
            Handles all part types: text, function_call, thought_signature, etc.
            """
            async for event in runner.run_async(
                user_id="local-user",
                session_id=session.id,
                new_message=message,
            ):
                if event.content and event.content.parts:
                    text_parts: List[str] = []
                    for part in event.content.parts:
                        # Handle text parts
                        if getattr(part, "text", None):
                            text_parts.append(part.text)
                        
                        # Handle function calls (agent tool invocations)
                        elif getattr(part, "function_call", None):
                            fn = part.function_call
                            fn_name = getattr(fn, "name", "unknown_function")
                            args = getattr(fn, "args", None)
                            
                            # Log function call for debugging
                            if args:
                                if isinstance(args, str):
                                    text_parts.append(f"[Function: {fn_name}]\n{args}")
                                else:
                                    try:
                                        args_json = json.dumps(args, ensure_ascii=False, indent=2)
                                        text_parts.append(f"[Function: {fn_name}]\n{args_json}")
                                    except Exception:
                                        text_parts.append(f"[Function: {fn_name}]\n{str(args)}")
                        
                        # Handle thought signatures (internal reasoning - skip for transcript)
                        elif getattr(part, "thought_signature", None):
                            # These are internal model thoughts, not needed in transcript
                            pass
                        
                        # Handle any other part types
                        else:
                            part_type = type(part).__name__
                            # Only log if it's something unexpected
                            if part_type not in ["ThoughtSignature", "Thought"]:
                                text_parts.append(f"[{part_type}]: {str(part)[:200]}")
                    
                    if text_parts:
                        transcript.append(
                            TranscriptEntry(
                                author=event.author or "agent",
                                text="\n".join(text_parts),
                            )
                        )

        _run_sync(_consume())
        _run_sync(runner.close())

        if not transcript:
            raise ScenarioError("ADK NL orchestrator produced no output")
        
        raw_response = _extract_final_json(transcript)
        plan_dict = _safe_json_loads(raw_response)
        scenario = _scenario_from_dict(plan_dict, base_env)
        return GeneratedScenario(scenario=scenario, raw_plan=plan_dict, transcript=transcript)

    # --- Heuristic fallback ---------------------------------------------------

    def _build_via_rules(
        self,
        prompt: str,
        base_env: Dict[str, Any],
        dom_context: Optional[str],
        feedback: Optional[str],
    ) -> GeneratedScenario:
        prompt_lower = prompt.lower()
        flow: List[Dict[str, Any]] = []
        meta = {
            "name": "NL scenario",
            "tags": ["nl", "heuristic"],
        }
        if feedback:
            meta["notes"] = {"feedback": feedback}
        env = {"baseUrl": base_env.get("baseUrl", self.settings.base_url)}
        creds = {}
        if "admin" in prompt_lower and "password" in prompt_lower:
            creds = {"user": "admin", "pass": "password"}
            env["creds"] = creds

        if dom_context:
            if "/demo_login.html" in dom_context:
                path = "/demo_login.html"
            else:
                path = "/"
        elif "demo" in prompt_lower and "login" in prompt_lower:
            path = "/demo_login.html"
        elif "login" in prompt_lower:
            path = "/login"
        else:
            path = "/"
        flow.append({"go": path})

        # Parse DOM context if available (future enhancement)
        selector_hints = {}

        if "login" in prompt_lower:
            flow.append({"see": {"text": "login"}})
            flow.append({"type": {"into": "input[name=username]|#username", "text": creds.get("user", "user@example.com")}})
            flow.append({"type": {"into": "input[name=password]|#password", "text": creds.get("pass", "changeme")}})
            flow.append({"click": {"on": "#login-button|button[type=submit]"}})
            flow.append({"see": {"text": "Login successful", "meaning": "the user sees that login succeeded"}})
        else:
            flow.append({"see": {"text": "welcome"}})

        plan_dict = {"meta": meta, "env": env, "flow": flow}
        transcript = [
            TranscriptEntry(author="heuristic_planner", text=json.dumps(plan_dict, ensure_ascii=False, indent=2))
        ]
        scenario = _scenario_from_dict(plan_dict, base_env)
        return GeneratedScenario(scenario=scenario, raw_plan=plan_dict, transcript=transcript)


def _scenario_from_dict(data: Dict[str, Any], base_env: Dict[str, Any]) -> Scenario:
    """
    Convert JSON plan to Scenario object.
    Validates and normalizes flow steps.
    """
    meta = data.get("meta", {})
    env = deep_merge({"baseUrl": base_env.get("baseUrl")}, data.get("env", {}))
    flow = data.get("flow", [])
    
    # Better validation with context
    if not flow:
        # Check if there's any step-like data elsewhere
        if "steps" in data:
            flow = data["steps"]
        elif "actions" in data:
            flow = data["actions"]
        else:
            # Provide helpful error message
            available_keys = list(data.keys())
            raise ScenarioError(
                f"Generated scenario has no flow steps. "
                f"Available keys: {available_keys}. "
                f"Expected 'flow' key with list of actions."
            )
    
    normalized: List[Dict[str, Any]] = []
    for i, step in enumerate(flow):
        try:
            normalized.append(_normalize_step_format(step))
        except Exception as exc:
            raise ScenarioError(
                f"Failed to normalize step {i+1}/{len(flow)}: {step}. Error: {exc}"
            ) from exc
    
    return Scenario(meta=meta, env=env, flow=normalized)


def _safe_json_loads(raw: str) -> Dict[str, Any]:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ScenarioError("Failed to parse scenario JSON from NL orchestrator") from exc


def _extract_final_json(transcript: List[TranscriptEntry]) -> str:
    """
    Extract JSON from agent transcript.
    Looks for the most complete scenario JSON with 'flow' key.
    Handles both naked JSON and markdown code blocks (```json ... ```).
    """
    # Pattern to match JSON within markdown code blocks
    json_block_pattern = re.compile(r'```(?:json)?\s*\n(\{.*?\})\s*\n```', re.DOTALL | re.IGNORECASE)
    
    best_candidate = None
    best_score = -1
    
    for entry in reversed(transcript):
        text = entry.text.strip()
        candidates = []
        
        # 1) Try to find JSON in markdown code block first
        match = json_block_pattern.search(text)
        if match:
            json_candidate = match.group(1).strip()
            if json_candidate.startswith("{") and json_candidate.endswith("}"):
                candidates.append(json_candidate)
        
        # 2) Try to extract naked JSON (remove markdown fences if present)
        candidate = text
        if candidate.startswith("```"):
            # Remove markdown code fence lines
            lines = [line for line in candidate.splitlines() 
                    if not line.strip().startswith("```")]
            candidate = "\n".join(lines).strip()
        
        # 3) Check if it's complete JSON object
        if candidate.startswith("{") and candidate.endswith("}"):
            candidates.append(candidate)
        
        # 4) Try to find JSON substring within text
        if "{" in candidate and "}" in candidate:
            start = candidate.find("{")
            end = candidate.rfind("}") + 1
            snippet = candidate[start:end]
            if snippet.startswith("{") and snippet.endswith("}"):
                candidates.append(snippet)
        
        # Score each candidate
        for cand in candidates:
            try:
                parsed = json.loads(cand)
                score = 0
                
                # Prioritize JSONs with 'flow' key (the actual scenario)
                if "flow" in parsed and isinstance(parsed["flow"], list) and len(parsed["flow"]) > 0:
                    score += 100
                
                # Bonus for having meta/env keys
                if "meta" in parsed:
                    score += 10
                if "env" in parsed:
                    score += 10
                
                # Penalize if it's just intent/selector hints
                if set(parsed.keys()) == {"goals", "inputs", "assertions"}:
                    score = 1  # Low score
                if set(parsed.keys()) == {"selectors", "messages"}:
                    score = 1  # Low score
                
                if score > best_score:
                    best_score = score
                    best_candidate = cand
            except json.JSONDecodeError:
                continue
    
    if best_candidate:
        return best_candidate
    
    raise ScenarioError("No valid scenario JSON with 'flow' key found in NL orchestrator transcript")


def _normalize_step_format(step: Any) -> Dict[str, Any]:
    if not isinstance(step, dict):
        raise ScenarioError(f"Scenario step must be an object, got: {step}")
    # allow nested args/payload forms
    params = dict(step)
    step_name = params.pop("step", None)
    action = params.pop("action", None)
    if action is None:
        action = step_name
    if action is None:
        if len(step) == 1:
            key, value = next(iter(step.items()))
            return {key: value}
        raise ScenarioError(f"Step missing action: {step}")
    for key in ("args", "parameters", "params", "payload"):
        if key in params:
            nested = params.pop(key) or {}
            if isinstance(nested, dict):
                params.update(nested)

    selector = params.get("selector")
    if isinstance(selector, str):
        normalized_selector = _normalize_selector(selector)
        params["selector"] = normalized_selector
        if not params.get("text"):
            literal = _extract_text_literal(selector)
            if literal:
                params.setdefault("text", literal)

    match action:
        case "go":
            target = params.get("url") or params.get("path")
            return {"go": target or "/"}
        case "type":
            return {
                "type": {
                    "into": params.get("selector") or params.get("into", ""),
                    "text": params.get("text") or params.get("value", ""),
                }
            }
        case "click":
            return {"click": {"on": params.get("selector") or params.get("on", "")}}
        case "see":
            payload = {}
            text = params.get("text") or params.get("value")
            selector_hint = params.get("selector")
            if not text and selector_hint:
                extracted = _extract_text_literal(selector_hint)
                if extracted:
                    text = extracted
            if text:
                payload["text"] = text
            meaning = (
                params.get("meaning")
                or params.get("expected")
                or params.get("assertion")
                or params.get("description")
            )
            if meaning:
                payload["meaning"] = meaning
            if not payload:
                payload["meaning"] = "verify desired outcome"
            return {"see": payload}
        case "seeUrl":
            return {"seeUrl": params.get("fragment") or params.get("value") or params.get("url", "")}
        case "waitApi":
            payload = {
                "url": params.get("url") or params.get("pattern"),
                "code": params.get("code") or 200,
            }
            if schema := params.get("schema"):
                payload["schema"] = schema
            return {"waitApi": payload}
        case "a11y":
            return {"a11y": {"exclude": params.get("exclude", [])}}
        case _:
            return {action: params}


def _extract_text_literal(selector: str) -> Optional[str]:
    selector = selector.strip()
    patterns = ["text=", "text:", "text->", "text"]
    for prefix in patterns:
        if selector.lower().startswith(prefix):
            literal = selector[len(prefix):].strip()
            return literal.strip("\"' ")
    if selector.startswith("text(\"") or selector.startswith("text('"):
        literal = selector[5:-1]
        return literal.strip("\"' ")
    if selector.startswith(":has-text("):
        literal = selector[len(":has-text(") :].rstrip(")")
        return literal.strip("\"' ")
    return None


def _normalize_selector(selector: str) -> str:
    selector = selector.strip()
    if selector.lower().startswith("text="):
        literal = selector.split("=", 1)[1].strip().strip("\"'")
        return _build_text_fallback(literal)
    if selector.startswith("text(\"") or selector.startswith("text('"):
        literal = selector[5:-1]
        return _build_text_fallback(literal)
    return selector


def _build_text_fallback(text: str, dom_hints: Optional[Dict[str, str]] = None) -> str:
    """
    Build fallback selector chain for text-based locators.
    Prioritizes DOM hints if available, then generic patterns.
    """
    text = text.strip()
    if not text:
        return ""
    
    candidates = []
    
    # If DOM hints provided, use them first
    if dom_hints:
        text_lower = text.lower()
        if any(word in text_lower for word in ["login", "sign", "submit"]):
            if "submit" in dom_hints:
                candidates.append(dom_hints["submit"])
    
    # Generic patterns with priority order
    candidates.extend([
        f"button:has-text(\"{text}\")",
        f"[type='submit']:has-text(\"{text}\")",
        f"text={text}",
    ])
    
    # Case-insensitive fallback (only if different from original)
    if text != text.lower():
        candidates.append(f"button:has-text(\"{text.lower()}\")")
    
    # Deduplicate while preserving order
    seen = set()
    unique_candidates = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            unique_candidates.append(c)
    
    return "|".join(unique_candidates)


def _run_sync(coro):
    """
    Safely run async coroutine in sync context.
    Ensures event loop is properly cleaned up even on exceptions.
    """
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    except Exception:
        raise
    finally:
        try:
            loop.close()
        except Exception:
            pass  # Ignore cleanup errors
