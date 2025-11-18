"""
DOM Semantic Indexer - Stage 1 of Hybrid Approach

Builds intelligent index of page elements using pure Playwright.
No AI required - fast, free, and deterministic.

Extracts and prioritizes selectors:
  Priority 1: #id (best)
  Priority 2: [data-testid]
  Priority 3: text=
  Priority 4: [name]
  Priority 5: CSS fallback
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

try:
    from playwright.sync_api import Page, ElementHandle
except ImportError:  # pragma: no cover
    Page = None  # type: ignore
    ElementHandle = None  # type: ignore


@dataclass
class ElementInfo:
    """Rich element information with priority-sorted selector"""
    
    tag: str                      # HTML tag (input, button, a, etc.)
    selector: str                 # Best selector (#id, [data-testid], text=, etc.)
    priority: int                 # 1=highest (id), 5=lowest (CSS)
    text: Optional[str] = None    # Visible text content
    role: str = ""                # Semantic role (button, input:text, link, etc.)
    attributes: Dict[str, str] = None  # Useful attrs (placeholder, aria-label, etc.)
    
    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}


class DOMSemanticIndexer:
    """
    Builds intelligent index of page elements.
    Pure Playwright - no AI, fast, free.
    
    Usage:
        indexer = DOMSemanticIndexer(page)
        elements = indexer.build_index()
        context = indexer.to_context_string()
    """
    
    def __init__(self, page: Page):
        self.page = page
        self.elements: List[ElementInfo] = []
    
    def build_index(self, max_elements: int = 150) -> List[ElementInfo]:
        """
        Extract and prioritize all interactive elements.
        
        Args:
            max_elements: Maximum number of elements to index
            
        Returns:
            List of ElementInfo sorted by priority (best selectors first)
        """
        self.elements = []
        
        # Find all interactive elements (visible only)
        interactive_selectors = [
            "input:visible",
            "button:visible", 
            "a:visible",
            "select:visible",
            "textarea:visible",
            "[role=button]:visible",
            "[role=link]:visible",
        ]
        
        for selector in interactive_selectors:
            try:
                elements = self.page.query_selector_all(selector)
                
                for el in elements:
                    if len(self.elements) >= max_elements:
                        break
                    
                    info = self._analyze_element(el)
                    if info:
                        self.elements.append(info)
            except Exception:
                # Skip if selector fails (page might be loading)
                continue
        
        # Sort by priority (id > data-testid > text > name > CSS)
        self.elements.sort(key=lambda x: (x.priority, x.tag))
        
        return self.elements
    
    def _analyze_element(self, el: ElementHandle) -> Optional[ElementInfo]:
        """
        Extract best selector and metadata for element.
        
        Priority order:
          1. #id
          2. [data-testid]
          3. text= (for buttons/links)
          4. [name]
          5. CSS class (fallback)
        """
        try:
            tag = el.evaluate("el => el.tagName.toLowerCase()")
            text_content = el.text_content() or ""
            text_trimmed = text_content.strip()[:50]  # First 50 chars
            
            # Priority 1: id
            el_id = el.get_attribute("id")
            if el_id and el_id.strip():
                return ElementInfo(
                    tag=tag,
                    selector=f"#{el_id}",
                    priority=1,
                    text=text_trimmed if text_trimmed else None,
                    role=self._get_role(el, tag),
                    attributes=self._get_attrs(el)
                )
            
            # Priority 2: data-testid
            testid = el.get_attribute("data-testid")
            if testid and testid.strip():
                return ElementInfo(
                    tag=tag,
                    selector=f'[data-testid="{testid}"]',
                    priority=2,
                    text=text_trimmed if text_trimmed else None,
                    role=self._get_role(el, tag),
                    attributes=self._get_attrs(el)
                )
            
            # Priority 3: text (for buttons/links with short, stable text)
            if text_trimmed and tag in ["button", "a"] and len(text_trimmed) < 30:
                return ElementInfo(
                    tag=tag,
                    selector=f'text={text_trimmed}',
                    priority=3,
                    text=text_trimmed,
                    role=self._get_role(el, tag),
                    attributes=self._get_attrs(el)
                )
            
            # Priority 4: name
            name = el.get_attribute("name")
            if name and name.strip():
                return ElementInfo(
                    tag=tag,
                    selector=f'[name="{name}"]',
                    priority=4,
                    text=text_trimmed if text_trimmed else None,
                    role=self._get_role(el, tag),
                    attributes=self._get_attrs(el)
                )
            
            # Priority 5: CSS class (fallback, less reliable)
            class_name = el.get_attribute("class")
            if class_name and class_name.strip():
                first_class = class_name.split()[0]
                return ElementInfo(
                    tag=tag,
                    selector=f'.{first_class}',
                    priority=5,
                    text=text_trimmed if text_trimmed else None,
                    role=self._get_role(el, tag),
                    attributes=self._get_attrs(el)
                )
            
            return None
        except Exception:
            # Element might be stale or inaccessible
            return None
    
    def _get_role(self, el: ElementHandle, tag: str) -> str:
        """Determine semantic role of element"""
        el_type = el.get_attribute("type")
        
        if tag == "input":
            return f"input:{el_type or 'text'}"
        elif tag == "button":
            return "button"
        elif tag == "a":
            return "link"
        elif tag == "select":
            return "dropdown"
        elif tag == "textarea":
            return "textarea"
        
        return tag
    
    def _get_attrs(self, el: ElementHandle) -> Dict[str, str]:
        """Extract useful attributes for AI context"""
        attrs = {}
        
        for attr in ["placeholder", "aria-label", "title", "value", "href"]:
            val = el.get_attribute(attr)
            if val and val.strip():
                attrs[attr] = val.strip()[:50]  # Limit length
        
        return attrs
    
    def to_context_string(self) -> str:
        """
        Convert index to AI-friendly context string.
        Much more readable than raw HTML snippets.
        
        Example output:
            # Page Elements (Priority-Sorted)
            
            🔘 #search-btn → "Search"
            📝 #search-input [placeholder: Search for products...]
            🔗 text=Cart (2) → "Cart (2)"
            🔘 [data-testid="checkout-btn"] → "Proceed to Checkout"
        """
        if not self.elements:
            return "# No interactive elements found on page"
        
        lines = ["# Page Elements (Priority-Sorted)", ""]
        
        for el in self.elements[:100]:  # Top 100 elements
            # Role emoji
            role_emoji = {
                "button": "🔘",
                "input:text": "📝",
                "input:password": "🔒",
                "input:email": "📧",
                "input:search": "🔍",
                "link": "🔗",
                "dropdown": "📋",
                "textarea": "📄",
            }.get(el.role, "▪️")
            
            # Build line: emoji selector [text] [attributes]
            line_parts = [role_emoji, el.selector]
            
            if el.text:
                line_parts.append(f'→ "{el.text}"')
            
            if el.attributes.get("placeholder"):
                line_parts.append(f'[placeholder: {el.attributes["placeholder"]}]')
            
            if el.attributes.get("aria-label"):
                line_parts.append(f'[aria-label: {el.attributes["aria-label"]}]')
            
            lines.append(" ".join(line_parts))
        
        return "\n".join(lines)
    
    def get_by_role(self, role: str) -> List[ElementInfo]:
        """Get all elements of specific role (e.g., 'button', 'input:text')"""
        return [el for el in self.elements if el.role == role]
    
    def get_by_priority(self, max_priority: int = 3) -> List[ElementInfo]:
        """Get only high-priority elements (1-3: id, data-testid, text)"""
        return [el for el in self.elements if el.priority <= max_priority]
