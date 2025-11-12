from __future__ import annotations

from typing import Any, Dict, List

try:  # pragma: no cover - optional dependency
    from google.adk import tool  # type: ignore
except ImportError:  # pragma: no cover
    def tool(*_args: Any, **_kwargs: Any):  # type: ignore
        def decorator(func):
            return func

        return decorator

PLANNED_CALLS: List[Dict[str, Any]] = []


def bind_runner(runner: Any) -> None:
    global PLANNED_CALLS
    PLANNED_CALLS = []


def get_planned_calls() -> List[Dict[str, Any]]:
    return list(PLANNED_CALLS)


def _record_call(action: str, payload: Dict[str, Any]) -> None:
    PLANNED_CALLS.append({"action": action, "payload": payload})


@tool()
def browser_go(base_url: str, path: str) -> Dict[str, Any]:
    _record_call("go", {"base_url": base_url, "path": path})
    return {"ok": True, "url": f"{base_url.rstrip('/')}/{path.lstrip('/')}"}


@tool()
def browser_type(selector: str, text: str) -> Dict[str, Any]:
    _record_call("type", {"selector": selector, "text": text})
    return {"ok": True}


@tool()
def browser_click(selector: str) -> Dict[str, Any]:
    _record_call("click", {"selector": selector})
    return {"ok": True}


@tool()
def browser_see(text: str, timeout_ms: int = 8000) -> Dict[str, Any]:
    _record_call("see", {"text": text, "timeout_ms": timeout_ms})
    return {"ok": True}


@tool()
def browser_see_url(fragment: str, timeout_ms: int = 15000) -> Dict[str, Any]:
    _record_call("seeUrl", {"fragment": fragment, "timeout_ms": timeout_ms})
    return {"ok": True}


@tool()
def browser_wait_api(url_pattern: str, code: int, schema_path: str = "") -> Dict[str, Any]:
    _record_call(
        "waitApi",
        {
            "url_pattern": url_pattern,
            "code": code,
            "schema_path": schema_path,
        },
    )
    return {"ok": True}


@tool()
def browser_a11y(exclude: str = "") -> Dict[str, Any]:
    _record_call("a11y", {"exclude": exclude})
    return {"ok": True, "violations": []}
