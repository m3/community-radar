# Playwright Backend & Proxies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a native Playwright-based automation backend with residential proxy support and BWS secrets integration, allowing for scalable and IP-resilient Reddit scraping.

**Architecture:** Introduce a pluggable backend system. The `BridgePage` interface is extracted into a common base or replicated in a new `PlaywrightBackend` class. The system uses the existing `bws` CLI integration to fetch proxy credentials and launches headless Chromium instances.

**Tech Stack:** Python, Playwright, BWS CLI, YAML.

---

### Task 1: Playwright Dependency & Base Structure

**Files:**
- Modify: `scripts/pyproject.toml`
- Create: `scripts/reddit/backend.py`

- [ ] **Step 1: Add `playwright` to dependencies**

```toml
# scripts/pyproject.toml
dependencies = [
    "websockets>=12.0",
    "mcp[cli]>=1.27.0",
    "pyyaml>=6.0.3",
    "playwright>=1.40.0",
]
```

- [ ] **Step 2: Install playwright and browsers**

Run: `cd scripts && uv sync && uv run playwright install chromium`

- [ ] **Step 3: Define common Browser interface**

Create `scripts/reddit/backend.py` with an abstract base or common interface structure to be shared between Bridge and Playwright.

```python
from typing import Protocol, Any

class BrowserPage(Protocol):
    def navigate(self, url: str) -> None: ...
    def wait_for_load(self, timeout: float = 60.0) -> None: ...
    def evaluate(self, expression: str, timeout: float = 30.0) -> Any: ...
    # ... other methods from BridgePage
```

- [ ] **Step 4: Commit**

```bash
git add scripts/pyproject.toml scripts/reddit/backend.py
git commit -m "chore(reddit): add playwright dependency and base interface"
```

---

### Task 2: Implement Playwright Backend

**Files:**
- Create: `scripts/reddit/playwright_backend.py`

- [ ] **Step 1: Implement `PlaywrightPage` class**

Replicate the `BridgePage` methods using the `playwright.sync_api`.

```python
from playwright.sync_api import sync_playwright, Page, Browser
import os

class PlaywrightPage:
    def __init__(self, headless=True, proxy=None):
        self.pw = sync_playwright().start()
        browser_args = {}
        if proxy:
            browser_args["proxy"] = {"server": proxy}
            
        self.browser = self.pw.chromium.launch(headless=headless, **browser_args)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()

    def navigate(self, url: str):
        self.page.goto(url)

    def wait_for_load(self, timeout: int = 60000):
        self.page.wait_for_load_state("networkidle", timeout=timeout)

    def evaluate(self, expression: str):
        return self.page.evaluate(expression)
    
    def close(self):
        self.browser.close()
        self.pw.stop()
        
    # ... implement all other BridgePage methods (click, input, etc.)
```

- [ ] **Step 2: Commit**

```bash
git add scripts/reddit/playwright_backend.py
git commit -m "feat(reddit): implement playwright backend"
```

---

### Task 3: BWS Proxy Integration

**Files:**
- Modify: `scripts/cli.py`
- Modify: `src/collectors/discord.py` (Move BWS helper if needed)

- [ ] **Step 1: Implement `get_proxy_from_bws` helper**

```python
def get_proxy_from_bws(secret_id: str) -> str | None:
    import subprocess
    import json
    if not secret_id:
        return None
    try:
        result = subprocess.run(
            ["bws", "secret", "get", secret_id, "--output", "json"],
            capture_output=True, text=True, check=True
        )
        data = json.loads(result.stdout)
        return data.get("value")
    except Exception as e:
        print(f"Error fetching proxy from BWS: {e}")
        return None
```

- [ ] **Step 2: Update `_connect` in `scripts/cli.py` to support playwright**

```python
def _connect(args: argparse.Namespace):
    # Logic to choose between Bridge and Playwright based on args or config
    backend = getattr(args, "backend", "bridge")
    if backend == "playwright":
        from reddit.playwright_backend import PlaywrightPage
        proxy = get_proxy_from_bws(args.proxy_secret_id) if args.proxy_secret_id else None
        return PlaywrightPage(headless=not args.headed, proxy=proxy)
    else:
        # Existing bridge logic
```

- [ ] **Step 3: Commit**

```bash
git add scripts/cli.py
git commit -m "feat(reddit): integrate BWS proxies into CLI"
```

---

### Task 4: Configuration & Final Integration

**Files:**
- Modify: `config.yaml`
- Modify: `src/collectors/reddit.py`
- Modify: `src/collectors/reddit_domain.py`

- [ ] **Step 1: Add backend settings to `config.yaml`**

```yaml
reddit_global:
  backend: "playwright"
  headless: true
  proxy_secret_id: "global-uuid"
```

- [ ] **Step 2: Pass backend flags from collectors to `run_cli`**

Update `run_cli` to include `--backend`, `--proxy-secret-id`, and `--headed` based on config.

- [ ] **Step 3: Test with a test domain and playwright**

Run: `uv run python src/main.py --client pure-pool-pro collect` (ensuring playwright is set as backend).

- [ ] **Step 4: Commit**

```bash
git add config.yaml src/collectors/reddit.py src/collectors/reddit_domain.py
git commit -m "feat(reddit): complete playwright and proxy integration"
```
