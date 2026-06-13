"""Playwright backend for Reddit automation.

Implements BrowserPage protocol using playwright.sync_api.
"""

from __future__ import annotations

import os
import time
from typing import Any

from playwright.sync_api import sync_playwright

from .errors import ElementNotFoundError


class PlaywrightPage:
    """Playwright implementation compatible with BrowserPage interface."""

    def __init__(self, headless: bool = True, proxy: str | None = None) -> None:
        self._pw = sync_playwright().start()
        try:
            browser_args: dict[str, Any] = {}
            if proxy:
                # Format: http://user:pass@host:port
                browser_args["proxy"] = {"server": proxy}

            self._browser = self._pw.chromium.launch(headless=headless, **browser_args)
            self._context = self._browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
            )
            self._page = self._context.new_page()
        except Exception:
            self._pw.stop()
            raise

    # ─── Navigation ─────────────────────────────────────────────

    def navigate(self, url: str) -> None:
        self._page.goto(url)

    def wait_for_load(self, timeout: float = 60.0) -> None:
        self._page.wait_for_load_state("networkidle", timeout=timeout * 1000)

    def wait_dom_stable(self, timeout: float = 10.0, interval: float = 0.5) -> None:
        """Wait until the DOM stops changing."""
        start_time = time.time()
        last_html = ""
        while time.time() - start_time < timeout:
            current_html = self._page.content()
            if current_html == last_html:
                return
            last_html = current_html
            time.sleep(interval)

    # ─── JavaScript execution ───────────────────────────────────

    def evaluate(self, expression: str, timeout: float = 30.0) -> Any:
        return self._page.evaluate(expression)

    # ─── Element queries ────────────────────────────────────────

    def query_selector(self, selector: str) -> str | None:
        element = self._page.query_selector(selector)
        return "found" if element else None

    def query_selector_all(self, selector: str) -> list[str]:
        elements = self._page.query_selector_all(selector)
        return ["found"] * len(elements)

    def has_element(self, selector: str) -> bool:
        return self._page.query_selector(selector) is not None

    def wait_for_element(self, selector: str, timeout: float = 30.0) -> str:
        try:
            self._page.wait_for_selector(selector, timeout=timeout * 1000)
            return "found"
        except Exception:
            raise ElementNotFoundError(selector) from None

    # ─── Element operations ─────────────────────────────────────

    def click_element(self, selector: str) -> None:
        self._page.click(selector)

    def input_text(self, selector: str, text: str) -> None:
        self._page.fill(selector, text)

    def input_content_editable(self, selector: str, text: str) -> None:
        """Type text into a contenteditable element."""
        self._page.click(selector)
        self._page.keyboard.press("Control+KeyA")
        self._page.keyboard.press("Backspace")
        self._page.keyboard.type(text)

    def get_element_text(self, selector: str) -> str | None:
        element = self._page.query_selector(selector)
        return element.inner_text() if element else None

    def get_element_attribute(self, selector: str, attr: str) -> str | None:
        element = self._page.query_selector(selector)
        return element.get_attribute(attr) if element else None

    def get_elements_count(self, selector: str) -> int:
        return len(self._page.query_selector_all(selector))

    def remove_element(self, selector: str) -> None:
        self._page.evaluate("s => document.querySelector(s)?.remove()", selector)

    def hover_element(self, selector: str) -> None:
        self._page.hover(selector)

    def select_all_text(self, selector: str) -> None:
        self._page.click(selector)
        self._page.keyboard.press("Control+KeyA")

    # ─── Scrolling ──────────────────────────────────────────────

    def scroll_by(self, x: int, y: int) -> None:
        self._page.evaluate("([x, y]) => window.scrollBy(x, y)", [x, y])

    def scroll_to(self, x: int, y: int) -> None:
        self._page.evaluate("([x, y]) => window.scrollTo(x, y)", [x, y])

    def scroll_to_bottom(self) -> None:
        self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    def scroll_element_into_view(self, selector: str) -> None:
        element = self._page.query_selector(selector)
        if element:
            element.scroll_into_view_if_needed()

    def scroll_nth_element_into_view(self, selector: str, index: int) -> None:
        elements = self._page.query_selector_all(selector)
        if index < len(elements):
            elements[index].scroll_into_view_if_needed()

    def get_scroll_top(self) -> int:
        return int(self._page.evaluate("window.pageYOffset || document.documentElement.scrollTop"))

    def get_viewport_height(self) -> int:
        return int(self._page.evaluate("window.innerHeight"))

    # ─── Input events ───────────────────────────────────────────

    def press_key(self, key: str) -> None:
        self._page.keyboard.press(key)

    def type_text(self, text: str, delay_ms: int = 50) -> None:
        self._page.keyboard.type(text, delay=delay_ms)

    def mouse_move(self, x: float, y: float) -> None:
        self._page.mouse.move(x, y)

    def mouse_click(self, x: float, y: float, button: str = "left") -> None:
        # Playwright uses Literal["left", "right", "middle"]
        self._page.mouse.click(x, y, button=button)  # type: ignore

    def dispatch_wheel_event(self, delta_y: float) -> None:
        # Playwright doesn't have a direct dispatch_wheel_event on mouse,
        # but we can use mouse.wheel
        self._page.mouse.wheel(0, delta_y)

    # ─── File upload ────────────────────────────────────────────

    def set_file_input(self, selector: str, files: list[str]) -> None:
        abs_paths = [os.path.abspath(path) for path in files]
        self._page.set_input_files(selector, abs_paths)

    def close(self) -> None:
        self._browser.close()
        self._pw.stop()
