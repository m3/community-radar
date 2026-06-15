# Playwright Backend Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix resource leaks, selector injection risks, performance issues, and cross-platform compatibility in `PlaywrightPage`.

**Architecture:** Use `try-finally` for robust cleanup, pass arguments to `evaluate` to avoid injection, use lightweight DOM checks for stability, and use OS-aware modifiers for keyboard shortcuts.

**Tech Stack:** Python, Playwright.

---

### Task 1: Fix Resource Leak in `__init__`

**Files:**
- Modify: `scripts/reddit/playwright_backend.py`

- [ ] **Step 1: Wrap initialization in `try-except`**

Wrap the `sync_playwright().start()` and browser launch logic in a `try-except`. If any step fails before `self._pw` and `self._browser` are fully set, ensure `self._pw.stop()` is called if it was started.

- [ ] **Step 2: Verify cleanup on failure**

Since it's hard to trigger a launch failure reliably in a test without mocking, we will rely on code review and manual inspection of the logic.

- [ ] **Step 3: Commit**

```bash
git add scripts/reddit/playwright_backend.py
git commit -m "fix(reddit): prevent resource leak in PlaywrightPage init"
```

### Task 2: Refactor `evaluate` calls to prevent Selector Injection

**Files:**
- Modify: `scripts/reddit/playwright_backend.py`

- [ ] **Step 1: Refactor `remove_element`**

Change `self._page.evaluate(f"document.querySelector('{selector}')?.remove()")` to pass `selector` as an argument.

- [ ] **Step 2: Refactor `scroll_by` and `scroll_to`**

Pass `x` and `y` as arguments to `evaluate`.

- [ ] **Step 3: Refactor `get_scroll_top` and `get_viewport_height`**

Ensure these are safe (they don't take parameters currently, but check if they should).

- [ ] **Step 4: Commit**

```bash
git add scripts/reddit/playwright_backend.py
git commit -m "security(reddit): prevent selector injection in evaluate calls"
```

### Task 3: Optimize `wait_dom_stable`

**Files:**
- Modify: `scripts/reddit/playwright_backend.py`

- [ ] **Step 1: Replace `page.content()` with lightweight check**

Use `self.page.evaluate("() => document.body ? document.body.innerHTML.length : 0")` instead of `page.content()` which serializes the entire DOM.

- [ ] **Step 2: Commit**

```bash
git add scripts/reddit/playwright_backend.py
git commit -m "perf(reddit): optimize wait_dom_stable with lightweight check"
```

### Task 4: Cross-Platform Keys and Type Safety

**Files:**
- Modify: `scripts/reddit/playwright_backend.py`

- [ ] **Step 1: Implement `_get_modifier()`**

Add a helper to return `"Meta"` on Mac and `"Control"` on others (via `sys.platform`).

- [ ] **Step 2: Update `input_content_editable` and `select_all_text`**

Use the modifier for "Select All".

- [ ] **Step 3: Fix type ignore in `mouse_click`**

Cast the `button` string to the expected Literal type.

- [ ] **Step 4: Commit**

```bash
git add scripts/reddit/playwright_backend.py
git commit -m "fix(reddit): cross-platform keys and type safety in PlaywrightPage"
```

### Task 5: Verification

- [ ] **Step 1: Run a smoke test**

Create a simple script that instantiates `PlaywrightPage`, navigates to a local file or a simple site, and closes.

- [ ] **Step 2: Finalize**

```bash
git commit -m "test(reddit): add smoke test for PlaywrightPage fixes"
```
