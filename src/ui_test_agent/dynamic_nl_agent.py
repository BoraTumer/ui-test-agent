"""
Dynamic Natural Language Agent

Instead of generating a full scenario upfront, this agent:
1. Takes user's high-level goal
2. Observes current page DOM
3. Decides next action
4. Executes action
5. Repeats until goal achieved

This is TRUE natural language automation - agent adapts to page changes.
"""

from __future__ import annotations

import json
import logging
import os
import warnings
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from playwright.sync_api import Page

from .config import Settings
from .dom_indexer import DOMSemanticIndexer

# Suppress Google warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google")
for logger_name in ["google", "google.genai", "google.adk"]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

try:
    import google.generativeai as genai
except ImportError:
    genai = None


@dataclass
class ActionStep:
    """Single action decided by agent"""
    action: str  # go, type, click, select, see, done
    selector: Optional[str] = None
    value: Optional[str] = None
    text: Optional[str] = None
    reasoning: Optional[str] = None
    reasoning: Optional[str] = None


class DynamicNLAgent:
    """
    Agent that makes decisions step-by-step based on current page state.
    
    Usage:
        agent = DynamicNLAgent(settings, page)
        result = agent.execute_goal("Login as admin and add product to cart")
    """
    
    def __init__(self, settings: Settings, page: Page):
        self.settings = settings
        self.page = page
        self.max_steps = 20  # Safety limit (increased for complex flows)
        self.history: List[Dict[str, Any]] = []
        
        if genai and settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            self.model = genai.GenerativeModel(model_name)
        else:
            self.model = None
    
    def execute_goal(self, goal: str) -> Dict[str, Any]:
        """
        Execute high-level goal by making step-by-step decisions.
        
        Args:
            goal: Natural language goal (e.g., "Login as admin")
            
        Returns:
            Execution report with steps taken and final status
        """
        if not self.model:
            return {
                "status": "error",
                "message": "Gemini API not available",
                "steps": []
            }
        
        print(f"[dynamic-agent] Goal: {goal}")
        print(f"[dynamic-agent] Starting at: {self.page.url}")
        
        self.history = []
        steps_taken = 0
        
        while steps_taken < self.max_steps:
            # 1. Observe current page
            dom_context = self._get_current_dom()
            page_url = self.page.url
            page_title = self.page.title()
            
            # 2. Ask agent: "What should I do next?"
            next_action = self._decide_next_action(
                goal=goal,
                current_url=page_url,
                page_title=page_title,
                dom_context=dom_context,
                history=self.history
            )
            
            if not next_action:
                return {
                    "status": "error",
                    "message": "Agent couldn't decide next action",
                    "steps": self.history
                }
            
            # 3. Execute action
            print(f"[dynamic-agent] Step {steps_taken + 1}: {next_action.action}")
            if next_action.reasoning:
                print(f"[dynamic-agent] Reasoning: {next_action.reasoning}")
            
            try:
                self._execute_action(next_action)
                self.history.append({
                    "step": steps_taken + 1,
                    "action": next_action.action,
                    "selector": next_action.selector,
                    "value": next_action.value,
                    "status": "success",
                    "url": self.page.url,
                    "reasoning": next_action.reasoning
                })
            except Exception as exc:
                print(f"[dynamic-agent] Action failed: {exc}")
                self.history.append({
                    "step": steps_taken + 1,
                    "action": next_action.action,
                    "status": "failed",
                    "error": str(exc)
                })
                return {
                    "status": "failed",
                    "message": f"Action failed: {exc}",
                    "steps": self.history
                }
            
            # 4. Check if goal achieved
            if next_action.action == "done":
                print(f"[dynamic-agent] Goal achieved in {steps_taken + 1} steps!")
                return {
                    "status": "success",
                    "message": "Goal achieved",
                    "steps": self.history
                }
            
            steps_taken += 1
        
        return {
            "status": "timeout",
            "message": f"Max steps ({self.max_steps}) reached",
            "steps": self.history
        }
    
    def _get_current_dom(self) -> str:
        """Extract current page DOM context"""
        try:
            # Check if page is still alive
            if not self.page or self.page.is_closed():
                return "# Page closed or unavailable"
            
            indexer = DOMSemanticIndexer(self.page)
            elements = indexer.build_index(max_elements=50)
            return indexer.to_context_string()
        except Exception as exc:
            print(f"[dynamic-agent] DOM extraction failed: {exc}")
            return "# DOM extraction failed - page may be transitioning"
    
    def _decide_next_action(
        self,
        goal: str,
        current_url: str,
        page_title: str,
        dom_context: str,
        history: List[Dict[str, Any]]
    ) -> Optional[ActionStep]:
        """
        Ask LLM: "Given current page state, what's the next action to achieve goal?"
        """
        # Show more history to avoid repeating actions
        history_str = json.dumps(history[-8:], indent=2) if history else "None"
        
        prompt = f"""You are a web automation agent. Your goal: {goal}

CURRENT STATE:
- URL: {current_url}
- Page Title: {page_title}
- Previous Steps (Last 8): {history_str}

AVAILABLE ELEMENTS:
{dom_context}

TASK: Decide the NEXT SINGLE ACTION to get closer to the goal.

CRITICAL RULES:
1. CAREFULLY CHECK previous steps - if ALL required fields are filled and form is submitted, return "done"
2. DON'T REPEAT filling the same field multiple times (check history!)
3. If you see a success notification in previous steps, the goal IS COMPLETE - return "done"
4. If the same selector appears multiple times in history with type/select actions, SKIP IT
5. Work through the goal sequentially - don't jump around filling fields randomly

ACTION TYPES:
- go: Navigate to URL (use "value" field for URL)
- type: Enter text into input field (requires "selector" and "value")
- click: Click button/link (requires "selector")
- select: Choose dropdown option (requires "selector" and "value" with option value/text)
- see: Verify text appears (use "value" field for text to check)
- done: Goal achieved, stop immediately

OUTPUT FORMAT (JSON only, no markdown):
{{
  "action": "click|type|go|select|see|done",
  "selector": "#id|selector (if click/type/select)",
  "value": "text to type OR url to visit OR text to verify OR option to select",
  "reasoning": "why this action"
}}

IMPORTANT: 
- Before typing/selecting, check if that exact selector was already used in previous steps
- After "see" verification succeeds, usually the goal is DONE
- Complete the form ONCE, then submit, then verify, then DONE

RESPOND WITH JSON ONLY:"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Clean markdown fences
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join([l for l in lines if not l.strip().startswith("```")])
            
            # Parse JSON
            data = json.loads(response_text)
            
            return ActionStep(
                action=data.get("action", "done"),
                selector=data.get("selector"),
                value=data.get("value"),
                text=data.get("text"),
                reasoning=data.get("reasoning")
            )
        except Exception as exc:
            print(f"[dynamic-agent] Decision failed: {exc}")
            return None
    
    def _execute_action(self, action: ActionStep) -> None:
        """Execute the decided action"""
        if action.action == "go":
            url = action.value or action.selector
            if not url:
                raise ValueError("go action requires URL in 'value' field")
            self.page.goto(url, wait_until="networkidle", timeout=10000)
        
        elif action.action == "type":
            if not action.selector:
                raise ValueError("type action requires selector")
            if not action.value:
                raise ValueError("type action requires value")
            locator = self.page.locator(action.selector).first
            locator.wait_for(state="visible", timeout=8000)
            locator.fill(action.value)
        
        elif action.action == "click":
            if not action.selector:
                raise ValueError("click action requires selector")
            locator = self.page.locator(action.selector).first
            locator.wait_for(state="visible", timeout=8000)
            locator.click()
            # Wait a bit after click for page updates (e.g., modals, notifications)
            self.page.wait_for_timeout(800)
        
        elif action.action == "select":
            if not action.selector:
                raise ValueError("select action requires selector")
            if not action.value:
                raise ValueError("select action requires value (option to select)")
            # Use Playwright's select_option for dropdowns
            select = self.page.locator(action.selector).first
            select.wait_for(state="visible", timeout=8000)
            # Try label first (e.g., "Engineering"), then value (e.g., "engineering")
            try:
                select.select_option(label=action.value, timeout=5000)
            except Exception:
                try:
                    select.select_option(value=action.value.lower(), timeout=5000)
                except Exception:
                    # Last resort: try value as-is
                    select.select_option(value=action.value, timeout=5000)
            # Wait longer after dropdown selection to let any JS handlers complete
            self.page.wait_for_timeout(800)
        
        elif action.action == "see":
            # Try value first, then text field
            text_to_verify = action.value or action.text
            if not text_to_verify:
                raise ValueError("see action requires text in 'value' field")
            # For dynamic elements (like notifications), check if text exists in DOM first
            # Then try to wait for visibility (with shorter timeout for transient elements)
            locator = self.page.get_by_text(text_to_verify, exact=False)
            try:
                locator.wait_for(state="attached", timeout=2000)  # Just check if exists in DOM
                # Try to wait for visibility, but don't fail if it's transient
                try:
                    locator.wait_for(state="visible", timeout=3000)
                except Exception:
                    # Element exists but may be hidden/transient - that's OK for notifications
                    print(f"[dynamic-agent] Text '{text_to_verify}' found in DOM (may be hidden/transient)")
            except Exception:
                # Not found at all - fail
                locator.wait_for(state="visible", timeout=8000)
        
        elif action.action == "done":
            pass  # Goal achieved
        
        else:
            raise ValueError(f"Unknown action: {action.action}")
