from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

try:  # pragma: no cover - optional dependency
    import google.generativeai as genai  # type: ignore
except ImportError:  # pragma: no cover
    genai = None


def semantic_match(page_text: str, expectation: str, selector: Optional[str] = None, probe_text: Optional[str] = None) -> bool:
    """Returns True when the page text satisfies the semantic expectation."""
    expectation = expectation.strip()
    if not expectation:
        return False
    model = _get_model()
    if model:
        prompt = (
            "You are a test oracle. Decide if the provided page text shows the expected outcome.\n"
            f"Expectation: {expectation}\n"
            "Page text:\n```\n"
            f"{page_text[:4000]}\n"
            "```\n"
            "Respond with YES if the expectation is met, NO otherwise."
        )
        try:
            response = model.generate_content(prompt)
            text = (response.text or "").strip().lower()
            if text.startswith("yes"):
                return True
            if text.startswith("no"):
                return False
        except Exception:
            pass  # fall through to heuristic
    return _heuristic_match(page_text, expectation, selector, probe_text)


def _heuristic_match(page_text: str, expectation: str, selector: Optional[str], probe_text: Optional[str]) -> bool:
    expectation_lower = expectation.lower()
    page_lower = page_text.lower()
    if expectation_lower and expectation_lower in page_lower:
        return True
    if probe_text and probe_text.lower() in page_lower:
        return True
    if selector and "#status" in selector:
        status_fragment = _extract_between(page_text, "status", 200)
        if status_fragment and expectation_lower.split()[0] in status_fragment.lower():
            return True
    tokens = [token for token in expectation_lower.replace("!", " ").split() if token]
    return all(token in page_lower for token in tokens[:2])


def _extract_between(text: str, marker: str, span: int) -> Optional[str]:
    idx = text.lower().find(marker.lower())
    if idx == -1:
        return None
    start = max(0, idx - span // 2)
    end = min(len(text), idx + span // 2)
    return text[start:end]


@lru_cache(maxsize=1)
def _get_model():
    if genai is None:
        return None
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    try:
        return genai.GenerativeModel(model_name)
    except Exception:
        return None
