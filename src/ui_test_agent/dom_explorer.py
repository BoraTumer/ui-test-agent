from __future__ import annotations

import json
from typing import Optional

from playwright.sync_api import sync_playwright


def capture_dom_outline(url: str, max_nodes: int = 150, timeout_ms: int = 5000) -> Optional[str]:
    """Returns simplified HTML snippets of key interactive elements for the given URL."""
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            html_snippets = page.evaluate(
                """
                (maxNodes) => {
                    const snippets = [];
                    const elements = document.querySelectorAll('input, button, a, select, textarea, [role="button"]');
                    let count = 0;
                    
                    for (const el of elements) {
                        if (count >= maxNodes) break;
                        
                        // Build simplified HTML representation
                        let html = `<${el.tagName.toLowerCase()}`;
                        
                        // Add important attributes
                        if (el.id) html += ` id="${el.id}"`;
                        if (el.className) html += ` class="${el.className}"`;
                        if (el.getAttribute('name')) html += ` name="${el.getAttribute('name')}"`;
                        if (el.getAttribute('type')) html += ` type="${el.getAttribute('type')}"`;
                        if (el.getAttribute('placeholder')) html += ` placeholder="${el.getAttribute('placeholder')}"`;
                        if (el.getAttribute('data-testid')) html += ` data-testid="${el.getAttribute('data-testid')}"`;
                        if (el.getAttribute('role')) html += ` role="${el.getAttribute('role')}"`;
                        if (el.getAttribute('href')) html += ` href="${el.getAttribute('href')}"`;
                        
                        // Add text content for buttons/links
                        const text = (el.innerText || el.textContent || '').trim().slice(0, 50);
                        if (text) {
                            html += `>${text}</${el.tagName.toLowerCase()}>`;
                        } else {
                            html += ' />';
                        }
                        
                        snippets.push(html);
                        count += 1;
                    }
                    
                    return snippets.join('\\n');
                }
                """,
                max_nodes,
            )
            browser.close()
            return html_snippets
    except Exception:
        return None
