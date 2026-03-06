#!/usr/bin/env python3
"""Capture screenshots for documentation. Run with server at http://localhost:8081."""
import os
import sys
import time

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Run: pip install playwright && python -m playwright install chromium")
    sys.exit(1)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "screenshots")
BASE = "http://localhost:8081"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        try:
            page.goto(BASE, wait_until="networkidle", timeout=15000)
        except Exception as e:
            print(f"Ensure server is running at {BASE}: {e}")
            browser.close()
            sys.exit(1)
        time.sleep(1.5)
        page.screenshot(path=os.path.join(OUT_DIR, "01-main.png"))
        # Tag filter
        arxiv_btn = page.locator('#tag-filter-bar button[data-tag="arXiv"]')
        if arxiv_btn.count():
            arxiv_btn.first.click()
            time.sleep(0.5)
        page.screenshot(path=os.path.join(OUT_DIR, "02-tag-filter.png"))
        # Deep read modal - use JS click to bypass visibility
        page.evaluate("""() => {
            const btn = document.querySelector('button[onclick*="openDeepReadModal"]');
            if (btn) btn.click();
        }""")
        time.sleep(1)
        page.screenshot(path=os.path.join(OUT_DIR, "03-deep-read.png"))
        page.keyboard.press("Escape")
        time.sleep(0.5)
        # Close modal via JS if Escape didn't work
        page.evaluate("""() => {
            const m = document.getElementById('deepReadModal');
            if (m && !m.classList.contains('hidden')) {
                m.classList.add('hidden'); m.classList.remove('flex');
                document.body.style.overflow = '';
            }
        }""")
        time.sleep(0.3)
        # Settings
        settings_btn = page.locator('button[title="Settings"]')
        if settings_btn.count():
            settings_btn.first.click()
        time.sleep(0.3)
        time.sleep(0.3)
        page.screenshot(path=os.path.join(OUT_DIR, "04-settings.png"))
        page.keyboard.press("Escape")
        browser.close()
    print(f"Screenshots saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
