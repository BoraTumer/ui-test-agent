"""
Context Builder - Stage 2 of Hybrid Approach

Builds optimal context for single AI agent by combining:
  - User intent analysis (regex-based, no AI)
  - Semantic DOM index (from dom_indexer)
  - Few-shot examples (matching use case)
  - Best practices and rules

Much smarter than raw HTML snippets.
"""

from __future__ import annotations

import json
from typing import Dict, List, Any, Optional

from .dom_indexer import ElementInfo


class ContextBuilder:
    """
    Builds rich, structured context for scenario generation agent.
    
    Combines multiple information sources into optimal prompt:
      1. Intent analysis (what user wants to do)
      2. Available elements (smart index)
      3. Relevant examples (few-shot learning)
      4. Best practices (selector strategy, step limits)
    
    Usage:
        builder = ContextBuilder()
        context = builder.build_context(
            user_instructions="Login as admin",
            dom_index=indexer.build_index(),
            base_env={"baseUrl": "http://localhost:8000"}
        )
    """
    
    def __init__(self):
        self.few_shot_examples = self._load_examples()
    
    def build_context(
        self,
        user_instructions: str,
        dom_index: List[ElementInfo],
        base_env: Dict[str, Any],
        feedback: Optional[str] = None
    ) -> str:
        """
        Create rich, structured context for agent.
        
        Args:
            user_instructions: Natural language test description
            dom_index: Semantic index from DOMSemanticIndexer
            base_env: Environment variables (baseUrl, etc.)
            feedback: Optional feedback from previous attempt
            
        Returns:
            Formatted context string for AI agent
        """
        sections = []
        
        # 1. Intent Analysis
        intent_section = self._analyze_intent(user_instructions)
        if intent_section:
            sections.append(intent_section)
        
        # 2. User Instructions
        sections.append(f"# User Instructions\n\n{user_instructions}")
        
        # 3. Available Elements (Smart Index)
        if dom_index:
            sections.append(self._format_dom_index(dom_index))
        
        # 4. Relevant Few-Shot Examples
        examples = self._get_relevant_examples(user_instructions)
        if examples:
            sections.append(examples)
        
        # 5. Best Practices
        sections.append(self._get_best_practices())
        
        # 6. Environment
        env_json = json.dumps(base_env, ensure_ascii=False, indent=2)
        sections.append(f"# Environment\n\n```json\n{env_json}\n```")
        
        # 7. Feedback (if retry)
        if feedback:
            sections.append(f"# Previous Attempt Feedback\n\n{feedback}")
        
        return "\n\n---\n\n".join(sections)
    
    def _analyze_intent(self, instructions: str) -> str:
        """
        Extract key patterns and intents from user instructions.
        Regex-based, no AI needed.
        
        Detects common patterns:
          - Authentication (login, sign in)
          - Search (search, find)
          - E-commerce (cart, checkout, purchase)
          - Form filling (fill, enter, type)
          - Navigation (go to, open, click)
        """
        instructions_lower = instructions.lower()
        
        detected_actions = []
        
        # Authentication patterns
        if any(word in instructions_lower for word in ["login", "sign in", "log in", "authenticate"]):
            detected_actions.append("🔐 **Authentication Flow**")
        
        # Search patterns
        if any(word in instructions_lower for word in ["search", "find", "look for"]):
            detected_actions.append("🔍 **Search Operation**")
        
        # E-commerce patterns
        if any(word in instructions_lower for word in ["cart", "checkout", "purchase", "buy", "add to cart"]):
            detected_actions.append("🛒 **E-commerce Checkout**")
        
        # Form filling
        if any(word in instructions_lower for word in ["fill", "enter", "type", "input"]):
            detected_actions.append("⌨️ **Form Input**")
        
        # Navigation
        if any(word in instructions_lower for word in ["go to", "navigate", "open", "visit"]):
            detected_actions.append("🧭 **Navigation**")
        
        # Click interactions
        if any(word in instructions_lower for word in ["click", "press", "tap"]):
            detected_actions.append("👆 **Click Interaction**")
        
        # Assertions
        if any(word in instructions_lower for word in ["verify", "check", "ensure", "confirm"]):
            detected_actions.append("✅ **Verification/Assertion**")
        
        if detected_actions:
            return "# Detected Intent\n\n" + "\n".join(detected_actions)
        
        return ""
    
    def _format_dom_index(self, dom_index: List[ElementInfo]) -> str:
        """
        Format element index for AI consumption.
        Groups by role for better readability.
        """
        if not dom_index:
            return ""
        
        lines = ["# Available Page Elements", "", "**Use these exact selectors - don't guess!**", ""]
        
        # Group elements by role
        by_role: Dict[str, List[ElementInfo]] = {}
        for el in dom_index[:100]:  # Top 100 elements
            by_role.setdefault(el.role, []).append(el)
        
        # Format each role group
        role_names = {
            "button": "Buttons",
            "input:text": "Text Inputs",
            "input:password": "Password Inputs",
            "input:email": "Email Inputs",
            "input:search": "Search Inputs",
            "link": "Links",
            "dropdown": "Dropdowns",
            "textarea": "Text Areas",
        }
        
        for role, elements in sorted(by_role.items()):
            role_display = role_names.get(role, role.upper())
            lines.append(f"## {role_display}")
            lines.append("")
            
            for el in elements[:15]:  # Top 15 per role
                # Format: selector → "text" [attributes]
                line = f"- `{el.selector}`"
                
                if el.text:
                    line += f' → "{el.text}"'
                
                attrs = []
                if el.attributes.get("placeholder"):
                    attrs.append(f'placeholder: {el.attributes["placeholder"]}')
                if el.attributes.get("aria-label"):
                    attrs.append(f'aria: {el.attributes["aria-label"]}')
                
                if attrs:
                    line += f' [{", ".join(attrs)}]'
                
                lines.append(line)
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _get_relevant_examples(self, instructions: str) -> str:
        """
        Return few-shot examples matching the detected intent.
        Helps agent learn correct output format.
        """
        instructions_lower = instructions.lower()
        
        # Login example
        if any(word in instructions_lower for word in ["login", "sign in", "authenticate"]):
            return """# Example: Login Flow

```json
{
  "meta": {
    "name": "User Login",
    "description": "Login with credentials"
  },
  "env": {
    "baseUrl": "http://localhost:8000"
  },
  "flow": [
    {"action": "go", "url": "/login.html"},
    {"action": "type", "selector": "#username", "value": "admin"},
    {"action": "type", "selector": "#password", "value": "secret"},
    {"action": "click", "selector": "#login-btn"},
    {"action": "see", "text": "Welcome", "meaning": "Login successful"}
  ]
}
```
"""
        
        # Search example
        elif any(word in instructions_lower for word in ["search", "find"]):
            return """# Example: Search Flow

```json
{
  "meta": {
    "name": "Product Search",
    "description": "Search for products"
  },
  "env": {
    "baseUrl": "http://localhost:8000"
  },
  "flow": [
    {"action": "go", "url": "/shop.html"},
    {"action": "type", "selector": "#search-input", "value": "laptop"},
    {"action": "click", "selector": "#search-btn"},
    {"action": "see", "text": "Search Results", "meaning": "Results displayed"}
  ]
}
```
"""
        
        # E-commerce example
        elif any(word in instructions_lower for word in ["cart", "checkout", "purchase"]):
            return """# Example: E-commerce Checkout

```json
{
  "meta": {
    "name": "Add to Cart",
    "description": "Add product and checkout"
  },
  "env": {
    "baseUrl": "http://localhost:8000"
  },
  "flow": [
    {"action": "go", "url": "/products.html"},
    {"action": "click", "selector": "text=Add to Cart"},
    {"action": "click", "selector": "#cart-btn"},
    {"action": "see", "text": "Cart", "meaning": "Cart opened"},
    {"action": "click", "selector": "#checkout-btn"}
  ]
}
```
"""
        
        return ""
    
    def _get_best_practices(self) -> str:
        """Return selector strategy and best practices"""
        return """# Best Practices & Rules

## Selector Strategy (Priority Order)
1. **#id** - BEST (most reliable, use whenever available)
2. **[data-testid]** - GOOD (stable test selectors)
3. **text=** - GOOD (for buttons/links with exact text)
4. **[name]** - OK (for form inputs)
5. **CSS classes** - AVOID (fragile, changes frequently)

## Scenario Guidelines
- ✅ Keep scenarios **under 10 steps** (simpler is better)
- ✅ Use **exact selectors** from "Available Page Elements" section
- ✅ Match **exact text** from page for text= selectors
- ✅ Add **see** action after critical steps for verification
- ❌ **DON'T guess** selectors - use provided ones
- ❌ **DON'T add** extra verification steps unless requested
- ❌ **DON'T use** placeholder attributes as selectors (unreliable)

## Action Types
- `go` - Navigate to URL
- `type` - Enter text (requires: selector, value)
- `click` - Click element (requires: selector)
- `select` - Choose dropdown option (requires: selector, value)
- `check` - Check checkbox (requires: selector)
- `see` - Verify text appears (requires: text, optional: meaning)
- `seeUrl` - Verify URL contains text (requires: text)
- `wait` - Wait milliseconds (requires: ms)

## Output Format
Return **ONLY** valid JSON with this structure:
```json
{
  "meta": {"name": "...", "description": "..."},
  "env": {"baseUrl": "..."},
  "flow": [
    {"action": "...", ...}
  ]
}
```

**No markdown fences, no explanations, just pure JSON.**
"""
    
    def _load_examples(self) -> List[Dict]:
        """Load few-shot examples from file/database (future enhancement)"""
        # TODO: Load from scenarios/examples/ directory
        return []
