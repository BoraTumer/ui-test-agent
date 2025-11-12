from __future__ import annotations

import json
import re
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, List, Optional

from jsonschema import ValidationError, validate
from playwright.sync_api import Page, expect

try:
    from axe_playwright_python.sync_playwright import Axe  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    Axe = None  # type: ignore


class OracleError(RuntimeError):
    """Raised when an assertion fails."""


def see_text(page: Page, text: str, timeout_ms: int) -> None:
    locator = page.get_by_text(text, exact=False)
    locator.wait_for(state="visible", timeout=timeout_ms)


def see_url(page: Page, fragment: str, timeout_ms: int) -> None:
    pattern = re.compile(re.escape(fragment), re.IGNORECASE)
    expect(page).to_have_url(pattern, timeout=timeout_ms)


def wait_api(
    page: Page,
    url_pattern: str,
    code: int,
    schema_path: Optional[str],
    timeout_ms: int,
) -> None:
    response = page.wait_for_response(
        lambda resp: resp.status == code and fnmatch(resp.url, url_pattern),
        timeout=timeout_ms,
    )
    if response.status != code:
        raise OracleError(f"Expected status {code} but got {response.status} for {url_pattern}")
    if schema_path:
        _assert_schema(response, schema_path)


def run_axe(page: Page, exclude: Optional[Iterable[str]] = None) -> List[dict]:
    if Axe is None:
        return []
    axe = Axe(page)
    axe.inject()
    results = axe.run(exclude=exclude)
    if results["violations"]:
        raise OracleError(f"Accessibility violations: {len(results['violations'])}")
    return results["violations"]


def _assert_schema(response, schema_path: str) -> None:
    schema_file = Path(schema_path)
    if not schema_file.exists():
        raise OracleError(f"Schema file not found: {schema_file}")
    try:
        payload = response.json()
    except Exception as exc:  # pragma: no cover - Playwright provides details
        raise OracleError(f"Failed reading JSON body: {exc}") from exc
    with schema_file.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    try:
        validate(payload, schema)
    except ValidationError as exc:
        raise OracleError(f"Schema validation failed: {exc.message}") from exc
